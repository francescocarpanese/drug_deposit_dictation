"""Process transcriptions using LLM to extract structured data."""

import json
import csv
import ollama
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DrugMovement(BaseModel):
    """Complete drug movement information model."""
    name: str = Field(description="Drug name")
    dose: Optional[str] = Field(default=None, description="Dose amount (number only)")
    units: Optional[str] = Field(default=None, description="Units (mg, ml, g, l, etc.)")
    expiration: Optional[str] = Field(default=None, description="Expiration date (YYYY-MM-DD)")
    pieces_per_box: Optional[int] = Field(default=None, description="Pieces per box")
    type: Optional[str] = Field(default=None, description="Drug type: comprimidos, ampulla, xarope, pomadas, frasca")
    lote: Optional[str] = Field(default=None, description="Lot number")
    movement_type: str = Field(description="Type: entry, exit, or inventory")
    pieces_moved: Optional[int] = Field(default=None, description="Number of pieces moved")
    boxes_moved: Optional[int] = Field(default=None, description="Number of boxes (for inventory)")
    destination_origin: Optional[str] = Field(default=None, description="Supplier (entry) or receiver (exit)")
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
            Dictionary with list of movements
        """
        system_prompt = """You are an assistant that extracts drug inventory movement information from spoken Portuguese text.

Your task is to identify ALL movements mentioned in the audio. Each movement MUST include:
- Drug information: name, dose (number), units of the dose (mg/ml/g/l), expiration date, pieces per box, type (comprimidos/ampulla/xarope/pomadas/frasca), lot number
- Movement type: MUST be "entry", "exit", or "inventory" (entrada/saída/inventário in Portuguese)
- Pieces moved: number of pieces (for inventory: if boxes and pieces per box are mentioned, multiply them)
- Destination/origin: supplier name for entry, receiver for exit, empty for inventory
- Date: movement date if mentioned

IMPORTANT RULES:
1. The audio should ALWAYS contains a movement type (entry/exit/inventory). If not there, leave blank.
2. There may be MULTIPLE movements in one audio - extract ALL of them
3. For inventory: if "X caixas de Y comprimidos" (X boxes of Y pieces), pieces_moved = X * Y
4. Return a LIST of movements, even if only one movement

Return ONLY valid JSON with this structure:
{
  "movements": [
    {
      "name": "drug name",
      "dose": "dose number only",
      "units": "mg/ml/g/l",
      "expiration": "YYYY-MM-DD",
      "pieces_per_box": number,
      "type": "comprimidos/ampulla/xarope/pomadas/frasca",
      "lote": "lot number",
      "movement_type": "entry/exit/inventory",
      "pieces_moved": number,
      "destination_origin": "supplier or receiver",
      "date_movement": "YYYY-MM-DD",
    }
  ]
}

For example. 
Transcription:  Aqui temos ácido folico, 3 caixinha por 100, que é de 5 miligrama, incompreido. Eu comprimido com lote de SNT4112, que é caduco a fevereira de 2,027.
Return:
{
  "movements": [
    {
      "name": "ácido folico",
      "dose": "5",
      "units": "ml", (This must be conveterd to SI units)
      "expiration": "2027-02-01",
      "pieces_per_box": 100,
      "type": "comprimidos",
      "lote": "SNT4112",
      "movement_type": "",
      "pieces_moved": 300, (This is computerd as 3 boxes * 100 pieces_per_box)
      "destination_origin": "",
      "date_movement": "",
    }
  ]
}


Include only the fields that are mentioned. Calculate pieces_moved for inventory if boxes and pieces_per_box are given."""

        user_prompt = f"""Extract ALL drug movement information from this Portuguese text:

"{transcription_text}"

Remember:
- Find the movement type (entrada/saída/inventário)
- Extract ALL movements if multiple
- For inventory with boxes: multiply boxes × pieces_per_box

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
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text.strip())
            
            # Ensure movements is a list
            if "movements" not in result:
                # Try to wrap in movements list if not present
                result = {"movements": [result] if isinstance(result, dict) else result}
            
            # Calculate pieces_moved for inventory if boxes_moved is present
            for movement in result.get("movements", []):
                if movement.get("movement_type") == "inventory":
                    boxes = movement.get("boxes_moved")
                    pieces_per_box = movement.get("pieces_per_box")
                    if boxes and pieces_per_box and not movement.get("pieces_moved"):
                        movement["pieces_moved"] = boxes * pieces_per_box
            
            return result
            
        except Exception as e:
            print(f"Error processing with LLM: {e}")
            return {
                "movements": [],
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
        
        # Create CSV for movements
        csv_path = output_path / f"{json_filename}_data.csv"
        self._save_movements_csv(extracted_data.get('movements', []), csv_path)
        
        print(f"CSV saved to: {csv_path}")
        return str(csv_path)
    
    def _save_movements_csv(self, movements: List[Dict[str, Any]], csv_path: Path):
        """Save movements data to CSV."""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'name', 'dose', 'units', 'expiration',
                'pieces_per_box', 'type', 'lote',
                'movement_type', 'pieces_moved', 'boxes_moved',
                'destination_origin', 'date_movement', 'signature'
            ])
            
            for movement in movements:
                writer.writerow([
                    movement.get('name', ''),
                    movement.get('dose', ''),
                    movement.get('units', ''),
                    movement.get('expiration', ''),
                    movement.get('pieces_per_box', ''),
                    movement.get('type', ''),
                    movement.get('lote', ''),
                    movement.get('movement_type', ''),
                    movement.get('pieces_moved', ''),
                    movement.get('boxes_moved', ''),
                    movement.get('destination_origin', ''),
                    movement.get('date_movement', ''),
                    movement.get('signature', '')
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
