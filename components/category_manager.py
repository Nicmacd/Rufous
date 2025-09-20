"""
Category Management System
Fixed categories with merchant learning capability
"""

import sqlite3
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class CategoryManager:
    """Manages fixed categories and learned merchant mappings"""
    
    # Fixed set of categories - never changes
    FIXED_CATEGORIES = {
        "Food & Dining": ["Restaurants", "Fast Food", "Coffee", "Groceries", "Alcohol"],
        "Transportation": ["Gas", "Public Transit", "Rideshare", "Parking", "Car Rental"],
        "Shopping": ["Retail", "Online", "Clothing", "Electronics", "Home & Garden"],
        "Bills & Utilities": ["Phone", "Internet", "Utilities", "Insurance", "Subscriptions"],
        "Health & Fitness": ["Medical", "Pharmacy", "Gym", "Wellness"],
        "Entertainment": ["Movies", "Gaming", "Events", "Hobbies", "Travel"],
        "Education": ["Courses", "Books", "Supplies"],
        "Personal Care": ["Beauty", "Haircare", "Spa"],
        "Financial": ["Banking Fees", "Investments", "Transfers"],
        "Other": ["Miscellaneous", "Unknown"]
    }
    
    def __init__(self, db_path: str):
        """Initialize category manager"""
        self.db_path = Path(db_path)
        self._initialize_category_tables()
    
    def _initialize_category_tables(self):
        """Create category management tables with proper connection handling"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                    # Simple settings for single-user app
                    conn.execute("PRAGMA synchronous=NORMAL")
                    
                    conn.executescript("""
                        -- Fixed categories table
                        CREATE TABLE IF NOT EXISTS fixed_categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category TEXT NOT NULL,
                            subcategory TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(category, subcategory)
                        );
                        
                        -- Learned merchant mappings
                        CREATE TABLE IF NOT EXISTS merchant_categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            merchant_pattern TEXT NOT NULL UNIQUE,
                            category TEXT NOT NULL,
                            subcategory TEXT,
                            confidence REAL DEFAULT 1.0,
                            times_used INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (category, subcategory) REFERENCES fixed_categories(category, subcategory)
                        );
                        
                        -- Uncategorized merchants needing attention
                        CREATE TABLE IF NOT EXISTS uncategorized_merchants (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            merchant TEXT NOT NULL UNIQUE,
                            description_sample TEXT,
                            transaction_count INTEGER DEFAULT 1,
                            total_amount REAL DEFAULT 0,
                            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        
                        -- Indexes for performance
                        CREATE INDEX IF NOT EXISTS idx_merchant_pattern ON merchant_categories(merchant_pattern);
                        CREATE INDEX IF NOT EXISTS idx_uncategorized_merchant ON uncategorized_merchants(merchant);
                    """)
                    
                    # Populate fixed categories
                    self._populate_fixed_categories(conn)
                    break  # Success, exit retry loop
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying in {attempt + 1} seconds... (attempt {attempt + 1}/{max_retries})")
                    import time
                    time.sleep(attempt + 1)
                    continue
                else:
                    logger.error(f"Failed to initialize category tables after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error initializing category tables: {e}")
                raise
    
    def _populate_fixed_categories(self, conn):
        """Populate the fixed categories table"""
        cursor = conn.cursor()
        
        for category, subcategories in self.FIXED_CATEGORIES.items():
            for subcategory in subcategories:
                cursor.execute(
                    "INSERT OR IGNORE INTO fixed_categories (category, subcategory) VALUES (?, ?)",
                    (category, subcategory)
                )
        
        conn.commit()
        logger.info("Fixed categories populated")
    
    def get_all_categories(self) -> Dict[str, List[str]]:
        """Get all available categories"""
        return self.FIXED_CATEGORIES.copy()
    
    def get_category_list(self) -> List[Tuple[str, str]]:
        """Get flat list of (category, subcategory) tuples"""
        categories = []
        for category, subcategories in self.FIXED_CATEGORIES.items():
            for subcategory in subcategories:
                categories.append((category, subcategory))
        return categories
    
    def learn_merchant_mapping(self, merchant_pattern: str, category: str, subcategory: str) -> bool:
        """Learn a new merchant -> category mapping"""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                conn.execute("PRAGMA busy_timeout=30000")
                cursor = conn.cursor()
                
                # Validate category exists
                cursor.execute(
                    "SELECT COUNT(*) FROM fixed_categories WHERE category = ? AND subcategory = ?",
                    (category, subcategory)
                )
                
                if cursor.fetchone()[0] == 0:
                    logger.error(f"Invalid category: {category}/{subcategory}")
                    return False
                
                # Insert or update merchant mapping
                cursor.execute("""
                    INSERT OR REPLACE INTO merchant_categories 
                    (merchant_pattern, category, subcategory, times_used, updated_at)
                    VALUES (?, ?, ?, 
                           COALESCE((SELECT times_used FROM merchant_categories WHERE merchant_pattern = ?), 0) + 1,
                           CURRENT_TIMESTAMP)
                """, (merchant_pattern, category, subcategory, merchant_pattern))
                
                # Remove from uncategorized list
                cursor.execute("DELETE FROM uncategorized_merchants WHERE merchant = ?", (merchant_pattern,))
                
                conn.commit()
                logger.info(f"Learned mapping: {merchant_pattern} -> {category}/{subcategory}")
                return True
                
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.warning(f"Database locked while learning merchant mapping: {e}")
                return False
            logger.error(f"Failed to learn merchant mapping: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to learn merchant mapping: {e}")
            return False
    
    def get_merchant_category(self, merchant: str, description: str = "") -> Tuple[Optional[str], Optional[str]]:
        """Get category for merchant using learned mappings"""
        if not merchant:
            return None, None
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Try exact match first
                cursor.execute("""
                    SELECT category, subcategory, confidence 
                    FROM merchant_categories 
                    WHERE merchant_pattern = ? 
                    ORDER BY confidence DESC, times_used DESC
                    LIMIT 1
                """, (merchant,))
                
                result = cursor.fetchone()
                if result:
                    # Update usage count
                    cursor.execute(
                        "UPDATE merchant_categories SET times_used = times_used + 1 WHERE merchant_pattern = ?",
                        (merchant,)
                    )
                    conn.commit()
                    return result[0], result[1]
                
                # Try partial matches
                cursor.execute("""
                    SELECT category, subcategory, confidence 
                    FROM merchant_categories 
                    WHERE ? LIKE '%' || merchant_pattern || '%' 
                    ORDER BY confidence DESC, times_used DESC, LENGTH(merchant_pattern) DESC
                    LIMIT 1
                """, (merchant,))
                
                result = cursor.fetchone()
                if result:
                    return result[0], result[1]
                
                return None, None
                
        except Exception as e:
            logger.error(f"Failed to get merchant category: {e}")
            return None, None
    
    def add_uncategorized_merchant(self, merchant: str, description: str = "", amount: float = 0):
        """Track uncategorized merchant for training - non-blocking"""
        # Skip if merchant is empty or too short
        if not merchant or len(merchant.strip()) < 2:
            return
        
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                cursor = conn.cursor()
                
                # Use a simpler, faster query
                cursor.execute("""
                    INSERT OR IGNORE INTO uncategorized_merchants 
                    (merchant, description_sample, transaction_count, total_amount, last_seen)
                    VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
                """, (merchant.strip(), description[:100], amount))  # Limit description length
                
                # If merchant already exists, update it
                if cursor.rowcount == 0:
                    cursor.execute("""
                        UPDATE uncategorized_merchants 
                        SET transaction_count = transaction_count + 1,
                            total_amount = total_amount + ?,
                            last_seen = CURRENT_TIMESTAMP
                        WHERE merchant = ?
                    """, (amount, merchant.strip()))
                
                conn.commit()
                
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                # Skip silently - this is not critical for the main workflow
                return
            logger.warning(f"Failed to add uncategorized merchant {merchant}: {e}")
        except Exception as e:
            logger.warning(f"Failed to add uncategorized merchant {merchant}: {e}")
    
    def get_uncategorized_merchants(self, limit: int = 50) -> List[Dict]:
        """Get merchants needing categorization"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT merchant, description_sample, transaction_count, total_amount, first_seen
                    FROM uncategorized_merchants 
                    ORDER BY transaction_count DESC, ABS(total_amount) DESC
                    LIMIT ?
                """, (limit,))
                
                results = cursor.fetchall()
                return [
                    {
                        'merchant': row[0],
                        'description_sample': row[1],
                        'transaction_count': row[2],
                        'total_amount': row[3],
                        'first_seen': row[4]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Failed to get uncategorized merchants: {e}")
            return []
    
    def get_learned_mappings(self) -> List[Dict]:
        """Get all learned merchant mappings"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT merchant_pattern, category, subcategory, times_used, created_at
                    FROM merchant_categories 
                    ORDER BY times_used DESC, created_at DESC
                """)
                
                results = cursor.fetchall()
                return [
                    {
                        'merchant_pattern': row[0],
                        'category': row[1],
                        'subcategory': row[2],
                        'times_used': row[3],
                        'created_at': row[4]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Failed to get learned mappings: {e}")
            return []
    
    def delete_merchant_mapping(self, merchant_pattern: str) -> bool:
        """Delete a learned merchant mapping"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM merchant_categories WHERE merchant_pattern = ?", (merchant_pattern,))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to delete merchant mapping: {e}")
            return False
    
    def get_categorization_stats(self) -> Dict:
        """Get categorization statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total transactions
                cursor.execute("SELECT COUNT(*) FROM transactions")
                total_transactions = cursor.fetchone()[0]
                
                # Categorized transactions
                cursor.execute("SELECT COUNT(*) FROM transactions WHERE category IS NOT NULL AND category != ''")
                categorized_transactions = cursor.fetchone()[0]
                
                # Learned mappings
                cursor.execute("SELECT COUNT(*) FROM merchant_categories")
                learned_mappings = cursor.fetchone()[0]
                
                # Uncategorized merchants
                cursor.execute("SELECT COUNT(*) FROM uncategorized_merchants")
                uncategorized_merchants = cursor.fetchone()[0]
                
                return {
                    'total_transactions': total_transactions,
                    'categorized_transactions': categorized_transactions,
                    'categorization_rate': (categorized_transactions / total_transactions * 100) if total_transactions > 0 else 0,
                    'learned_mappings': learned_mappings,
                    'uncategorized_merchants': uncategorized_merchants
                }
                
        except Exception as e:
            logger.error(f"Failed to get categorization stats: {e}")
            return {}
