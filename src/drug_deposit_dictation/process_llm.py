"""Process transcriptions using LLM to extract structured data."""

import json
import csv
import ollama
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DrugInfo(BaseModel):
    """Drug information model."""
    name: str = Field(description="Drug name")
    dose: Optional[str] = Field(default=None, description="Dose amount")
    units: Optional[str] = Field(default=None, description="Units (mg, ml, g, etc.)")
    expiration: Optional[str] = Field(default=None, description="Expiration date (YYYY-MM-DD)")
    pieces_per_box: Optional[int] = Field(default=None, description="Pieces per box")
    type: Optional[str] = Field(default=None, description="Drug type (antibiotic, analgesic, etc.)")
    lote: Optional[str] = Field(default=None, description="Lot number")


class MovementInfo(BaseModel):
    """Movement information model."""
    drug_name: str = Field(description="Name of the drug")
    drug_dose: Optional[str] = Field(default=None, description="Dose of the drug")
    drug_lote: Optional[str] = Field(default=None, description="Lot number")
    movement_type: str = Field(description="Type: entry, exit, or inventory")
    pieces_moved: int = Field(description="Number of pieces")
    destination_origin: Optional[str] = Field(default=None, description="Destination (for exit) or origin (for entry)")
    date_movement: Optional[str] = Field(default=None, description="Date of movement (YYYY-MM-DD)")
    signature: Optional[str] = Field(default=None, description="Person responsible")


class TranscriptionProcessor:
    """Process transcriptions using LLM."""
    
    def __init__(self, model_name: str = "llama3.1"):
        """
        Initialize the processor.
        
        Args:
            model_name: Ollama model name
        """
        self.model_name = model_name
    
    def process_transcription(self, transcription_text: str) -> Dict[str, Any]:
        """
        Process transcription text and extract structured information.
        
        Args:
            transcription_text: The transcribed text
        
        Returns:
            Dictionary with extracted information
        """
        system_prompt = """
You are an assistant that extracts drug inventory information from spoken Portuguese text.
Your task is to identify:
1. Drug information: name, dose, units, expiration date, pieces per box, type, lot number
2. Movement information: movement type (entry/exit/inventory), pieces moved, destination/origin, date, signature

Return ONLY valid JSON with this structure:
{
  "type": "drug" or "movement",
  "drug": {
    "name": "drug name",
    "dose": "dose amount",
    "units": "units",
    "expiration": "YYYY-MM-DD",
    "pieces_per_box": number,
    "type": "drug type",
    "lote": "lot number"
  },
  "movement": {
    "drug_name": "drug name",
    "drug_dose": "dose",
    "drug_lote": "lot number",
    "movement_type": "entry/exit/inventory",
    "pieces_moved": number,
    "destination_origin": "destination or origin",
    "date_movement": "YYYY-MM-DD",
    "signature": "person name"
  }
}

Include only the fields that are mentioned in the text. If it's a new drug definition, use "type": "drug". If it's a movement, use "type": "movement"."""

        user_prompt = f"""Extract drug inventory information from this text:

"{transcription_text}"

Return only the JSON object, no explanation."""

        print(f"Processing with {self.model_name}...")
        
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            response_text = response['message']['content']
            
            # Try to extract JSON from the response
            # Sometimes the model adds markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text.strip())
            return result
            
        except Exception as e:
            print(f"Error processing with LLM: {e}")
            # Return a basic structure if parsing fails
            return {
                "type": "unknown",
                "error": str(e),
                "raw_text": transcription_text
            }
    
    def process_json_to_csv(
        self,
        json_path: str,
        output_dir: str = "output/processed"
    ) -> str:
        """
        Process a transcription JSON file and create CSV output.
        
        Args:
            json_path: Path to transcription JSON file
            output_dir: Directory to save CSV output
        
        Returns:
            Path to the saved CSV file
        """
        # Load transcription
        with open(json_path, 'r', encoding='utf-8') as f:
            transcription_data = json.load(f)
        
        text = transcription_data.get('text', '')
        
        # Process with LLM
        extracted_data = self.process_transcription(text)
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save processed JSON
        json_filename = Path(json_path).stem
        processed_json_path = output_path / f"{json_filename}_processed.json"
        
        processed_data = {
            "original_transcription": text,
            "extracted_data": extracted_data,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(processed_json_path, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        
        print(f"Processed JSON saved to: {processed_json_path}")
        
        # Create CSV
        csv_path = output_path / f"{json_filename}_data.csv"
        
        data_type = extracted_data.get('type', 'unknown')
        
        if data_type == 'drug':
            self._save_drug_csv(extracted_data.get('drug', {}), csv_path)
        elif data_type == 'movement':
            self._save_movement_csv(extracted_data.get('movement', {}), csv_path)
        else:
            print(f"Warning: Unknown data type '{data_type}'")
            # Save a generic CSV with raw data
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['type', 'raw_data'])
                writer.writerow([data_type, json.dumps(extracted_data)])
        
        print(f"CSV saved to: {csv_path}")
        return str(csv_path)
    
    def _save_drug_csv(self, drug_data: Dict[str, Any], csv_path: Path):
        """Save drug data to CSV."""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'type', 'name', 'dose', 'units', 'expiration',
                'pieces_per_box', 'drug_type', 'lote'
            ])
            writer.writerow([
                'drug',
                drug_data.get('name', ''),
                drug_data.get('dose', ''),
                drug_data.get('units', ''),
                drug_data.get('expiration', ''),
                drug_data.get('pieces_per_box', ''),
                drug_data.get('type', ''),
                drug_data.get('lote', '')
            ])
    
    def _save_movement_csv(self, movement_data: Dict[str, Any], csv_path: Path):
        """Save movement data to CSV."""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'type', 'drug_name', 'drug_dose', 'drug_lote',
                'movement_type', 'pieces_moved', 'destination_origin',
                'date_movement', 'signature'
            ])
            writer.writerow([
                'movement',
                movement_data.get('drug_name', ''),
                movement_data.get('drug_dose', ''),
                movement_data.get('drug_lote', ''),
                movement_data.get('movement_type', ''),
                movement_data.get('pieces_moved', ''),
                movement_data.get('destination_origin', ''),
                movement_data.get('date_movement', ''),
                movement_data.get('signature', '')
            ])
    
    def batch_process(
        self,
        json_files: List[str],
        output_dir: str = "output/processed"
    ) -> List[str]:
        """
        Process multiple JSON transcription files.
        
        Args:
            json_files: List of JSON file paths
            output_dir: Directory to save output
        
        Returns:
            List of paths to saved CSV files
        """
        csv_paths = []
        
        for json_file in json_files:
            try:
                csv_path = self.process_json_to_csv(json_file, output_dir)
                csv_paths.append(csv_path)
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
        
        return csv_paths


def process_transcription_file(
    json_path: str,
    output_dir: str = "output/processed",
    model_name: str = "llama3.1"
) -> str:
    """
    Convenience function to process a single transcription file.
    
    Args:
        json_path: Path to transcription JSON file
        output_dir: Directory to save output
        model_name: Ollama model name
    
    Returns:
        Path to the saved CSV file
    """
    processor = TranscriptionProcessor(model_name)
    return processor.process_json_to_csv(json_path, output_dir)
