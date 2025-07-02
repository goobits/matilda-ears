import asyncio
import base64
import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Pydantic models for API requests/responses
class TokenRequest(BaseModel):
    client_name: str
    expiration_days: int = 90
    one_time_use: bool = False

class TokenResponse(BaseModel):
    token: str
    expires: str
    client_name: str
    token_id: str
    one_time_use: bool

class RevokeTokenRequest(BaseModel):
    token_id: str

class ServerSettings(BaseModel):
    max_clients: int = 20
    default_expiration: int = 90
    whisper_model: str = "large-v3-turbo"

class ClientInfo(BaseModel):
    name: str
    token_id: str
    expires: str
    last_seen: Optional[str] = None
    is_active: bool = False
    one_time_use: bool = False
    used: bool = False

class TranscriptionResult(BaseModel):
    text: str
    confidence: float
    processing_time: float

class ServerStatus(BaseModel):
    status: str
    model: str
    gpu_available: bool
    clients: int
    uptime: float
    error: Optional[str] = None

class DashboardAPI:
    def __init__(self):
        self.app = FastAPI(title="STT Dashboard API", version="1.0.0")
        self.server_start_time = time.time()
        self.transcription_server = None
        
        # Import and initialize token manager
        from docker.src.token_manager import get_token_manager
        self.token_manager = get_token_manager()
        
        self.setup_routes()
        self.setup_middleware()


    def setup_middleware(self):
        """Setup CORS and other middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_routes(self):
        """Setup all API routes"""
        
        # Serve dashboard static files
        dashboard_dir = Path(__file__).parent.parent / "dashboard"
        self.app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def serve_dashboard():
            """Serve the main dashboard HTML"""
            return FileResponse(dashboard_dir / "index.html")

        @self.app.get("/api/status")
        async def get_server_status() -> ServerStatus:
            """Get current server status"""
            try:
                status = ServerStatus(
                    status="running",
                    model=os.getenv("WHISPER_MODEL", "large-v3-turbo"),
                    gpu_available=self._check_gpu_available(),
                    clients=len([c for c in self.clients_db.values() if c.is_active]),
                    uptime=time.time() - self.server_start_time
                )
                return status
            except Exception as e:
                logging.error(f"Failed to get server status: {e}")
                return ServerStatus(
                    status="error",
                    model="unknown",
                    gpu_available=False,
                    clients=0,
                    uptime=0,
                    error=str(e)
                )

        @self.app.post("/api/generate-token")
        async def generate_token(request: TokenRequest) -> TokenResponse:
            """Generate a new client token with QR code data"""
            try:
                # Generate token using TokenManager
                token_data = self.token_manager.generate_token(
                    client_name=request.client_name,
                    expiration_days=request.expiration_days,
                    one_time_use=request.one_time_use
                )
                
                return TokenResponse(
                    token=token_data["token"],
                    expires=token_data["expires"],
                    client_name=token_data["client_name"],
                    token_id=token_data["token_id"],
                    one_time_use=token_data["one_time_use"]
                )
                
            except Exception as e:
                logging.error(f"Failed to generate token: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/clients")
        async def get_active_clients() -> List[ClientInfo]:
            """Get list of all active clients"""
            clients = self.token_manager.get_active_clients()
            return [ClientInfo(**client) for client in clients]

        @self.app.post("/api/revoke-token")
        async def revoke_token(request: RevokeTokenRequest):
            """Revoke a client token"""
            success = self.token_manager.revoke_token(request.token_id)
            if success:
                return {"success": True}
            else:
                raise HTTPException(status_code=404, detail="Token not found")

        @self.app.post("/api/transcribe")
        async def transcribe_audio(audio: UploadFile = File(...)) -> TranscriptionResult:
            """Test transcription endpoint"""
            try:
                start_time = time.time()
                
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                    content = await audio.read()
                    tmp_file.write(content)
                    tmp_path = tmp_file.name
                
                try:
                    # Import transcription functionality
                    from lib.core.transcription.client import TranscriptionClient
                    from lib.core.config import Config
                    
                    config = Config()
                    client = TranscriptionClient(config)
                    
                    # Perform transcription
                    result = await client.transcribe_file(tmp_path)
                    processing_time = time.time() - start_time
                    
                    return TranscriptionResult(
                        text=result.get('text', ''),
                        confidence=result.get('confidence', 0.0),
                        processing_time=processing_time
                    )
                    
                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
            except Exception as e:
                logging.error(f"Transcription test failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/settings")
        async def save_settings(settings: ServerSettings):
            """Save server settings"""
            try:
                # Save settings to config file
                settings_file = Path("/app/data/dashboard_settings.json")
                settings_file.parent.mkdir(exist_ok=True)
                settings_file.write_text(settings.model_dump_json())
                
                return {"success": True}
            except Exception as e:
                logging.error(f"Failed to save settings: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/validate-token")
        async def validate_token(token: str) -> Dict[str, Any]:
            """Validate a JWT token (used by WebSocket server)"""
            # For first-time connections, mark one-time tokens as used
            payload = self.token_manager.validate_token(token, mark_as_used=True)
            if payload:
                return payload
            else:
                raise HTTPException(status_code=401, detail="Invalid or expired token")

    def _check_gpu_available(self) -> bool:
        """Check if GPU acceleration is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def mark_client_active(self, token_id: str):
        """Mark a client as active when they connect"""
        self.token_manager.mark_client_active(token_id)

    def mark_client_inactive(self, token_id: str):
        """Mark a client as inactive when they disconnect"""
        self.token_manager.mark_client_inactive(token_id)

# Global instance
dashboard_api = DashboardAPI()
app = dashboard_api.app