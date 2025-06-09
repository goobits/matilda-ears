#!/home/miko/projects/stt-hotkey/venv/bin/python3
"""
Facebook Denoiser real-time audio processing pipeline
GPU-accelerated noise reduction for crystal-clear audio
"""
import torch
import numpy as np
import logging
import time
from typing import Optional
from denoiser import pretrained
from denoiser.demucs import DemucsStreamer

class FacebookDenoiserPipeline:
    """Real-time Facebook Denoiser for GPU-accelerated noise reduction"""
    
    def __init__(self, 
                 sample_rate: int = 44100,
                 device: str = "cuda",
                 model_name: str = "dns64"):
        
        self.sample_rate = sample_rate
        self.device = device
        self.model_name = model_name
        
        # Model and streaming components
        self.model = None
        self.streamer = None
        self.is_initialized = False
        
        # Performance tracking
        self.processing_times = []
        
        # Initialize the model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Facebook Denoiser model on GPU"""
        try:
            logging.info(f"Loading Facebook Denoiser {self.model_name} on {self.device}...")
            start_time = time.time()
            
            # Load pretrained model - correct API
            if self.model_name == "dns64":
                self.model = pretrained.dns64().to(self.device)
            elif self.model_name == "dns48":
                self.model = pretrained.dns48().to(self.device)
            elif self.model_name == "master64":
                self.model = pretrained.master64().to(self.device)
            else:
                # Default to dns64
                self.model = pretrained.dns64().to(self.device)
            self.model.eval()
            
            # Create streaming interface for real-time processing
            self.streamer = DemucsStreamer(
                self.model,
                dry=0.0,  # No dry signal - full denoising
                num_frames=1  # Process frame by frame for low latency
            )
            
            load_time = time.time() - start_time
            logging.info(f"Facebook Denoiser loaded in {load_time:.2f}s")
            
            self.is_initialized = True
            
        except Exception as e:
            logging.error(f"Failed to initialize Facebook Denoiser: {e}")
            self.is_initialized = False
            raise
    
    def process_chunk(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Process single audio chunk through denoiser"""
        if not self.is_initialized:
            logging.warning("Denoiser not initialized, returning original audio")
            return audio_chunk
        
        try:
            start_time = time.time()
            
            # Convert numpy to torch tensor
            audio_tensor = torch.from_numpy(audio_chunk).float()
            
            # Ensure correct shape for DemucsStreamer: (channels, samples)
            if audio_tensor.dim() == 1:
                audio_tensor = audio_tensor.unsqueeze(0)  # Add channel dimension: (1, samples)
            
            # Move to GPU
            audio_tensor = audio_tensor.to(self.device)
            
            # Process through denoiser
            with torch.no_grad():
                if self.streamer:
                    # Use streaming interface for low latency
                    denoised_tensor = self.streamer.feed(audio_tensor)
                else:
                    # Direct model inference
                    denoised_tensor = self.model(audio_tensor)
            
            # Convert back to numpy
            denoised_audio = denoised_tensor.squeeze().cpu().numpy()
            
            # Track performance
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            # Keep only last 100 measurements
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)
            
            return denoised_audio
            
        except Exception as e:
            logging.error(f"Denoiser processing error: {e}")
            return audio_chunk  # Return original on error
    
    def process_audio_stream(self, audio_data: np.ndarray, chunk_size: int = 1024) -> np.ndarray:
        """Process complete audio by chunks for streaming compatibility"""
        if not self.is_initialized:
            return audio_data
        
        denoised_chunks = []
        
        # Process in chunks
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            
            # Pad last chunk if necessary
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), mode='constant')
            
            denoised_chunk = self.process_chunk(chunk)
            denoised_chunks.append(denoised_chunk)
        
        # Concatenate all processed chunks
        result = np.concatenate(denoised_chunks)
        
        # Trim to original length
        return result[:len(audio_data)]
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        if not self.processing_times:
            return {}
        
        times = np.array(self.processing_times)
        return {
            'avg_processing_time': np.mean(times),
            'max_processing_time': np.max(times),
            'min_processing_time': np.min(times),
            'realtime_factor': 1024 / self.sample_rate / np.mean(times),  # How many times faster than realtime
            'gpu_utilization': f"{self.device}",
            'total_chunks_processed': len(self.processing_times)
        }
    
    def warmup(self, num_warmup: int = 5):
        """Warm up the model with dummy data for consistent performance"""
        logging.info("Warming up Facebook Denoiser...")
        
        dummy_chunk = np.random.randn(1024).astype(np.float32)
        
        for i in range(num_warmup):
            self.process_chunk(dummy_chunk)
        
        # Clear warmup times
        self.processing_times = []
        logging.info("Denoiser warmup completed")
    
    def cleanup(self):
        """Clean up GPU resources"""
        if self.model:
            del self.model
        if self.streamer:
            del self.streamer
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logging.info("Facebook Denoiser cleaned up")

# Singleton instance for global access
_denoiser_instance: Optional[FacebookDenoiserPipeline] = None

def get_denoiser(sample_rate: int = 44100, device: str = "cuda") -> FacebookDenoiserPipeline:
    """Get global denoiser instance (singleton pattern)"""
    global _denoiser_instance
    
    if _denoiser_instance is None:
        _denoiser_instance = FacebookDenoiserPipeline(sample_rate=sample_rate, device=device)
        _denoiser_instance.warmup()
    
    return _denoiser_instance

if __name__ == "__main__":
    # Test the denoiser pipeline
    logging.basicConfig(level=logging.INFO)
    
    # Create test noisy audio
    duration = 2.0  # 2 seconds
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Clean signal (sine wave)
    clean_signal = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440 Hz tone
    
    # Add noise
    noise = 0.3 * np.random.randn(len(clean_signal))
    noisy_signal = clean_signal + noise
    
    print(f"Testing Facebook Denoiser with {len(noisy_signal)} samples...")
    
    # Initialize denoiser
    denoiser = FacebookDenoiserPipeline(sample_rate=sample_rate)
    
    # Process the noisy audio
    start_time = time.time()
    denoised_signal = denoiser.process_audio_stream(noisy_signal.astype(np.float32))
    processing_time = time.time() - start_time
    
    print(f"Processing completed in {processing_time:.3f}s")
    print(f"Realtime factor: {duration/processing_time:.2f}x")
    
    # Show performance stats
    stats = denoiser.get_performance_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    denoiser.cleanup()