#!/usr/bin/env python3
"""Simple server utilities for STT - minimal implementation for auto-start functionality."""

import socket
import subprocess
import time
import os
import signal
from typing import Optional, Dict, Any


def check_server_port(port: int = 8769, host: str = "127.0.0.1") -> Dict[str, Any]:
    """Check if server is running on specified port.
    
    Args:
        port: Port to check
        host: Host to check
        
    Returns:
        Dictionary with status information
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return {
                "status": "running",
                "port": port,
                "host": host,
                "healthy": True
            }
        else:
            return {
                "status": "not_running",
                "port": port,
                "host": host,
                "healthy": False
            }
    except Exception as e:
        return {
            "status": "error",
            "port": port,
            "host": host,
            "healthy": False,
            "error": str(e)
        }


def start_server_simple(port: int = 8769, host: str = "0.0.0.0") -> Dict[str, Any]:
    """Start STT server in background using simple subprocess.
    
    Args:
        port: Port to start server on
        host: Host to bind to
        
    Returns:
        Dictionary with start result
    """
    try:
        # Check if already running
        status = check_server_port(port, "127.0.0.1")
        if status["healthy"]:
            return {
                "success": True,
                "message": "Server already running",
                "port": port,
                "pid": None
            }
        
        # Start server in background
        cmd = ["stt", "serve", "--port", str(port), "--host", host]
        
        # Use subprocess.Popen for background process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
        
        # Wait a bit for server to start
        time.sleep(2)
        
        # Check if it started successfully
        status = check_server_port(port, "127.0.0.1")
        if status["healthy"]:
            return {
                "success": True,
                "message": "Server started successfully",
                "port": port,
                "pid": process.pid
            }
        else:
            # Try to clean up if it failed
            try:
                os.kill(process.pid, signal.SIGTERM)
            except:
                pass
            return {
                "success": False,
                "message": "Server failed to start",
                "port": port,
                "pid": None
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to start server: {str(e)}",
            "port": port,
            "pid": None
        }


def is_server_running(port: int = 8769) -> bool:
    """Simple check if server is running.
    
    Args:
        port: Port to check
        
    Returns:
        True if server is running, False otherwise
    """
    status = check_server_port(port)
    return status.get("healthy", False)