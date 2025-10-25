"""Import data from CSV files to database."""

import csv
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from .database import DatabaseManager


class DataImporter:
    """Import processed CSV data into the database."""
    
    def __init__(self, db_path: str = "data/drug_inventory.db"):
        """
        Initialize the importer.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db = DatabaseManager(db_path)
    
    def import_csv(self, csv_path: str) -> Dict[str, Any]:
        """
        Import data from a CSV file.
        
        Args:
            csv_path: Path to the CSV file
        
        Returns:
            Dictionary with import results
        """
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if not rows:
            return {"success": False, "error": "No data in CSV"}
        
        data_type = rows[0].get('type', '')
        
        if data_type == 'drug':
            return self._import_drug(rows[0])
        elif data_type == 'movement':
            return self._import_movement(rows[0])
        else:
            return {"success": False, "error": f"Unknown type: {data_type}"}
    
    def _import_drug(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Import a drug from CSV row."""
        drug_name = row.get('name', '').strip()
        
        if not drug_name:
            return {"success": False, "error": "Drug name is required"}
        
        # Check if drug already exists
        existing_drug = self.db.find_drug(
            drug_name,
            dose=row.get('dose'),
            lote=row.get('lote')
        )
        
        if existing_drug:
            return {
                "success": False,
                "error": f"Drug already exists with ID {existing_drug['id']}",
                "drug_id": existing_drug['id']
            }
        
        # Parse pieces_per_box
        pieces_per_box = 0
        if row.get('pieces_per_box'):
            try:
                pieces_per_box = int(row.get('pieces_per_box'))
            except ValueError:
                pass
        
        # Insert drug
        drug_data = {
            'name': drug_name,
            'dose': row.get('dose', ''),
            'units': row.get('units', ''),
            'expiration': row.get('expiration', ''),
            'pieces_per_box': pieces_per_box,
            'type': row.get('drug_type', ''),
            'lote': row.get('lote', ''),
            'current_stock': 0
        }
        
        drug_id = self.db.insert_drug(drug_data)
        
        return {
            "success": True,
            "type": "drug",
            "drug_id": drug_id,
            "message": f"Drug '{drug_name}' added with ID {drug_id}"
        }
    
    def _import_movement(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Import a movement from CSV row."""
        drug_name = row.get('drug_name', '').strip()
        movement_type = row.get('movement_type', '').strip().lower()
        
        if not drug_name:
            return {"success": False, "error": "Drug name is required"}
        
        if movement_type not in ['entry', 'exit', 'inventory']:
            return {"success": False, "error": f"Invalid movement type: {movement_type}"}
        
        # Find the drug
        drug = self.db.find_drug(
            drug_name,
            dose=row.get('drug_dose') if row.get('drug_dose') else None,
            lote=row.get('drug_lote') if row.get('drug_lote') else None
        )
        
        if not drug:
            return {
                "success": False,
                "error": f"Drug '{drug_name}' not found in database. Please add the drug first."
            }
        
        # Parse pieces_moved
        try:
            pieces_moved = int(row.get('pieces_moved', 0))
        except ValueError:
            return {"success": False, "error": "Invalid pieces_moved value"}
        
        if pieces_moved <= 0:
            return {"success": False, "error": "pieces_moved must be positive"}
        
        # Prepare movement data
        date_movement = row.get('date_movement', '')
        if not date_movement:
            date_movement = datetime.now().strftime('%Y-%m-%d')
        
        movement_data = {
            'drug_id': drug['id'],
            'movement_type': movement_type,
            'pieces_moved': pieces_moved,
            'destination_origin': row.get('destination_origin', ''),
            'date_movement': date_movement,
            'signature': row.get('signature', '')
        }
        
        # Insert movement
        movement_id = self.db.insert_movement(movement_data)
        
        # Get updated stock
        new_stock = self.db.get_drug_stock(drug['id'])
        
        return {
            "success": True,
            "type": "movement",
            "movement_id": movement_id,
            "drug_id": drug['id'],
            "drug_name": drug_name,
            "movement_type": movement_type,
            "pieces_moved": pieces_moved,
            "new_stock": new_stock,
            "message": f"Movement added: {movement_type} of {pieces_moved} pieces. New stock: {new_stock}"
        }
    
    def batch_import(self, csv_files: List[str]) -> List[Dict[str, Any]]:
        """
        Import multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths
        
        Returns:
            List of import results
        """
        results = []
        
        for csv_file in csv_files:
            try:
                result = self.import_csv(csv_file)
                result['file'] = csv_file
                results.append(result)
                
                if result['success']:
                    print(f"✓ {csv_file}: {result['message']}")
                else:
                    print(f"✗ {csv_file}: {result['error']}")
                    
            except Exception as e:
                results.append({
                    "success": False,
                    "file": csv_file,
                    "error": str(e)
                })
                print(f"✗ {csv_file}: Error - {e}")
        
        return results
    
    def import_with_review(self, csv_path: str) -> Dict[str, Any]:
        """
        Import CSV with manual review and confirmation.
        
        Args:
            csv_path: Path to the CSV file
        
        Returns:
            Import result
        """
        # Read and display CSV content
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if not rows:
            return {"success": False, "error": "No data in CSV"}
        
        row = rows[0]
        data_type = row.get('type', '')
        
        print("\n" + "="*60)
        print("DATA TO IMPORT:")
        print("="*60)
        for key, value in row.items():
            if value:
                print(f"  {key}: {value}")
        print("="*60)
        
        response = input("\nImport this data? (y/n): ").strip().lower()
        
        if response == 'y':
            result = self.import_csv(csv_path)
            return result
        else:
            return {"success": False, "error": "Import cancelled by user"}


def import_csv_file(
    csv_path: str,
    db_path: str = "data/drug_inventory.db",
    review: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to import a single CSV file.
    
    Args:
        csv_path: Path to the CSV file
        db_path: Path to the database
        review: Whether to review before importing
    
    Returns:
        Import result
    """
    importer = DataImporter(db_path)
    
    if review:
        return importer.import_with_review(csv_path)
    else:
        return importer.import_csv(csv_path)
