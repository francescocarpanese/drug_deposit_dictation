"""Audio transcription using Whisper."""

import json
import whisper
from pathlib import Path
from typing import Optional
from datetime import datetime


class AudioTranscriber:
    """Transcribe audio files using Whisper."""
    
    def __init__(self, model_name: str = "base"):
        """
        Initialize the transcriber.
        
        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_name = model_name
        self.model = None
    
    def load_model(self):
        """Load the Whisper model."""
        if self.model is None:
            print(f"Loading Whisper model '{self.model_name}'...")
            self.model = whisper.load_model(self.model_name)
            print("Model loaded successfully!")
    
    def transcribe_audio(self, audio_path: str, language: str = "pt") -> dict:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to the audio file
            language: Language code (default: Portuguese)
        
        Returns:
            Dictionary with transcription results
        """
        self.load_model()
        
        print(f"Transcribing {audio_path}...")
        result = self.model.transcribe(
            audio_path,
            language=language,
            fp16=False  # Disable FP16 for CPU compatibility
        )
        
        return result
    
    def save_transcription(
        self,
        audio_path: str,
        output_dir: str = "output/transcriptions",
        language: str = "pt"
    ) -> str:
        """
        Transcribe audio and save to JSON file.
        
        Args:
            audio_path: Path to the audio file
            output_dir: Directory to save transcription JSON
            language: Language code
        
        Returns:
            Path to the saved JSON file
        """
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Transcribe
        result = self.transcribe_audio(audio_path, language)
        
        # Prepare output data
        audio_filename = Path(audio_path).stem
        output_data = {
            "audio_file": audio_path,
            "timestamp": datetime.now().isoformat(),
            "language": language,
            "model": self.model_name,
            "text": result["text"],
            "segments": result.get("segments", [])
        }
        
        # Save to JSON
        json_path = output_path / f"{audio_filename}_transcription.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"Transcription saved to: {json_path}")
        print(f"Transcribed text: {result['text']}")
        
        return str(json_path)
    
    def batch_transcribe(
        self,
        audio_files: list[str],
        output_dir: str = "output/transcriptions",
        language: str = "pt"
    ) -> list[str]:
        """
        Transcribe multiple audio files.
        
        Args:
            audio_files: List of audio file paths
            output_dir: Directory to save transcriptions
            language: Language code
        
        Returns:
            List of paths to saved JSON files
        """
        json_paths = []
        
        for audio_file in audio_files:
            try:
                json_path = self.save_transcription(audio_file, output_dir, language)
                json_paths.append(json_path)
            except Exception as e:
                print(f"Error transcribing {audio_file}: {e}")
        
        return json_paths


def transcribe_audio_file(
    audio_path: str,
    output_dir: str = "output/transcriptions",
    model_name: str = "base",
    language: str = "pt"
) -> str:
    """
    Convenience function to transcribe a single audio file.
    
    Args:
        audio_path: Path to the audio file
        output_dir: Directory to save transcription
        model_name: Whisper model size
        language: Language code
    
    Returns:
        Path to the saved JSON file
    """
    transcriber = AudioTranscriber(model_name)
    return transcriber.save_transcription(audio_path, output_dir, language)
