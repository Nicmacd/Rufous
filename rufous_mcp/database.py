"""
SQLite database management for Rufous PDF processing
Implements the schema defined in the PRD
"""

import sqlite3
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)


class RufousDatabase:
    """SQLite database manager for Rufous transaction data"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection"""
        if db_path is None:
            # Default to user's home directory
            home_dir = Path.home()
            self.db_path = home_dir / "rufous_data.db"
        else:
            self.db_path = Path(db_path)
            
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
    
    def _initialize_database(self):
        """Create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Transactions table
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    description TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    balance DECIMAL(10,2),
                    account_type TEXT NOT NULL, -- 'debit' or 'credit'
                    category TEXT,
                    is_transfer BOOLEAN DEFAULT FALSE,
                    statement_file TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Categories table for learning/customization
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    keywords TEXT, -- JSON array of associated keywords
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Statement tracking to prevent duplicates
                CREATE TABLE IF NOT EXISTS statements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    statement_date DATE NOT NULL,
                    account_type TEXT NOT NULL,
                    transaction_count INTEGER,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
                CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
                CREATE INDEX IF NOT EXISTS idx_transactions_account_type ON transactions(account_type);
                CREATE INDEX IF NOT EXISTS idx_transactions_description ON transactions(description);
            """)
            conn.commit()
        logger.info(f"Database initialized at {self.db_path}")
    
    def add_statement(self, filename: str, statement_date: date, account_type: str, transaction_count: int) -> int:
        """Add a processed statement record"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO statements (filename, statement_date, account_type, transaction_count) VALUES (?, ?, ?, ?)",
                (filename, statement_date, account_type, transaction_count)
            )
            conn.commit()
            return cursor.lastrowid
    
    def is_statement_processed(self, filename: str) -> bool:
        """Check if a statement has already been processed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM statements WHERE filename = ?", (filename,))
            return cursor.fetchone()[0] > 0
    
    def add_transactions(self, transactions: List[Dict[str, Any]]) -> int:
        """Add multiple transactions, return count of added transactions"""
        added_count = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for txn in transactions:
                # Check for duplicates (strict matching)
                cursor.execute(
                    """SELECT COUNT(*) FROM transactions 
                       WHERE date = ? AND description = ? AND amount = ? AND statement_file = ?""",
                    (txn['date'], txn['description'], txn['amount'], txn['statement_file'])
                )
                
                if cursor.fetchone()[0] == 0:  # No duplicate found
                    cursor.execute(
                        """INSERT INTO transactions 
                           (date, description, amount, balance, account_type, category, is_transfer, statement_file)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            txn['date'], txn['description'], txn['amount'], txn.get('balance'),
                            txn['account_type'], txn.get('category'), txn.get('is_transfer', False),
                            txn['statement_file']
                        )
                    )
                    added_count += 1
                else:
                    logger.debug(f"Duplicate transaction skipped: {txn['description']} on {txn['date']}")
            
            conn.commit()
        
        logger.info(f"Added {added_count} new transactions")
        return added_count
    
    def get_transactions(self, start_date: Optional[date] = None, end_date: Optional[date] = None, 
                        category: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get transactions with optional filters"""
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY date DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def search_transactions(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search transactions by description"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM transactions WHERE description LIKE ? ORDER BY date DESC LIMIT ?",
                (f"%{search_term}%", limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_spending_summary(self, start_date: Optional[date] = None, end_date: Optional[date] = None,
                           category: Optional[str] = None) -> Dict[str, Any]:
        """Get spending summary with totals and counts"""
        query = """
            SELECT 
                COUNT(*) as transaction_count,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spent,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_income,
                AVG(CASE WHEN amount < 0 THEN ABS(amount) ELSE NULL END) as avg_expense
            FROM transactions 
            WHERE 1=1 AND is_transfer = FALSE
        """
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if category:
            query += " AND category = ?"
            params.append(category)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            return {
                'transaction_count': result[0] or 0,
                'total_spent': round(result[1] or 0, 2),
                'total_income': round(result[2] or 0, 2),
                'average_expense': round(result[3] or 0, 2) if result[3] else 0
            }
    
    def get_category_breakdown(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get spending breakdown by category"""
        query = """
            SELECT 
                COALESCE(category, 'Uncategorized') as category,
                COUNT(*) as transaction_count,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spent
            FROM transactions 
            WHERE amount < 0 AND is_transfer = FALSE
        """
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " GROUP BY category ORDER BY total_spent DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def update_transaction_category(self, transaction_id: int, category: str):
        """Update the category of a specific transaction"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
                (category, transaction_id)
            )
            conn.commit()
    
    def get_uncategorized_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get transactions that need categorization"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM transactions WHERE category IS NULL ORDER BY date DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def add_category(self, name: str, keywords: List[str] = None):
        """Add a new category with optional keywords"""
        import json
        keywords_json = json.dumps(keywords) if keywords else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO categories (name, keywords) VALUES (?, ?)",
                (name, keywords_json)
            )
            conn.commit()
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM categories ORDER BY name")
            return [dict(row) for row in cursor.fetchall()] 