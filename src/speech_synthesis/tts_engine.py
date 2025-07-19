"""Basic TTS engine for Phase 1 - uses system TTS or generates marked text."""

import subprocess
import os
import time
from typing import List
from document_parsing.base_parser import SemanticElement, SemanticType


class SimpleTTSEngine:
    """Simple TTS engine for Phase 1 proof of concept."""
    
    def __init__(self):
        self.available_engines = self._detect_available_engines()
        
    def _detect_available_engines(self) -> List[str]:
        """Detect available TTS engines on the system."""
        engines = []
        
        # Check for espeak
        try:
            subprocess.run(['espeak', '--version'], capture_output=True, check=True)
            engines.append('espeak')
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        # Check for festival
        try:
            subprocess.run(['festival', '--version'], capture_output=True, check=True)
            engines.append('festival')
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        # Check for say (macOS)
        try:
            subprocess.run(['say', '-v', '?'], capture_output=True, check=True)
            engines.append('say')
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        return engines
    
    def speak(self, text: str, emotion: str = "normal") -> bool:
        """Convert text to speech with basic emotion support.
        
        Args:
            text: Text to speak
            emotion: Emotion hint (normal, excited, soft, monotone)
            
        Returns:
            True if speech was generated successfully
        """
        if not self.available_engines:
            print(f"[TTS] No TTS engine available. Would speak: {text}")
            return False
            
        # Use the first available engine
        engine = self.available_engines[0]
        
        try:
            if engine == 'espeak':
                return self._speak_espeak(text, emotion)
            elif engine == 'festival':
                return self._speak_festival(text, emotion)
            elif engine == 'say':
                return self._speak_say(text, emotion)
        except Exception as e:
            print(f"[TTS] Error with {engine}: {e}")
            print(f"[TTS] Fallback - would speak: {text}")
            return False
            
        return False
    
    def _speak_espeak(self, text: str, emotion: str) -> bool:
        """Use espeak for TTS."""
        cmd = ['espeak']
        
        # Adjust parameters based on emotion
        if emotion == "excited":
            cmd.extend(['-p', '60', '-s', '180'])  # Higher pitch, faster
        elif emotion == "soft":
            cmd.extend(['-p', '30', '-s', '120'])  # Lower pitch, slower
        elif emotion == "monotone":
            cmd.extend(['-p', '40', '-s', '150'])  # Flat pitch, medium speed
        else:
            cmd.extend(['-p', '50', '-s', '160'])  # Normal
            
        cmd.append(text)
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def _speak_festival(self, text: str, emotion: str) -> bool:
        """Use festival for TTS."""
        # Festival doesn't have simple emotion control, just speak normally
        result = subprocess.run(['festival', '--tts'], input=text, text=True, capture_output=True)
        return result.returncode == 0
    
    def _speak_say(self, text: str, emotion: str) -> bool:
        """Use macOS say command for TTS."""
        cmd = ['say']
        
        # Adjust voice based on emotion (if available)
        if emotion == "excited":
            cmd.extend(['-v', 'Samantha', '-r', '200'])
        elif emotion == "soft":
            cmd.extend(['-v', 'Whisper', '-r', '120'])
        elif emotion == "monotone":
            cmd.extend(['-v', 'Ralph', '-r', '150'])
        else:
            cmd.extend(['-r', '160'])
            
        cmd.append(text)
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def speak_with_emotion(self, text: str, emotion: str, timing: float = 0) -> bool:
        """Speak text with specific emotion and timing.
        
        Args:
            text: Text to speak
            emotion: Emotion type ("excited", "soft", "monotone", "normal")
            timing: Pause duration in seconds after speaking
            
        Returns:
            True if speech was generated successfully
        """
        if not self.available_engines:
            print(f"[TTS] No TTS engine available. Would speak with {emotion}: {text}")
            if timing > 0:
                print(f"[TTS] Would pause for {timing}s")
            return False
            
        # Use the first available engine
        engine = self.available_engines[0]
        
        try:
            success = False
            if engine == 'espeak':
                success = self._speak_espeak(text, emotion)
            elif engine == 'festival':
                success = self._speak_festival(text, emotion)
            elif engine == 'say':
                success = self._speak_say(text, emotion)
                
            # Add timing pause if specified
            if success and timing > 0:
                time.sleep(timing)
                
            return success
        except Exception as e:
            print(f"[TTS] Error with {engine}: {e}")
            print(f"[TTS] Fallback - would speak with {emotion}: {text}")
            if timing > 0:
                print(f"[TTS] Would pause for {timing}s")
            return False
    
    def speak_elements(self, elements: List[SemanticElement]) -> bool:
        """Speak a list of semantic elements with appropriate emotion."""
        success = True
        
        for element in elements:
            emotion = self._get_emotion_for_element(element)
            
            # Add pauses for structure
            if element.type == SemanticType.HEADING:
                self.speak("", "normal")  # Brief pause before headings
                
            if not self.speak(element.content, emotion):
                success = False
                
            # Add pauses after headings
            if element.type == SemanticType.HEADING:
                self.speak("", "normal")  # Brief pause after headings
                
        return success
    
    def _get_emotion_for_element(self, element: SemanticElement) -> str:
        """Map semantic element type to emotion."""
        emotion_map = {
            SemanticType.HEADING: "excited",
            SemanticType.BOLD: "excited", 
            SemanticType.ITALIC: "soft",
            SemanticType.CODE: "monotone",
            SemanticType.CODE_BLOCK: "monotone",
            SemanticType.LIST_ITEM: "normal",
            SemanticType.LINK: "normal",
            SemanticType.TEXT: "normal"
        }
        
        return emotion_map.get(element.type, "normal")