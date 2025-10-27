"""Import data from CSV files to database with intelligent drug matching."""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

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
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0.0 to 1.0)."""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def _find_matching_drug(
        self,
        movement: Dict[str, Any],
        threshold: float = 0.85
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Find a matching drug in the database with intelligent matching.
        
        Returns:
            Tuple of (drug_dict or None, reason_string)
        """
        name = movement.get('name', '').strip()
        dose = movement.get('dose', '').strip()
        units = movement.get('units', '').strip()
        expiration = movement.get('expiration', '').strip()
        lote = movement.get('lote', '').strip()
        
        if not name:
            return None, "No drug name provided"
        
        # Get all drugs from database
        all_drugs = self.db.list_drugs()
        
        if not all_drugs:
            return None, "Database is empty"
        
        # Try exact match first (name, dose, lote)
        exact_match = self.db.find_drug(name, dose=dose, lote=lote)
        if exact_match:
            return exact_match, f"Exact match found (ID: {exact_match['id']})"
        
        # Try fuzzy matching
        candidates = []
        for drug in all_drugs:
            score = 0.0
            reasons = []
            
            # Name similarity (most important)
            name_sim = self._calculate_similarity(name, drug.get('name', ''))
            if name_sim > threshold:
                score += name_sim * 4  # Weight: 4x
                reasons.append(f"name:{name_sim:.2f}")
            
            # Dose match (important)
            if dose and drug.get('dose'):
                if dose.lower() == drug.get('dose', '').lower():
                    score += 2
                    reasons.append("dose:exact")
                elif self._calculate_similarity(dose, drug.get('dose', '')) > 0.8:
                    score += 1
                    reasons.append("dose:similar")
            
            # Units match
            if units and drug.get('units'):
                if units.lower() == drug.get('units', '').lower():
                    score += 1
                    reasons.append("units:match")
            
            # Expiration match (important for perishables)
            if expiration and drug.get('expiration'):
                if expiration == drug.get('expiration'):
                    score += 2
                    reasons.append("exp:match")
            
            # Lote similarity (less important - can vary)
            if lote and drug.get('lote'):
                lote_sim = self._calculate_similarity(lote, drug.get('lote', ''))
                if lote_sim > 0.7:
                    score += lote_sim * 0.5  # Weight: 0.5x
                    reasons.append(f"lote:{lote_sim:.2f}")
            
            if score > 0:
                candidates.append({
                    'drug': drug,
                    'score': score,
                    'reasons': reasons
                })
        
        if not candidates:
            return None, "No similar drugs found in database"
        
        # Sort by score
        candidates.sort(key=lambda x: x['score'], reverse=True)
        best_match = candidates[0]
        
        # Only accept if score is high enough
        if best_match['score'] >= 5.0:  # Threshold for acceptance
            reason = f"Close match (ID: {best_match['drug']['id']}, score: {best_match['score']:.1f}, {', '.join(best_match['reasons'])})"
            return best_match['drug'], reason
        
        return None, f"Best match score too low ({best_match['score']:.1f})"
    
    def import_csv(self, csv_path: str, auto_create_drugs: bool = True) -> Dict[str, Any]:
        """
        Import data from a CSV file.
        
        Args:
            csv_path: Path to the CSV file
            auto_create_drugs: If True, create new drugs when no match found
        
        Returns:
            Dictionary with import results
        """
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if not rows:
            return {"success": False, "error": "No data in CSV"}
        
        results = {
            "success": True,
            "movements_processed": 0,
            "movements_failed": 0,
            "drugs_created": 0,
            "drugs_matched": 0,
            "details": []
        }
        
        for idx, row in enumerate(rows, 1):
            try:
                result = self._import_movement(row, auto_create_drugs)
                results["details"].append(result)
                
                if result["success"]:
                    results["movements_processed"] += 1
                    if result.get("drug_created"):
                        results["drugs_created"] += 1
                    else:
                        results["drugs_matched"] += 1
                else:
                    results["movements_failed"] += 1
                    
            except Exception as e:
                results["movements_failed"] += 1
                results["details"].append({
                    "success": False,
                    "movement_number": idx,
                    "error": str(e)
                })
        
        if results["movements_failed"] > 0:
            results["success"] = False
        
        return results
    
    def _import_movement(
        self,
        movement: Dict[str, str],
        auto_create_drugs: bool = True
    ) -> Dict[str, Any]:
        """Import a single movement from CSV row."""
        drug_name = movement.get('name', '').strip()
        movement_type = movement.get('movement_type', '').strip().lower()
        
        if not drug_name:
            return {"success": False, "error": "Drug name is required"}
        
        if movement_type not in ['entry', 'exit', 'inventory']:
            return {"success": False, "error": f"Invalid movement type: {movement_type}"}
        
        # Try to find matching drug
        matched_drug, match_reason = self._find_matching_drug(movement)
        
        drug_id = None
        drug_created = False
        
        if matched_drug:
            drug_id = matched_drug['id']
            print(f"  ✓ {match_reason}")
        elif auto_create_drugs:
            # Create new drug
            drug_data = {
                'name': drug_name,
                'dose': movement.get('dose', ''),
                'units': movement.get('units', ''),
                'expiration': movement.get('expiration', ''),
                'pieces_per_box': int(movement.get('pieces_per_box', 0)) if movement.get('pieces_per_box') else 0,
                'type': movement.get('type', ''),
                'lote': movement.get('lote', ''),
                'current_stock': 0
            }
            drug_id = self.db.insert_drug(drug_data)
            drug_created = True
            print(f"  ✓ Created new drug (ID: {drug_id})")
        else:
            return {
                "success": False,
                "error": f"No matching drug found and auto_create_drugs=False. {match_reason}"
            }
        
        # Parse pieces_moved
        try:
            pieces_moved = int(movement.get('pieces_moved', 0)) if movement.get('pieces_moved') else 0
        except ValueError:
            return {"success": False, "error": "Invalid pieces_moved value"}
        
        if pieces_moved <= 0:
            return {"success": False, "error": "pieces_moved must be positive"}
        
        # Prepare movement data
        date_movement = movement.get('date_movement', '')
        if not date_movement:
            date_movement = datetime.now().strftime('%Y-%m-%d')
        
        movement_data = {
            'drug_id': drug_id,
            'movement_type': movement_type,
            'pieces_moved': pieces_moved,
            'destination_origin': movement.get('destination_origin', ''),
            'date_movement': date_movement,
            'signature': movement.get('signature', '')
        }
        
        # Insert movement
        movement_id = self.db.insert_movement(movement_data)
        
        # Get updated stock
        new_stock = self.db.get_drug_stock(drug_id)
        
        return {
            "success": True,
            "drug_created": drug_created,
            "movement_id": movement_id,
            "drug_id": drug_id,
            "drug_name": drug_name,
            "movement_type": movement_type,
            "pieces_moved": pieces_moved,
            "new_stock": new_stock,
            "message": f"{movement_type.capitalize()} of {pieces_moved} pieces. New stock: {new_stock}"
        }
    
    def batch_import(self, csv_files: List[str], auto_create_drugs: bool = True) -> List[Dict[str, Any]]:
        """
        Import multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths
            auto_create_drugs: If True, create new drugs when no match found
        
        Returns:
            List of import results
        """
        results = []
        
        for csv_file in csv_files:
            try:
                print(f"\nProcessing: {csv_file}")
                result = self.import_csv(csv_file, auto_create_drugs)
                result['file'] = csv_file
                results.append(result)
                
                if result['success']:
                    print(f"✓ {result['movements_processed']} movements imported")
                    print(f"  - {result['drugs_created']} new drugs created")
                    print(f"  - {result['drugs_matched']} existing drugs matched")
                else:
                    print(f"✗ {result['movements_failed']} movements failed")
                    
            except Exception as e:
                results.append({
                    "success": False,
                    "file": csv_file,
                    "error": str(e)
                })
                print(f"✗ Error: {e}")
        
        return results
    
    def import_with_review(self, csv_path: str, auto_create_drugs: bool = True) -> Dict[str, Any]:
        """
        Import CSV with manual review and confirmation.
        
        Args:
            csv_path: Path to the CSV file
            auto_create_drugs: If True, create new drugs when no match found
        
        Returns:
            Import result
        """
        # Read and display CSV content
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if not rows:
            return {"success": False, "error": "No data in CSV"}
        
        print("\n" + "="*80)
        print(f"MOVEMENTS TO IMPORT: {len(rows)}")
        print("="*80)
        
        for idx, row in enumerate(rows, 1):
            print(f"\n[{idx}] {row.get('name', 'N/A')}")
            print(f"    Type: {row.get('movement_type', 'N/A')}")
            print(f"    Dose: {row.get('dose', '')} {row.get('units', '')}")
            print(f"    Pieces: {row.get('pieces_moved', 'N/A')}")
            if row.get('lote'):
                print(f"    Lot: {row.get('lote')}")
            if row.get('destination_origin'):
                print(f"    Dest/Origin: {row.get('destination_origin')}")
        
        print("="*80)
        
        response = input("\nImport these movements? (y/n): ").strip().lower()
        
        if response == 'y':
            result = self.import_csv(csv_path, auto_create_drugs)
            return result
        else:
            return {"success": False, "error": "Import cancelled by user"}


def import_csv_file(
    csv_path: str,
    db_path: str = "data/drug_inventory.db",
    review: bool = False,
    auto_create_drugs: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to import a single CSV file.
    
    Args:
        csv_path: Path to the CSV file
        db_path: Path to the database
        review: Whether to review before importing
        auto_create_drugs: If True, create new drugs when no match found
    
    Returns:
        Import result
    """
    importer = DataImporter(db_path)
    
    if review:
        return importer.import_with_review(csv_path, auto_create_drugs)
    else:
        return importer.import_csv(csv_path, auto_create_drugs)
