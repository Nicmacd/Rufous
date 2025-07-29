#!/usr/bin/env python3
"""
Simple database viewer for Rufous database
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def view_database():
    """View contents of the Rufous database"""
    
    # Database path (same as default in database.py)
    db_path = Path.home() / "rufous_data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        return
    
    print(f"📊 Viewing Rufous Database: {db_path}")
    print("=" * 60)
    
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.row_factory = sqlite3.Row  # Enable column names
            cursor = conn.cursor()
            
            # Get database info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"📋 Tables found: {[table[0] for table in tables]}")
            print()
            
            # View statements table
            print("📄 STATEMENTS:")
            cursor.execute("SELECT * FROM statements ORDER BY statement_date DESC")
            statements = cursor.fetchall()
            
            if statements:
                print(f"   Count: {len(statements)}")
                for stmt in statements:
                    print(f"   📋 {stmt['filename']} ({stmt['account_type']}) - {stmt['statement_date']} - {stmt['transaction_count']} transactions")
            else:
                print("   No statements found")
            print()
            
            # View transactions table
            print("💰 TRANSACTIONS:")
            cursor.execute("SELECT COUNT(*) as count FROM transactions")
            count = cursor.fetchone()['count']
            print(f"   Total count: {count}")
            
            if count > 0:
                # Show recent transactions
                cursor.execute("""
                    SELECT date, description, amount, account_type, category, statement_file 
                    FROM transactions 
                    ORDER BY date DESC, id DESC 
                    LIMIT 10
                """)
                recent = cursor.fetchall()
                
                print("   📅 Recent transactions (last 10):")
                for txn in recent:
                    category = txn['category'] or 'Uncategorized'
                    print(f"     {txn['date']} | ${txn['amount']:>8.2f} | {category:<15} | {txn['description'][:40]}")
                
                # Show summary by account type
                cursor.execute("""
                    SELECT account_type, COUNT(*) as count, SUM(amount) as total
                    FROM transactions 
                    GROUP BY account_type
                """)
                summary = cursor.fetchall()
                
                print("   📊 Summary by account type:")
                for row in summary:
                    print(f"     {row['account_type']}: {row['count']} transactions, Total: ${row['total']:,.2f}")
                
                # Show summary by statement
                cursor.execute("""
                    SELECT statement_file, COUNT(*) as count, MIN(date) as from_date, MAX(date) as to_date
                    FROM transactions 
                    GROUP BY statement_file
                    ORDER BY MAX(date) DESC
                """)
                by_statement = cursor.fetchall()
                
                print("   📄 Summary by statement:")
                for row in by_statement:
                    print(f"     {row['statement_file']}: {row['count']} transactions ({row['from_date']} to {row['to_date']})")
            else:
                print("   No transactions found")
            print()
            
            # View categories table
            print("🏷️  CATEGORIES:")
            cursor.execute("SELECT * FROM categories ORDER BY name")
            categories = cursor.fetchall()
            
            if categories:
                print(f"   Count: {len(categories)}")
                for cat in categories:
                    keywords = cat['keywords'] or 'No keywords'
                    print(f"   📂 {cat['name']} - Keywords: {keywords}")
            else:
                print("   No custom categories found")
            
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    view_database() 