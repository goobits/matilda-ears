import os
import secrets
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from docker.src import __version__
from matilda_ears.core.token_manager import TokenManager

if TYPE_CHECKING:
    from matilda_ears.transcription.server.core import MatildaWebSocketServer

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


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


class ClientInfo(BaseModel):
    name: str
    token_id: str
    expires: str
    last_seen: str | None = None
    active: bool = False
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
    websocket_port: int
    websocket_secure: bool
    error: str | None = None


class DashboardAPI:
    def __init__(
        self,
        token_manager: TokenManager,
        transcription_server: "MatildaWebSocketServer",
        api_token: str | None = None,
    ) -> None:
        self.app = FastAPI(title="Matilda Dashboard API", version=__version__)
        self.server_start_time = time.time()
        self.token_manager = token_manager
        self.transcription_server = transcription_server
        self.api_token = api_token or os.getenv("MATILDA_API_TOKEN")
        if not self.api_token:
            raise RuntimeError("MATILDA_API_TOKEN must be set before starting the dashboard")

        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        allowed_origins = [
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8080").split(",")
            if origin.strip()
        ]
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def _setup_routes(self) -> None:
        dashboard_dir = Path(__file__).parent.parent / "dashboard"
        self.app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

        async def verify_admin(auth_header: str | None = Security(api_key_header)) -> None:
            if not auth_header:
                raise HTTPException(status_code=401, detail="Missing Authorization header")
            scheme, _, token = auth_header.partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise HTTPException(status_code=401, detail="Expected Bearer authentication")
            if not secrets.compare_digest(token, self.api_token):
                raise HTTPException(status_code=403, detail="Invalid dashboard token")

        protected = [Depends(verify_admin)]

        @self.app.get("/", response_class=HTMLResponse)
        async def serve_dashboard() -> FileResponse:
            return FileResponse(dashboard_dir / "index.html")

        @self.app.get("/api/status")
        async def get_server_status() -> ServerStatus:
            server = self.transcription_server
            backend = server.backend
            ready = bool(backend and backend.is_ready)
            return ServerStatus(
                status="running" if ready else "starting",
                model=server.model_size,
                gpu_available=self._check_gpu_available(),
                clients=len(server.connected_clients),
                uptime=time.time() - self.server_start_time,
                websocket_port=server.port,
                websocket_secure=server.ssl_enabled,
            )

        @self.app.post("/api/generate-token", dependencies=protected)
        async def generate_token(request: TokenRequest) -> TokenResponse:
            token_data = self.token_manager.generate_token(
                client_name=request.client_name,
                expiration_days=request.expiration_days,
                one_time_use=request.one_time_use,
            )
            return TokenResponse(**token_data)

        @self.app.get("/api/clients", dependencies=protected)
        async def get_active_clients() -> list[ClientInfo]:
            return [ClientInfo(**client) for client in self.token_manager.get_active_clients()]

        @self.app.post("/api/revoke-token", dependencies=protected)
        async def revoke_token(request: RevokeTokenRequest) -> dict[str, bool]:
            if self.token_manager.revoke_token(request.token_id):
                return {"success": True}
            raise HTTPException(status_code=404, detail="Token not found")

        @self.app.post("/api/transcribe", dependencies=protected)
        async def transcribe_audio(audio: Annotated[UploadFile, File()]) -> TranscriptionResult:
            content = await audio.read()
            if not content:
                raise HTTPException(status_code=400, detail="Empty audio file")

            started = time.monotonic()
            success, text, info = await self.transcription_server.transcribe_audio_from_wav(content, "dashboard")
            if not success:
                raise HTTPException(status_code=503, detail=info.get("error", "Transcription failed"))

            return TranscriptionResult(
                text=text,
                confidence=float(info.get("confidence", 0.95)),
                processing_time=time.monotonic() - started,
            )

    @staticmethod
    def _check_gpu_available() -> bool:
        try:
            import ctranslate2

            return ctranslate2.get_cuda_device_count() > 0
        except (ImportError, RuntimeError):
            return False


__all__ = ["DashboardAPI"]
