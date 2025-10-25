"""Database management for drugs and movements."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


def create_all_tables(path_to_database: str) -> None:
    """Create all necessary database tables."""
    conn = sqlite3.connect(path_to_database)
    c = conn.cursor()

    # Create drugs table
    c.execute(
        """CREATE TABLE IF NOT EXISTS drugs 
        (
            id INTEGER PRIMARY KEY,
            name TEXT,
            dose TEXT,
            units TEXT,
            expiration DATE,
            pieces_per_box INTEGER,
            type TEXT,
            lote TEXT,
            current_stock INTEGER DEFAULT 0,
            last_inventory_date DATE DEFAULT '1990-01-01'
        )
        """
    )

    # Create movements table
    c.execute(
        """CREATE TABLE IF NOT EXISTS movements 
        (
            id INTEGER PRIMARY KEY,
            date_movement DATE,
            destination_origin TEXT,
            pieces_moved INTEGER,
            movement_type TEXT CHECK(movement_type IN ('entry', 'exit', 'inventory')),
            signature TEXT,
            entry_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            drug_id INTEGER,
            FOREIGN KEY (drug_id) REFERENCES drugs(id)
        )
        """
    )

    # Create trigger for update timestamp
    c.execute("DROP TRIGGER IF EXISTS update_movements_entry_datetime")
    c.execute(
        """CREATE TRIGGER update_movements_entry_datetime
            AFTER UPDATE ON movements
            FOR EACH ROW
            WHEN OLD.entry_datetime <> CURRENT_TIMESTAMP
            BEGIN
                UPDATE movements SET entry_datetime = CURRENT_TIMESTAMP WHERE id = OLD.id;
            END;
        """
    )

    conn.commit()
    conn.close()


class DatabaseManager:
    """Manage database operations for drugs and movements."""
    
    def __init__(self, db_path: str):
        """Initialize database manager."""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        create_all_tables(db_path)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def find_drug(self, name: str, dose: Optional[str] = None, lote: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a drug by name, optionally filtering by dose and lote."""
        conn = self.get_connection()
        c = conn.cursor()
        
        query = "SELECT * FROM drugs WHERE LOWER(name) = LOWER(?)"
        params = [name]
        
        if dose:
            query += " AND LOWER(dose) = LOWER(?)"
            params.append(dose)
        
        if lote:
            query += " AND LOWER(lote) = LOWER(?)"
            params.append(lote)
        
        c.execute(query, params)
        row = c.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def insert_drug(self, drug_data: Dict[str, Any]) -> int:
        """Insert a new drug and return its ID."""
        conn = self.get_connection()
        c = conn.cursor()
        
        c.execute(
            """INSERT INTO drugs (name, dose, units, expiration, pieces_per_box, type, lote, current_stock)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                drug_data.get('name'),
                drug_data.get('dose'),
                drug_data.get('units'),
                drug_data.get('expiration'),
                drug_data.get('pieces_per_box', 0),
                drug_data.get('type'),
                drug_data.get('lote'),
                drug_data.get('current_stock', 0)
            )
        )
        
        drug_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return drug_id
    
    def insert_movement(self, movement_data: Dict[str, Any]) -> int:
        """Insert a new movement and update drug stock."""
        conn = self.get_connection()
        c = conn.cursor()
        
        # Insert movement
        c.execute(
            """INSERT INTO movements (date_movement, destination_origin, pieces_moved, movement_type, signature, drug_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                movement_data.get('date_movement', datetime.now().strftime('%Y-%m-%d')),
                movement_data.get('destination_origin'),
                movement_data.get('pieces_moved'),
                movement_data.get('movement_type'),
                movement_data.get('signature', ''),
                movement_data.get('drug_id')
            )
        )
        
        movement_id = c.lastrowid
        
        # Update stock based on movement type
        drug_id = movement_data.get('drug_id')
        pieces_moved = movement_data.get('pieces_moved', 0)
        movement_type = movement_data.get('movement_type')
        
        if movement_type == 'entry':
            c.execute(
                "UPDATE drugs SET current_stock = current_stock + ? WHERE id = ?",
                (pieces_moved, drug_id)
            )
        elif movement_type == 'exit':
            c.execute(
                "UPDATE drugs SET current_stock = current_stock - ? WHERE id = ?",
                (pieces_moved, drug_id)
            )
        elif movement_type == 'inventory':
            c.execute(
                "UPDATE drugs SET current_stock = ?, last_inventory_date = ? WHERE id = ?",
                (pieces_moved, datetime.now().strftime('%Y-%m-%d'), drug_id)
            )
        
        conn.commit()
        conn.close()
        
        return movement_id
    
    def get_drug_stock(self, drug_id: int) -> int:
        """Get current stock for a drug."""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT current_stock FROM drugs WHERE id = ?", (drug_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return row['current_stock']
        return 0
    
    def list_drugs(self) -> List[Dict[str, Any]]:
        """List all drugs."""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM drugs ORDER BY name")
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_movements_for_drug(self, drug_id: int) -> List[Dict[str, Any]]:
        """Get all movements for a specific drug."""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT * FROM movements WHERE drug_id = ? ORDER BY date_movement DESC, entry_datetime DESC",
            (drug_id,)
        )
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
