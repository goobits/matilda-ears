"""
Docker Server Launcher for STT Transcription Server
Launches both the dashboard web interface and WebSocket transcription server
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional
import uvicorn
from multiprocessing import Process
import time

# Add project root to path
sys.path.append('/app')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/server_launcher.log')
    ]
)

logger = logging.getLogger(__name__)

class DockerServerLauncher:
    """Manages both dashboard and WebSocket server processes"""
    
    def __init__(self):
        self.dashboard_process: Optional[Process] = None
        self.websocket_process: Optional[Process] = None
        self.running = False
        
        # Configuration from environment
        self.websocket_port = int(os.getenv("WEBSOCKET_PORT", "8769"))
        self.web_port = int(os.getenv("WEB_PORT", "8080"))
        self.host = os.getenv("WEBSOCKET_BIND_HOST", "0.0.0.0")
        self.verbose = os.getenv("VERBOSE", "false").lower() == "true"
        
        logger.info(f"Server launcher initialized")
        logger.info(f"Dashboard: http://{self.host}:{self.web_port}")
        logger.info(f"WebSocket: wss://{self.host}:{self.websocket_port}")
    
    def start_dashboard(self):
        """Start the FastAPI dashboard server"""
        try:
            logger.info(f"Starting dashboard server on port {self.web_port}")
            
            # Import the dashboard API
            from docker.src.api import app
            
            # Configure uvicorn
            log_level = "debug" if self.verbose else "info"
            
            uvicorn.run(
                app,
                host=self.host,
                port=self.web_port,
                log_level=log_level,
                access_log=True,
                loop="asyncio"
            )
            
        except Exception as e:
            logger.error(f"Dashboard server failed: {e}")
            raise
    
    def start_websocket_server(self):
        """Start the WebSocket transcription server"""
        try:
            logger.info(f"Starting WebSocket server on port {self.websocket_port}")
            
            # Import the WebSocket server
            from docker.src.websocket_server import get_websocket_server
            
            # Create and start server
            server = get_websocket_server()
            
            # Run the server
            asyncio.run(server.start_server())
            
        except Exception as e:
            logger.error(f"WebSocket server failed: {e}")
            raise
    
    def start_all_services(self):
        """Start both dashboard and WebSocket servers"""
        try:
            logger.info("Starting all STT Docker services...")
            
            # Create required directories
            os.makedirs("/app/logs", exist_ok=True)
            os.makedirs("/app/data", exist_ok=True)
            os.makedirs("/app/ssl", exist_ok=True)
            
            self.running = True
            
            # Start dashboard in separate process
            logger.info("Launching dashboard process...")
            self.dashboard_process = Process(
                target=self.start_dashboard,
                name="STT-Dashboard"
            )
            self.dashboard_process.start()
            
            # Give dashboard time to start
            time.sleep(2)
            
            # Start WebSocket server in separate process
            logger.info("Launching WebSocket process...")
            self.websocket_process = Process(
                target=self.start_websocket_server,
                name="STT-WebSocket"
            )
            self.websocket_process.start()
            
            # Monitor processes
            self.monitor_processes()
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.shutdown()
        except Exception as e:
            logger.error(f"Failed to start services: {e}")
            self.shutdown()
            raise
    
    def monitor_processes(self):
        """Monitor both processes and restart if needed"""
        logger.info("Monitoring services...")
        
        while self.running:
            try:
                # Check dashboard process
                if self.dashboard_process and not self.dashboard_process.is_alive():
                    logger.error("Dashboard process died, restarting...")
                    self.dashboard_process = Process(
                        target=self.start_dashboard,
                        name="STT-Dashboard"
                    )
                    self.dashboard_process.start()
                
                # Check WebSocket process
                if self.websocket_process and not self.websocket_process.is_alive():
                    logger.error("WebSocket process died, restarting...")
                    self.websocket_process = Process(
                        target=self.start_websocket_server,
                        name="STT-WebSocket"
                    )
                    self.websocket_process.start()
                
                # Sleep before next check
                time.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted")
                break
            except Exception as e:
                logger.error(f"Error in process monitoring: {e}")
                time.sleep(1)
    
    def shutdown(self):
        """Gracefully shutdown all services"""
        logger.info("Shutting down STT Docker services...")
        self.running = False
        
        # Terminate dashboard process
        if self.dashboard_process and self.dashboard_process.is_alive():
            logger.info("Stopping dashboard...")
            self.dashboard_process.terminate()
            self.dashboard_process.join(timeout=10)
            if self.dashboard_process.is_alive():
                logger.warning("Force killing dashboard process")
                self.dashboard_process.kill()
        
        # Terminate WebSocket process
        if self.websocket_process and self.websocket_process.is_alive():
            logger.info("Stopping WebSocket server...")
            self.websocket_process.terminate()
            self.websocket_process.join(timeout=10)
            if self.websocket_process.is_alive():
                logger.warning("Force killing WebSocket process")
                self.websocket_process.kill()
        
        logger.info("All services stopped")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)


def main():
    """Main entry point"""
    try:
        # Check if we're in Docker mode
        if not os.getenv("STT_DOCKER_MODE"):
            logger.error("This launcher is designed for Docker mode only")
            logger.error("Set STT_DOCKER_MODE=1 environment variable")
            sys.exit(1)
        
        # Create launcher
        launcher = DockerServerLauncher()
        
        # Setup signal handlers
        launcher.setup_signal_handlers()
        
        # Start all services
        launcher.start_all_services()
        
    except Exception as e:
        logger.error(f"Server launcher failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()