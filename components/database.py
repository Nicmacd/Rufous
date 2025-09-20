"""
Enhanced SQLite database management for Rufous v2
Optimized for analytics and fast querying with Streamlit
"""

import sqlite3
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


class RufousDatabase:
    """Enhanced SQLite database manager optimized for financial analytics"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection"""
        if db_path is None:
            # Default to data directory
            self.db_path = Path(__file__).parent.parent / "data" / "transactions.db"
        else:
            self.db_path = Path(db_path)
            
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
    
    def _initialize_database(self):
        """Create optimized tables for analytics"""
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            # Use simple, fast settings for single-user desktop app
            conn.execute("PRAGMA journal_mode=DELETE")  # Default rollback journal
            conn.execute("PRAGMA synchronous=NORMAL")   # Good balance of safety/speed
            conn.execute("PRAGMA cache_size=10000")     # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")    # Keep temp tables in RAM
            
            conn.executescript("""
                -- Enhanced transactions table with better indexing
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    description TEXT NOT NULL,
                    amount DECIMAL(12,2) NOT NULL,
                    balance DECIMAL(12,2),
                    account_type TEXT NOT NULL, -- 'debit' or 'credit'
                    category TEXT,
                    subcategory TEXT,
                    merchant TEXT, -- Extracted merchant name
                    is_transfer BOOLEAN DEFAULT FALSE,
                    is_recurring BOOLEAN DEFAULT FALSE,
                    statement_file TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Enhanced categories with hierarchy
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    parent_category TEXT,
                    keywords TEXT, -- JSON array of keywords
                    color_hex TEXT, -- For visualization
                    budget_limit DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Statement tracking with metadata
                CREATE TABLE IF NOT EXISTS statements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    statement_date DATE NOT NULL,
                    account_type TEXT NOT NULL,
                    transaction_count INTEGER,
                    total_amount DECIMAL(12,2),
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- User query history for saved queries feature
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_text TEXT NOT NULL,
                    query_type TEXT, -- 'search', 'analysis', 'visualization'
                    results_summary TEXT,
                    favorited BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Performance indexes
                CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
                CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions(amount);
                CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
                CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(merchant);
                CREATE INDEX IF NOT EXISTS idx_transactions_description ON transactions(description);
                CREATE INDEX IF NOT EXISTS idx_transactions_account_date ON transactions(account_type, date);
                
                -- Query optimization indexes
                CREATE INDEX IF NOT EXISTS idx_query_favorited ON query_history(favorited, created_at);
            """)
            conn.commit()
        logger.info(f"Enhanced database initialized at {self.db_path}")
    
    def add_statement(self, filename: str, statement_date: date, account_type: str, 
                     transaction_count: int, total_amount: float = 0.0) -> int:
        """Add processed statement with enhanced metadata"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO statements 
                   (filename, statement_date, account_type, transaction_count, total_amount) 
                   VALUES (?, ?, ?, ?, ?)""",
                (filename, statement_date, account_type, transaction_count, total_amount)
            )
            conn.commit()
            return cursor.lastrowid
    
    def is_statement_processed(self, filename: str) -> bool:
        """Check if statement already processed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM statements WHERE filename = ?", (filename,))
            return cursor.fetchone()[0] > 0
    
    def add_transactions(self, transactions: List[Dict[str, Any]]) -> int:
        """Add transactions with enhanced deduplication and better error handling"""
        added_count = 0
        try:
            with sqlite3.connect(self.db_path, timeout=60.0) as conn:
                # Set optimizations for bulk insert
                conn.execute("PRAGMA busy_timeout=60000")
                conn.execute("PRAGMA synchronous=NORMAL")
                cursor = conn.cursor()
                
                # Process transactions in batches to avoid long-running transactions
                batch_size = 100
                for i in range(0, len(transactions), batch_size):
                    batch = transactions[i:i+batch_size]
                    
                    for txn in batch:
                        # Enhanced duplicate checking
                        cursor.execute(
                            """SELECT COUNT(*) FROM transactions 
                               WHERE date = ? AND description = ? AND ABS(amount - ?) < 0.01 
                               AND statement_file = ?""",
                            (txn['date'], txn['description'], txn['amount'], txn['statement_file'])
                        )
                        
                        if cursor.fetchone()[0] == 0:
                            cursor.execute(
                                """INSERT INTO transactions 
                                   (date, description, amount, balance, account_type, category, 
                                    subcategory, merchant, is_transfer, is_recurring, statement_file)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    txn['date'], txn['description'], txn['amount'], 
                                    txn.get('balance'), txn['account_type'],
                                    txn.get('category'), txn.get('subcategory'),
                                    txn.get('merchant'), txn.get('is_transfer', False),
                                    txn.get('is_recurring', False), txn['statement_file']
                                )
                            )
                            added_count += 1
                    
                    # Commit each batch
                    conn.commit()
                    logger.debug(f"Processed batch {i//batch_size + 1}/{(len(transactions) + batch_size - 1)//batch_size}")
            
            logger.info(f"Added {added_count} new transactions")
            return added_count
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.error(f"Database locked during transaction insert: {e}")
                return 0
            logger.error(f"Database error during transaction insert: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during transaction insert: {e}")
            raise
    
    def get_transactions_df(self, start_date: Optional[date] = None, 
                           end_date: Optional[date] = None,
                           category: Optional[str] = None,
                           limit: Optional[int] = None,
                           include_transfers: bool = False) -> pd.DataFrame:
        """Get transactions as pandas DataFrame for analytics"""
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        # Exclude transfers by default
        if not include_transfers:
            query += " AND is_transfer = FALSE"
        
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
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df['amount'] = pd.to_numeric(df['amount'])
            return df
    
    def search_transactions(self, search_term: str, limit: int = 100) -> pd.DataFrame:
        """Search transactions returning DataFrame"""
        with sqlite3.connect(self.db_path) as conn:
            query = """SELECT * FROM transactions 
                      WHERE (description LIKE ? OR merchant LIKE ?) 
                      AND is_transfer = FALSE
                      ORDER BY date DESC LIMIT ?"""
            df = pd.read_sql_query(
                query, conn, 
                params=[f"%{search_term}%", f"%{search_term}%", limit]
            )
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df['amount'] = pd.to_numeric(df['amount'])
            return df
    
    def get_spending_by_category(self, start_date: Optional[date] = None, 
                                end_date: Optional[date] = None) -> pd.DataFrame:
        """Get spending breakdown by category as DataFrame"""
        query = """
            SELECT 
                COALESCE(category, 'Uncategorized') as category,
                COUNT(*) as transaction_count,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_spent,
                AVG(CASE WHEN amount > 0 THEN amount ELSE NULL END) as avg_expense
            FROM transactions 
            WHERE is_transfer = FALSE
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
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty:
                df['total_spent'] = pd.to_numeric(df['total_spent'])
                df['avg_expense'] = pd.to_numeric(df['avg_expense'])
            return df
    
    def get_monthly_trends(self, months: int = 12) -> pd.DataFrame:
        """Get monthly spending trends"""
        query = """
            SELECT 
                strftime('%Y-%m', date) as month,
                COUNT(*) as transaction_count,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_spent,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_returns
            FROM transactions 
            WHERE date >= date('now', '-{} months')
            AND is_transfer = FALSE
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month
        """.format(months)
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                df['month'] = pd.to_datetime(df['month'])
                df['total_spent'] = pd.to_numeric(df['total_spent'])
                df['total_returns'] = pd.to_numeric(df['total_returns'])
                df['net_flow'] = df['total_returns'] - df['total_spent']  # Returns (negative) - Spent (positive) = negative net flow
            return df
    
    def save_query(self, query_text: str, query_type: str = 'search', 
                   results_summary: str = '', favorited: bool = False) -> int:
        """Save user query for history/favorites"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO query_history 
                   (query_text, query_type, results_summary, favorited)
                   VALUES (?, ?, ?, ?)""",
                (query_text, query_type, results_summary, favorited)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_favorite_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get favorited queries"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM query_history 
                   WHERE favorited = TRUE 
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for dashboard"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Basic stats
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total_transactions = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM statements")
            total_statements = cursor.fetchone()[0]
            
            cursor.execute("SELECT MIN(date), MAX(date) FROM transactions")
            date_range = cursor.fetchone()
            
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_spent,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_returns
                FROM transactions WHERE is_transfer = FALSE
            """)
            totals = cursor.fetchone()
            
            return {
                'total_transactions': total_transactions,
                'total_statements': total_statements,
                'date_range': {
                    'earliest': date_range[0],
                    'latest': date_range[1]
                },
                'total_spent': round(totals[0] or 0, 2),
                'total_returns': round(totals[1] or 0, 2),
                'net_worth_change': round((totals[1] or 0) - (totals[0] or 0), 2)  # Returns - Spent = Net Change
            }
    
    def update_transaction_category(self, transaction_id: int, category: str, subcategory: str = None) -> bool:
        """Update category for a specific transaction"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE transactions SET category = ?, subcategory = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (category, subcategory, transaction_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update transaction category: {e}")
            return False
    
    def bulk_update_categories(self, search_term: str, category: str, subcategory: str = None) -> int:
        """Update category for all transactions matching search term"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """UPDATE transactions 
                       SET category = ?, subcategory = ?, updated_at = CURRENT_TIMESTAMP 
                       WHERE description LIKE ? OR merchant LIKE ?""",
                    (category, subcategory, f"%{search_term}%", f"%{search_term}%")
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to bulk update categories: {e}")
            return 0
    
    def auto_categorize_transactions(self, force_recategorize: bool = False) -> int:
        """Auto-categorize uncategorized transactions using the categorizer"""
        from .categorizer import TransactionCategorizer
        
        categorizer = TransactionCategorizer(str(self.db_path))
        
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                # Get uncategorized transactions (or all if force_recategorize)
                if force_recategorize:
                    query = "SELECT id, description, merchant, amount FROM transactions"
                else:
                    query = "SELECT id, description, merchant, amount FROM transactions WHERE category IS NULL OR category = ''"
                
                cursor.execute(query)
                transactions = cursor.fetchall()
                
                if not transactions:
                    logger.info("No transactions need categorization")
                    return 0
                
                logger.info(f"Categorizing {len(transactions)} transactions...")
                
                updated_count = 0
                batch_size = 25  # Smaller batches for faster processing
                
                for i in range(0, len(transactions), batch_size):
                    batch = transactions[i:i+batch_size]
                    
                    # Prepare batch updates
                    updates = []
                    for txn_id, description, merchant, amount in batch:
                        category, subcategory = categorizer.categorize_transaction(
                            description or '', merchant or '', amount
                        )
                        
                        if category:
                            updates.append((category, subcategory, txn_id))
                    
                    # Execute batch updates
                    if updates:
                        cursor.executemany(
                            "UPDATE transactions SET category = ?, subcategory = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            updates
                        )
                        updated_count += len(updates)
                    
                    # Commit each batch to avoid long transactions
                    conn.commit()
                    logger.debug(f"Categorized batch {i//batch_size + 1}/{(len(transactions) + batch_size - 1)//batch_size}")
                
                logger.info(f"Auto-categorized {updated_count} transactions")
                return updated_count
                
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.error(f"Database locked during auto-categorization: {e}")
                raise  # Re-raise so the retry logic in app.py can handle it
            logger.error(f"Database error during auto-categorization: {e}")
            return 0
        except Exception as e:
            logger.error(f"Auto-categorization failed: {e}")
            return 0
    
    def get_category_summary(self) -> Dict[str, int]:
        """Get summary of categorization status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total transactions
                cursor.execute("SELECT COUNT(*) FROM transactions")
                total = cursor.fetchone()[0]
                
                # Categorized transactions
                cursor.execute("SELECT COUNT(*) FROM transactions WHERE category IS NOT NULL AND category != ''")
                categorized = cursor.fetchone()[0]
                
                # Category breakdown
                cursor.execute("""
                    SELECT category, COUNT(*) 
                    FROM transactions 
                    WHERE category IS NOT NULL AND category != ''
                    GROUP BY category 
                    ORDER BY COUNT(*) DESC
                """)
                breakdown = dict(cursor.fetchall())
                
                return {
                    'total_transactions': total,
                    'categorized': categorized,
                    'uncategorized': total - categorized,
                    'categories': breakdown
                }
        except Exception as e:
            logger.error(f"Failed to get category summary: {e}")
            return {}
    
    def update_transactions_with_locations(self) -> int:
        """Extract location information from existing transaction descriptions"""
        try:
            from .location_extractor import LocationExtractor
            extractor = LocationExtractor()
            
            # Get all transactions without location data
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, description 
                    FROM transactions 
                    WHERE location IS NULL OR location = ''
                """)
                transactions = cursor.fetchall()
                
                updated_count = 0
                
                for transaction_id, description in transactions:
                    location, cleaned_description = extractor.extract_location(description)
                    
                    if location:
                        # Update transaction with location and cleaned description
                        cursor.execute("""
                            UPDATE transactions 
                            SET location = ?, description = ?, updated_at = CURRENT_TIMESTAMP 
                            WHERE id = ?
                        """, (location, cleaned_description, transaction_id))
                        updated_count += 1
                    elif cleaned_description != description:
                        # Update just the cleaned description if no location found but description changed
                        cursor.execute("""
                            UPDATE transactions 
                            SET description = ?, updated_at = CURRENT_TIMESTAMP 
                            WHERE id = ?
                        """, (cleaned_description, transaction_id))
                
                conn.commit()
                logger.info(f"Updated {updated_count} transactions with location data")
                return updated_count
                
        except Exception as e:
            logger.error(f"Failed to update transactions with locations: {e}")
            return 0
    
    def search_transactions_with_location(self, search_term: str, location_filter: str) -> pd.DataFrame:
        """Search transactions with location filtering"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Search in both description and location fields
                query = """
                    SELECT id, date, description, location, amount, category, subcategory, 
                           merchant, account_type, statement_file
                    FROM transactions
                    WHERE (
                        description LIKE ? OR 
                        merchant LIKE ? OR
                        category LIKE ?
                    ) AND (
                        location LIKE ? OR location IS NULL
                    ) AND is_transfer = FALSE
                    ORDER BY date DESC
                """
                
                search_pattern = f"%{search_term}%"
                location_pattern = f"%{location_filter}%"
                
                df = pd.read_sql_query(
                    query, 
                    conn, 
                    params=[search_pattern, search_pattern, search_pattern, location_pattern]
                )
                
                return df
                
        except Exception as e:
            logger.error(f"Failed to search transactions with location: {e}")
            return pd.DataFrame()
    
    
    def mark_transfers(self) -> int:
        """Mark credit card payments and transfers"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Mark transactions that are transfers/payments
                transfer_patterns = [
                    '%PAYMENT%', '%PYMT%', '%AUTOPAY%', '%AUTOMATIC PAYMENT%',
                    '%TRANSFER%', '%TRSF%', '%DIRECT DEBIT%', '%PREAUTH%', '%PRE-AUTH%',
                    '%CREDIT CARD PAYMENT%', '%ONLINE PAYMENT%', '%PAYPAL TRANSFER%',
                    '%INTERAC TRANSFER%', '%E-TRANSFER%', '%FROM/DE ACCT%', '%TO/A ACCT%'
                ]
                
                marked_count = 0
                for pattern in transfer_patterns:
                    cursor.execute("""
                        UPDATE transactions 
                        SET is_transfer = TRUE, updated_at = CURRENT_TIMESTAMP 
                        WHERE description LIKE ? AND is_transfer = FALSE
                    """, (pattern,))
                    marked_count += cursor.rowcount
                
                # Also mark any positive amounts on credit cards as likely payments
                # (in case we missed converting any)
                cursor.execute("""
                    UPDATE transactions 
                    SET is_transfer = TRUE, updated_at = CURRENT_TIMESTAMP 
                    WHERE account_type = 'credit' AND amount < 0 AND is_transfer = FALSE
                """)
                marked_count += cursor.rowcount
                
                conn.commit()
                logger.info(f"Marked {marked_count} transactions as transfers")
                return marked_count
                
        except Exception as e:
            logger.error(f"Failed to mark transfers: {e}")
            return 0