#!/usr/bin/env python3
"""
App hooks for STT CLI - provides implementation for all STT commands
This file connects the generated CLI to the actual STT functionality
"""

import asyncio
import sys
from typing import Optional

# Import STT functionality
# Note: Import modes only when needed to avoid side effects


def on_listen(
    device: Optional[str],
    language: Optional[str],
    model: str,
    hold_to_talk: Optional[str],
    json: bool,
    debug: bool,
    config: Optional[str],
    no_formatting: bool,
    sample_rate: int,
    **kwargs,
) -> int:
    """Handle the listen command - record once and transcribe"""
    try:
        # Create args object for mode initialization
        class Args:
            def __init__(self):
                self.model = model
                self.language = language if language else "en"
                self.device = device
                self.sample_rate = sample_rate
                self.format = "json" if json else "text"
                self.debug = debug
                self.config_path = config
                self.disable_formatting = no_formatting

        args = Args()
        
        # Use hold-to-talk mode if key specified, otherwise listen-once
        if hold_to_talk:
            from stt.modes.hold_to_talk import HoldToTalkMode
            args.hold_key = hold_to_talk
            mode = HoldToTalkMode(args)
        else:
            from stt.modes.listen_once import ListenOnceMode
            mode = ListenOnceMode(args)
        
        # Run the mode
        asyncio.run(mode.run())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def on_live(
    device: Optional[str],
    language: Optional[str],
    model: str,
    tap_to_talk: Optional[str],
    json: bool,
    debug: bool,
    config: Optional[str],
    no_formatting: bool,
    sample_rate: int,
    **kwargs,
) -> int:
    """Handle the live command - continuous conversation mode"""
    try:
        # Create args object for mode initialization
        class Args:
            def __init__(self):
                self.model = model
                self.language = language if language else "en"
                self.device = device
                self.sample_rate = sample_rate
                self.format = "json" if json else "text"
                self.debug = debug
                self.config_path = config
                self.disable_formatting = no_formatting

        args = Args()
        
        # Use tap-to-talk mode if key specified, otherwise conversation mode
        if tap_to_talk:
            from stt.modes.tap_to_talk import TapToTalkMode
            args.tap_key = tap_to_talk
            mode = TapToTalkMode(args)
        else:
            from stt.modes.conversation import ConversationMode
            mode = ConversationMode(args)
        
        # Run the mode
        asyncio.run(mode.run())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def on_serve(
    port: int,
    host: str,
    debug: bool,
    config: Optional[str],
    **kwargs,
) -> int:
    """Handle the serve command - start transcription server"""
    try:
        import os
        import asyncio
        
        # Set management token to bypass server restriction
        os.environ["MATILDA_MANAGEMENT_TOKEN"] = "managed-by-matilda-system"
        
        # Import and start server
        from stt.transcription.server import MatildaWebSocketServer
        
        print(f"🌐 Starting STT WebSocket server on {host}:{port}")
        if debug:
            print("Debug mode enabled")
        
        server = MatildaWebSocketServer()
        asyncio.run(server.start_server(host=host, port=port))
        return 0
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        return 0
    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        return 1


def on_status(json: bool = False, **kwargs) -> int:
    """Show comprehensive system status and health information"""
    import sys
    import os
    import json as json_lib
    import time
    import platform
    import shutil
    import psutil
    from pathlib import Path
    from datetime import datetime
    
    try:
        # Add parent directory to path for imports
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        status_data = {}
        
        # System Information
        status_data["system"] = {
            "platform": platform.system(),
            "platform_version": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Memory Information
        try:
            memory = psutil.virtual_memory()
            status_data["memory"] = {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent_used": memory.percent,
                "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 90 else "critical"
            }
        except Exception as e:
            status_data["memory"] = {"error": str(e), "status": "error"}
        
        # CUDA and GPU Information
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            gpu_info = {
                "cuda_available": cuda_available,
                "pytorch_version": torch.__version__
            }
            if cuda_available:
                gpu_info["device_count"] = torch.cuda.device_count()
                gpu_info["device_name"] = torch.cuda.get_device_name(0)
                gpu_info["memory_allocated_mb"] = round(torch.cuda.memory_allocated(0) / (1024**2), 2)
                gpu_info["memory_reserved_mb"] = round(torch.cuda.memory_reserved(0) / (1024**2), 2)
                gpu_info["memory_total_mb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**2), 2)
            
            # Check CTranslate2 CUDA support
            try:
                import ctranslate2
                cuda_device_count = ctranslate2.get_cuda_device_count()
                gpu_info["ctranslate2_cuda_devices"] = cuda_device_count
                gpu_info["ctranslate2_version"] = ctranslate2.__version__
            except Exception as e:
                gpu_info["ctranslate2_error"] = str(e)
            
            status_data["gpu"] = gpu_info
        except ImportError:
            status_data["gpu"] = {"error": "PyTorch not installed", "cuda_available": False}
        except Exception as e:
            status_data["gpu"] = {"error": str(e), "cuda_available": False}
        
        # Audio System Information
        audio_info = {}
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            device_count = p.get_device_count()
            audio_info["total_devices"] = device_count
            audio_info["pyaudio_available"] = True
            
            # Get detailed device information
            devices = []
            for i in range(device_count):
                try:
                    info = p.get_device_info_by_index(i)
                    if info["maxInputChannels"] > 0:  # Only input devices
                        devices.append({
                            "index": i,
                            "name": info["name"],
                            "channels": info["maxInputChannels"],
                            "sample_rate": info["defaultSampleRate"]
                        })
                except:
                    continue
            
            audio_info["input_devices"] = devices
            audio_info["input_device_count"] = len(devices)
            audio_info["status"] = "healthy" if len(devices) > 0 else "warning"
            p.terminate()
        except ImportError:
            audio_info = {
                "error": "PyAudio not installed",
                "pyaudio_available": False,
                "status": "error",
                "fix_command": "./setup.sh upgrade"
            }
        except Exception as e:
            audio_info = {"error": str(e), "pyaudio_available": False, "status": "error"}
        
        status_data["audio"] = audio_info
        
        # Configuration Information
        try:
            from stt.core.config import get_config
            config = get_config()
            
            config_info = {
                "whisper_model": config.whisper_model,
                "whisper_device": config.whisper_device_auto,
                "whisper_compute_type": config.whisper_compute_type_auto,
                "websocket_port": config.websocket_port,
                "websocket_host": config.websocket_host,
                "ssl_enabled": config.ssl_enabled,
                "audio_sample_rate": config.audio_sample_rate,
                "audio_channels": config.audio_channels,
                "config_file": config.config_file
            }
            
            # Validate critical configuration
            validation_errors = []
            if not os.path.exists(config.config_file):
                validation_errors.append("Config file not found")
            
            try:
                # Test CUDA configuration match
                cuda_available = status_data["gpu"].get("cuda_available", False)
                if config.whisper_device_auto == "cuda" and not cuda_available:
                    validation_errors.append("CUDA device configured but not available")
            except:
                pass
            
            config_info["validation_errors"] = validation_errors
            config_info["status"] = "healthy" if not validation_errors else "warning"
            
            status_data["config"] = config_info
        except Exception as e:
            status_data["config"] = {"error": str(e), "status": "error"}
        
        # Model Performance and Loading Stats
        model_info = {"status": "not_loaded"}
        try:
            # Check if we can load a model (performance test)
            from faster_whisper import WhisperModel
            start_time = time.time()
            
            # Get model info from config
            config = get_config()
            model_name = config.whisper_model
            device = config.whisper_device_auto
            compute_type = config.whisper_compute_type_auto
            
            model_info["model_name"] = model_name
            model_info["device"] = device
            model_info["compute_type"] = compute_type
            
            # Try to load model for performance test
            try:
                model = WhisperModel(model_name, device=device, compute_type=compute_type)
                load_time = time.time() - start_time
                model_info["load_time_seconds"] = round(load_time, 2)
                model_info["status"] = "loaded_successfully"
                
                # Get model size estimate
                model_info["parameters"] = _get_model_parameters(model_name)
                
                del model  # Free memory
            except Exception as e:
                model_info["load_error"] = str(e)
                model_info["status"] = "load_failed"
                
        except Exception as e:
            model_info["error"] = str(e)
            model_info["status"] = "error"
        
        status_data["model"] = model_info
        
        # WebSocket Server Health
        server_info = {"status": "not_running"}
        try:
            import socket
            config = get_config()
            host = config.websocket_host
            port = config.websocket_port
            
            # Test if server is running
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                server_info["status"] = "running"
                server_info["host"] = host
                server_info["port"] = port
                server_info["ssl_enabled"] = config.ssl_enabled
            else:
                server_info["status"] = "not_running"
                server_info["host"] = host
                server_info["port"] = port
                
        except Exception as e:
            server_info["error"] = str(e)
            server_info["status"] = "error"
        
        status_data["websocket_server"] = server_info
        
        # Disk Space Information
        disk_info = {}
        try:
            # Check space for project directory
            project_path = Path(__file__).parent.parent.parent
            project_usage = shutil.disk_usage(project_path)
            
            # Check logs directory
            logs_path = project_path / "logs"
            if logs_path.exists():
                log_files = list(logs_path.glob("*.txt"))
                total_log_size = sum(f.stat().st_size for f in log_files if f.exists())
                log_info = {
                    "path": str(logs_path),
                    "file_count": len(log_files),
                    "total_size_mb": round(total_log_size / (1024**2), 2)
                }
            else:
                log_info = {"path": str(logs_path), "exists": False}
            
            disk_info = {
                "project_directory": {
                    "path": str(project_path),
                    "total_gb": round(project_usage.total / (1024**3), 2),
                    "free_gb": round(project_usage.free / (1024**3), 2),
                    "used_gb": round((project_usage.total - project_usage.free) / (1024**3), 2),
                    "percent_free": round((project_usage.free / project_usage.total) * 100, 2)
                },
                "logs": log_info,
                "status": "healthy" if project_usage.free > 1024**3 else "warning"  # Warn if < 1GB free
            }
        except Exception as e:
            disk_info = {"error": str(e), "status": "error"}
        
        status_data["disk"] = disk_info
        
        # Recent Performance Stats from Logs
        performance_info = {"status": "no_data"}
        try:
            logs_path = Path(__file__).parent.parent.parent / "logs"
            if logs_path.exists():
                recent_logs = []
                for log_file in logs_path.glob("*.txt"):
                    if log_file.exists():
                        stat = log_file.stat()
                        recent_logs.append({
                            "name": log_file.name,
                            "size_kb": round(stat.st_size / 1024, 2),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                
                recent_logs.sort(key=lambda x: x["modified"], reverse=True)
                performance_info = {
                    "recent_logs": recent_logs[:5],  # Top 5 recent logs
                    "total_log_files": len(recent_logs),
                    "status": "available" if recent_logs else "no_logs"
                }
        except Exception as e:
            performance_info = {"error": str(e), "status": "error"}
        
        status_data["performance"] = performance_info
        
        # Overall System Health Score
        health_score = _calculate_health_score(status_data)
        status_data["overall"] = {
            "health_score": health_score,
            "status": "healthy" if health_score >= 80 else "warning" if health_score >= 60 else "critical",
            "timestamp": datetime.now().isoformat()
        }
        
        # Output results
        if json:
            print(json_lib.dumps(status_data, indent=2))
        else:
            _print_status_formatted(status_data)
        
        return 0
    except Exception as e:
        if json:
            print(json_lib.dumps({"error": str(e), "status": "critical"}))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        return 1


def _get_model_parameters(model_name: str) -> str:
    """Get estimated parameter count for Whisper model"""
    model_params = {
        "tiny": "39M",
        "base": "74M", 
        "small": "244M",
        "medium": "769M",
        "large": "1550M",
        "large-v2": "1550M",
        "large-v3": "1550M",
        "large-v3-turbo": "809M"
    }
    return model_params.get(model_name, "unknown")


def _calculate_health_score(status_data: dict) -> int:
    """Calculate overall system health score (0-100)"""
    score = 100
    
    # Memory health
    if status_data.get("memory", {}).get("status") == "critical":
        score -= 30
    elif status_data.get("memory", {}).get("status") == "warning":
        score -= 15
    elif status_data.get("memory", {}).get("status") == "error":
        score -= 20
    
    # GPU health
    if not status_data.get("gpu", {}).get("cuda_available", True):
        score -= 10  # Not critical if no GPU
    
    # Audio health
    audio_status = status_data.get("audio", {}).get("status")
    if audio_status == "error":
        score -= 25
    elif audio_status == "warning":
        score -= 15
    
    # Config health
    config_status = status_data.get("config", {}).get("status")
    if config_status == "error":
        score -= 30
    elif config_status == "warning":
        score -= 10
    
    # Model health
    model_status = status_data.get("model", {}).get("status")
    if model_status == "error":
        score -= 25
    elif model_status == "load_failed":
        score -= 20
    
    # Disk health
    disk_status = status_data.get("disk", {}).get("status")
    if disk_status == "error":
        score -= 15
    elif disk_status == "warning":
        score -= 10
    
    return max(0, score)


def _print_status_formatted(status_data: dict) -> None:
    """Print status data in a formatted, human-readable way"""
    
    # Header
    overall = status_data.get("overall", {})
    health_score = overall.get("health_score", 0)
    health_status = overall.get("status", "unknown")
    
    status_emoji = {
        "healthy": "✅",
        "warning": "⚠️",
        "critical": "❌",
        "unknown": "❓"
    }
    
    print(f"\n🎤 STT System Status - {status_emoji.get(health_status, '❓')} {health_status.upper()} ({health_score}/100)")
    print("=" * 70)
    
    # System Information
    system = status_data.get("system", {})
    print(f"\n📋 System Information")
    print(f"   Platform: {system.get('platform', 'unknown')} {system.get('architecture', '')}")
    print(f"   Python: {system.get('python_version', 'unknown')}")
    print(f"   Timestamp: {system.get('timestamp', 'unknown')}")
    
    # Memory Information
    memory = status_data.get("memory", {})
    if "error" not in memory:
        status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "❌"}.get(memory.get("status"), "❓")
        print(f"\n💾 Memory Usage {status_icon}")
        print(f"   Total: {memory.get('total_gb', 0):.1f} GB")
        print(f"   Used: {memory.get('used_gb', 0):.1f} GB ({memory.get('percent_used', 0):.1f}%)")
        print(f"   Available: {memory.get('available_gb', 0):.1f} GB")
    else:
        print(f"\n💾 Memory Usage ❌ Error: {memory.get('error')}")
    
    # GPU Information  
    gpu = status_data.get("gpu", {})
    if gpu.get("cuda_available"):
        print(f"\n🎮 GPU/CUDA ✅")
        print(f"   Device: {gpu.get('device_name', 'unknown')}")
        print(f"   Memory: {gpu.get('memory_allocated_mb', 0):.1f}MB / {gpu.get('memory_total_mb', 0):.1f}MB")
        print(f"   PyTorch: {gpu.get('pytorch_version', 'unknown')}")
        if gpu.get("ctranslate2_cuda_devices"):
            print(f"   CTranslate2: {gpu.get('ctranslate2_cuda_devices')} CUDA devices")
    else:
        print(f"\n🎮 GPU/CUDA ⚠️  CPU mode only")
        if "error" in gpu:
            print(f"   Error: {gpu['error']}")
    
    # Audio Information
    audio = status_data.get("audio", {})
    status_icon = {"healthy": "✅", "warning": "⚠️", "error": "❌"}.get(audio.get("status"), "❓") 
    print(f"\n🎧 Audio System {status_icon}")
    if audio.get("pyaudio_available"):
        input_count = audio.get("input_device_count", 0)
        print(f"   Input devices: {input_count}")
        if input_count > 0:
            for device in audio.get("input_devices", [])[:3]:  # Show top 3
                print(f"     • {device['name']} ({device['channels']} ch, {device['sample_rate']:.0f} Hz)")
    else:
        print(f"   Error: {audio.get('error', 'Unknown error')}")
        if audio.get("fix_command"):
            print(f"   Fix: {audio['fix_command']}")
    
    # Model Information
    model = status_data.get("model", {})
    status_icon = {"loaded_successfully": "✅", "load_failed": "❌", "error": "❌", "not_loaded": "⏸️"}.get(model.get("status"), "❓")
    print(f"\n🤖 Whisper Model {status_icon}")
    if model.get("model_name"):
        print(f"   Model: {model['model_name']} ({model.get('parameters', 'unknown')} parameters)")
        print(f"   Device: {model.get('device', 'unknown')}")
        print(f"   Compute Type: {model.get('compute_type', 'unknown')}")
        if model.get("load_time_seconds"):
            print(f"   Load Time: {model['load_time_seconds']}s")
        if model.get("load_error"):
            print(f"   Error: {model['load_error']}")
    
    # WebSocket Server
    server = status_data.get("websocket_server", {})
    status_icon = {"running": "✅", "not_running": "⏸️", "error": "❌"}.get(server.get("status"), "❓")
    print(f"\n🌐 WebSocket Server {status_icon}")
    if server.get("host") and server.get("port"):
        protocol = "wss" if server.get("ssl_enabled") else "ws"
        print(f"   Address: {protocol}://{server['host']}:{server['port']}")
        print(f"   Status: {server.get('status', 'unknown')}")
        if server.get("ssl_enabled"):
            print(f"   SSL: Enabled")
    
    # Configuration
    config = status_data.get("config", {})
    status_icon = {"healthy": "✅", "warning": "⚠️", "error": "❌"}.get(config.get("status"), "❓")
    print(f"\n⚙️  Configuration {status_icon}")
    if config.get("config_file"):
        print(f"   File: {config['config_file']}")
    validation_errors = config.get("validation_errors", [])
    if validation_errors:
        print(f"   Issues:")
        for error in validation_errors:
            print(f"     • {error}")
    
    # Disk Space
    disk = status_data.get("disk", {})
    status_icon = {"healthy": "✅", "warning": "⚠️", "error": "❌"}.get(disk.get("status"), "❓")
    print(f"\n💿 Disk Space {status_icon}")
    if disk.get("project_directory"):
        proj = disk["project_directory"]
        print(f"   Project: {proj.get('free_gb', 0):.1f} GB free ({proj.get('percent_free', 0):.1f}%)")
    if disk.get("logs"):
        logs = disk["logs"]
        if logs.get("file_count"):
            print(f"   Logs: {logs['file_count']} files, {logs.get('total_size_mb', 0):.1f} MB")
    
    # Performance Stats
    perf = status_data.get("performance", {})
    if perf.get("status") == "available":
        print(f"\n📊 Recent Activity ✅")
        print(f"   Log files: {perf.get('total_log_files', 0)}")
        recent = perf.get("recent_logs", [])
        if recent:
            latest = recent[0]
            print(f"   Latest: {latest['name']} ({latest['size_kb']} KB)")
    else:
        print(f"\n📊 Recent Activity ⏸️  No recent logs")
    
    print()  # Final newline


def on_model_download(model_name: str, force: bool = False, device: str = "auto", **kwargs) -> int:
    """Download a Whisper model"""
    try:
        import os
        from pathlib import Path
        
        print(f"🔽 Downloading Whisper model: {model_name}")
        
        # Import faster-whisper to download the model
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            print("❌ Error: faster-whisper not installed")
            print("   To fix: pip install faster-whisper")
            return 1
        
        # Determine compute type based on device
        if device == "auto":
            try:
                import torch
                compute_type = "float16" if torch.cuda.is_available() else "int8"
                device_type = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                compute_type = "int8"
                device_type = "cpu"
        elif device == "cuda":
            compute_type = "float16"
            device_type = "cuda"
        else:
            compute_type = "int8"
            device_type = "cpu"
        
        print(f"📱 Using device: {device_type} with compute type: {compute_type}")
        
        # Download the model (this will cache it automatically)
        try:
            model = WhisperModel(model_name, device=device_type, compute_type=compute_type)
            print(f"✅ Successfully downloaded and cached model: {model_name}")
            print(f"📁 Model cached in: ~/.cache/huggingface/transformers/")
            return 0
        except Exception as e:
            print(f"❌ Error downloading model: {e}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def on_model_list(downloaded_only: bool = False, json: bool = False, **kwargs) -> int:
    """List available and downloaded models"""
    try:
        import os
        import json as j
        from pathlib import Path
        
        # Model information
        models_info = {
            "tiny": {"params": "39M", "vram": "~1GB", "desc": "Fastest, lowest accuracy"},
            "base": {"params": "74M", "vram": "~1GB", "desc": "Good balance (default)"},
            "small": {"params": "244M", "vram": "~2GB", "desc": "Better accuracy"},
            "medium": {"params": "769M", "vram": "~5GB", "desc": "High accuracy"},
            "large": {"params": "1550M", "vram": "~10GB", "desc": "Best accuracy, slowest"},
        }
        
        # Check which models are downloaded by looking in cache
        cache_dir = Path.home() / ".cache" / "huggingface" / "transformers"
        downloaded_models = []
        
        if cache_dir.exists():
            for model_name in models_info.keys():
                # Look for model files in cache (simplified check)
                model_files = list(cache_dir.glob(f"*{model_name}*"))
                if model_files:
                    downloaded_models.append(model_name)
        
        if json:
            result = {}
            for model_name, info in models_info.items():
                if not downloaded_only or model_name in downloaded_models:
                    result[model_name] = {
                        **info,
                        "downloaded": model_name in downloaded_models
                    }
            print(j.dumps(result, indent=2))
        else:
            if downloaded_only:
                print("📦 Downloaded Whisper Models")
            else:
                print("📦 Available Whisper Models")
            print("=" * 60)
            
            print(f"{'Model':<10} {'Parameters':<12} {'VRAM':<8} {'Status':<12} {'Description'}")
            print("-" * 60)
            
            for model_name, info in models_info.items():
                if downloaded_only and model_name not in downloaded_models:
                    continue
                    
                status = "✅ Downloaded" if model_name in downloaded_models else "⬇️  Available"
                print(f"{model_name:<10} {info['params']:<12} {info['vram']:<8} {status:<12} {info['desc']}")
            
            if not downloaded_only:
                print(f"\nDownloaded: {len(downloaded_models)}/{len(models_info)} models")
                print("To download a model: stt model download <model_name>")
        
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def on_model_info(model_name: str, json: bool = False, **kwargs) -> int:
    """Show detailed model information"""
    try:
        import json as j
        from pathlib import Path
        
        models_detailed = {
            "tiny": {
                "params": "39M", "vram": "~1GB", "desc": "Fastest, lowest accuracy",
                "languages": "99", "speed": "~32x realtime", "wer": "~12%",
                "use_case": "Real-time applications, low-resource devices"
            },
            "base": {
                "params": "74M", "vram": "~1GB", "desc": "Good balance (default)",
                "languages": "99", "speed": "~16x realtime", "wer": "~9%",
                "use_case": "General purpose, good accuracy/speed balance"
            },
            "small": {
                "params": "244M", "vram": "~2GB", "desc": "Better accuracy",
                "languages": "99", "speed": "~6x realtime", "wer": "~6%",
                "use_case": "Higher accuracy applications"
            },
            "medium": {
                "params": "769M", "vram": "~5GB", "desc": "High accuracy",
                "languages": "99", "speed": "~2x realtime", "wer": "~5%",
                "use_case": "Professional transcription, high accuracy needed"
            },
            "large": {
                "params": "1550M", "vram": "~10GB", "desc": "Best accuracy, slowest",
                "languages": "99", "speed": "~1x realtime", "wer": "~3%",
                "use_case": "Maximum accuracy, batch processing"
            }
        }
        
        if model_name not in models_detailed:
            print(f"❌ Unknown model: {model_name}")
            return 1
        
        info = models_detailed[model_name]
        
        # Check if downloaded
        cache_dir = Path.home() / ".cache" / "huggingface" / "transformers"
        is_downloaded = False
        if cache_dir.exists():
            model_files = list(cache_dir.glob(f"*{model_name}*"))
            is_downloaded = bool(model_files)
        
        if json:
            result = {**info, "downloaded": is_downloaded}
            print(j.dumps(result, indent=2))
        else:
            print(f"🧠 Whisper Model: {model_name}")
            print("=" * 40)
            print(f"Parameters: {info['params']}")
            print(f"VRAM Usage: {info['vram']}")
            print(f"Languages: {info['languages']}")
            print(f"Speed: {info['speed']}")
            print(f"Word Error Rate: {info['wer']}")
            print(f"Status: {'✅ Downloaded' if is_downloaded else '⬇️  Not downloaded'}")
            print(f"Use Case: {info['use_case']}")
            print(f"Description: {info['desc']}")
            
            if not is_downloaded:
                print(f"\nTo download: stt model download {model_name}")
        
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def on_model_remove(model_name: str, force: bool = False, **kwargs) -> int:
    """Remove downloaded model"""
    try:
        import shutil
        from pathlib import Path
        
        cache_dir = Path.home() / ".cache" / "huggingface" / "transformers"
        
        if not cache_dir.exists():
            print(f"❌ No model cache found")
            return 1
        
        # Find model files
        model_files = list(cache_dir.glob(f"*{model_name}*"))
        
        if not model_files:
            print(f"❌ Model '{model_name}' not found in cache")
            return 1
        
        if not force:
            print(f"⚠️  This will remove model '{model_name}' from cache")
            print(f"📁 Files to be removed: {len(model_files)}")
            response = input("Continue? (y/N): ").strip().lower()
            if response != 'y':
                print("❌ Cancelled")
                return 0
        
        # Remove model files
        removed_count = 0
        for file_path in model_files:
            try:
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
                removed_count += 1
            except Exception as e:
                print(f"⚠️  Warning: Could not remove {file_path}: {e}")
        
        print(f"✅ Removed {removed_count} files for model '{model_name}'")
        print("💾 You can re-download the model with: stt model download " + model_name)
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def on_model_benchmark(model_name: str, duration: int = 10, device: str = "auto", json: bool = False, **kwargs) -> int:
    """Test model performance"""
    try:
        import time
        import json as j
        import tempfile
        import os
        from pathlib import Path
        
        print(f"⚡ Benchmarking Whisper model: {model_name}")
        print(f"⏱️  Test duration: {duration} seconds")
        
        # Import faster-whisper
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            print("❌ Error: faster-whisper not installed")
            return 1
        
        # Determine device settings
        if device == "auto":
            try:
                import torch
                compute_type = "float16" if torch.cuda.is_available() else "int8"
                device_type = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                compute_type = "int8"
                device_type = "cpu"
        elif device == "cuda":
            compute_type = "float16"
            device_type = "cuda"
        else:
            compute_type = "int8"
            device_type = "cpu"
        
        print(f"📱 Using device: {device_type} with compute type: {compute_type}")
        
        # Load model and measure loading time
        print("📥 Loading model...")
        load_start = time.time()
        try:
            model = WhisperModel(model_name, device=device_type, compute_type=compute_type)
            load_time = time.time() - load_start
            print(f"✅ Model loaded in {load_time:.2f}s")
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return 1
        
        # Create a test audio file (silence for benchmarking)
        print("🎵 Creating test audio...")
        try:
            import numpy as np
            import wave
            
            # Generate silent audio for testing
            sample_rate = 16000
            test_audio = np.zeros(sample_rate * duration, dtype=np.float32)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                temp_path = tmp_file.name
                
                # Write wav file
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    # Convert float32 to int16
                    audio_int16 = (test_audio * 32767).astype(np.int16)
                    wav_file.writeframes(audio_int16.tobytes())
            
            # Benchmark transcription
            print("🔄 Running transcription benchmark...")
            transcribe_start = time.time()
            segments, info = model.transcribe(temp_path)
            
            # Process all segments
            segment_count = 0
            for segment in segments:
                segment_count += 1
            
            transcribe_time = time.time() - transcribe_start
            
            # Calculate metrics
            speed_ratio = duration / transcribe_time if transcribe_time > 0 else float('inf')
            
            # Cleanup
            os.unlink(temp_path)
            
            # Results
            results = {
                "model": model_name,
                "device": device_type,
                "compute_type": compute_type,
                "test_duration": duration,
                "load_time": round(load_time, 3),
                "transcribe_time": round(transcribe_time, 3),
                "speed_ratio": round(speed_ratio, 2),
                "segments_processed": segment_count,
                "detected_language": info.language if hasattr(info, 'language') else "unknown"
            }
            
            if json:
                print(j.dumps(results, indent=2))
            else:
                print("\n📊 Benchmark Results")
                print("=" * 30)
                print(f"Model: {results['model']}")
                print(f"Device: {results['device']} ({results['compute_type']})")
                print(f"Loading Time: {results['load_time']}s")
                print(f"Transcription Time: {results['transcribe_time']}s")
                print(f"Speed Ratio: {results['speed_ratio']}x realtime")
                print(f"Segments: {results['segments_processed']}")
                
                if results['speed_ratio'] > 1:
                    print(f"✅ Model is {results['speed_ratio']}x faster than realtime")
                else:
                    print(f"⚠️  Model is slower than realtime ({results['speed_ratio']}x)")
            
            return 0
            
        except ImportError as e:
            print(f"❌ Missing dependencies for benchmarking: {e}")
            print("   Install with: pip install numpy")
            return 1
        except Exception as e:
            print(f"❌ Benchmark error: {e}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def on_config_show(json: bool = False, **kwargs) -> int:
    """Show all configuration settings"""
    try:
        from stt.core.config import Config
        config = Config()
        
        if json:
            import json as j
            # Filter out secrets
            safe_config = {k: v for k, v in config.config.items() if k not in ['jwt_secret']}
            print(j.dumps(safe_config, indent=2))
        else:
            print("🔧 Current Configuration")
            print("=" * 40)
            for k, v in config.config.items():
                if k not in ['jwt_secret']:  # Don't show secrets
                    print(f"  {k}: {v}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def on_config_get(key: str, **kwargs) -> int:
    """Get specific configuration value"""
    try:
        from stt.core.config import Config
        config = Config()
        value = config.get(key)
        print(f"{key}: {value}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def on_config_set(key: str, value: str, **kwargs) -> int:
    """Set configuration value"""
    try:
        from stt.core.config import Config
        config = Config()
        config.set(key, value)
        config.save()
        print(f"✅ Set {key} = {value}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1