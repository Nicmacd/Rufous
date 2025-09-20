#!/usr/bin/env python3
"""
Local PDF Statement Processor
Processes bank statements using local open source models (via Ollama)
No data leaves your computer - complete privacy
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
    import PyPDF2
    from components.database import RufousDatabase
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install PyPDF2 requests")
    sys.exit(1)


class LocalStatementProcessor:
    """Process bank statements using local Ollama models"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        # Use the same database as the web app
        self.database = RufousDatabase()
        
    def check_ollama(self) -> bool:
        """Check if Ollama is running and available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
            
    def get_available_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [model['name'] for model in models]
            return []
        except:
            return []
    
    def extract_text_from_pdf(self, pdf_path: str, password: str = None) -> str:
        """Extract text from PDF using PyPDF2, handling encrypted PDFs"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Handle encrypted PDFs
                if pdf_reader.is_encrypted:
                    if not password:
                        # Try common bank statement passwords
                        common_passwords = ["", "password", "123456", "000000"]
                        
                        # Also try last 4 digits of common patterns
                        # You might want to customize these based on your bank
                        
                        decrypted = False
                        for pwd in common_passwords:
                            try:
                                if pdf_reader.decrypt(pwd):
                                    print(f"✅ PDF decrypted successfully")
                                    decrypted = True
                                    break
                            except:
                                continue
                        
                        if not decrypted:
                            print("🔒 PDF is password protected!")
                            user_password = input("Enter PDF password (or press Enter to skip): ").strip()
                            if user_password:
                                try:
                                    if pdf_reader.decrypt(user_password):
                                        print("✅ PDF decrypted with user password")
                                        decrypted = True
                                except:
                                    pass
                        
                        if not decrypted:
                            return ""
                    else:
                        # Use provided password
                        if not pdf_reader.decrypt(password):
                            print(f"❌ Failed to decrypt PDF with provided password")
                            return ""
                
                # Extract text from all pages
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                    
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ""
        return text
    
    def query_ollama(self, prompt: str, model: str = "llama3.2") -> str:
        """Query local Ollama model"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120  # 2 minute timeout for processing
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                print(f"Ollama error: {response.status_code}")
                return ""
        except Exception as e:
            print(f"Error querying Ollama: {e}")
            return ""
    
    def create_parsing_prompt(self, pdf_text: str, account_type: str = "auto") -> str:
        """Create prompt for transaction extraction"""
        return f"""
You are a financial data extraction expert. Extract transaction data from this bank statement text.

ACCOUNT TYPE: {account_type} (or detect automatically if 'auto')

IMPORTANT RULES:
1. Extract ONLY actual transactions (not headers, summaries, or advertisements)
2. For amounts: negative = money out, positive = money in (follow bank statement convention)
3. Include running balance if shown
4. Format dates as YYYY-MM-DD
5. Clean up merchant names (remove extra codes/addresses when possible)

EXTRACT TO JSON FORMAT:
{{
  "account_type": "debit" or "credit",
  "statement_date": "YYYY-MM-DD",
  "transactions": [
    {{
      "date": "YYYY-MM-DD",
      "description": "Cleaned merchant/transaction name",
      "amount": -123.45,
      "balance": 1234.56
    }}
  ]
}}

BANK STATEMENT TEXT:
{pdf_text[:8000]}  

Return only valid JSON, no other text:"""

    def parse_transactions(self, pdf_path: str, account_type: str = "auto", model: str = "llama3.2", password: str = None) -> Dict[str, Any]:
        """Parse transactions from PDF using local LLM"""
        print(f"📄 Extracting text from {pdf_path}...")
        pdf_text = self.extract_text_from_pdf(pdf_path, password)
        
        if not pdf_text.strip():
            return {"error": "Could not extract text from PDF"}
        
        print(f"🤖 Processing with {model} model...")
        prompt = self.create_parsing_prompt(pdf_text, account_type)
        response = self.query_ollama(prompt, model)
        
        if not response:
            return {"error": "No response from local model"}
        
        # Try to extract JSON from response
        try:
            # Find JSON in response (models sometimes add extra text)
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                return {"error": "Could not find valid JSON in response", "raw_response": response}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {e}", "raw_response": response}
    
    def process_statement(self, pdf_path: str, account_type: str = "auto", model: str = "llama3.2", password: str = None) -> Dict[str, Any]:
        """Process a complete statement and store in database"""
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            return {"error": f"File not found: {pdf_path}"}
        
        print(f"🏦 Processing statement: {pdf_file.name}")
        
        # Parse transactions
        result = self.parse_transactions(pdf_path, account_type, model, password)
        
        if "error" in result:
            return result
        
        # Store in database
        try:
            transactions = result.get('transactions', [])
            if not transactions:
                return {"error": "No transactions found"}
            
            # Prepare transactions for database
            processed_transactions = []
            for txn in transactions:
                processed_transactions.append({
                    'date': txn['date'],
                    'description': txn['description'],
                    'amount': txn['amount'],
                    'balance': txn.get('balance'),
                    'account_type': result.get('account_type', account_type),
                    'statement_file': pdf_file.name,
                    'category': None,
                    'is_transfer': False
                })
            
            # Add statement record
            statement_date = datetime.strptime(result.get('statement_date', transactions[0]['date']), '%Y-%m-%d').date()
            self.database.add_statement(
                filename=pdf_file.name,
                statement_date=statement_date,
                account_type=result.get('account_type', account_type),
                transaction_count=len(processed_transactions)
            )
            
            # Add transactions
            added_count = self.database.add_transactions(processed_transactions)
            
            return {
                "success": True,
                "statement_file": pdf_file.name,
                "account_type": result.get('account_type', account_type),
                "transactions_found": len(transactions),
                "transactions_added": added_count,
                "statement_date": result.get('statement_date')
            }
            
        except Exception as e:
            return {"error": f"Database error: {e}"}


def main():
    """Main CLI interface"""
    processor = LocalStatementProcessor()
    
    print("🏠 Local PDF Statement Processor")
    print("=" * 40)
    
    # Check Ollama
    if not processor.check_ollama():
        print("❌ Ollama not running!")
        print("\n📥 Install Ollama:")
        print("   1. Download from: https://ollama.ai")
        print("   2. Install and run: ollama serve")
        print("   3. Install a model: ollama pull llama3.2")
        return
    
    # Show available models
    models = processor.get_available_models()
    if not models:
        print("❌ No models available!")
        print("   Install a model: ollama pull llama3.2")
        return
    
    print(f"✅ Ollama running with {len(models)} models:")
    for model in models[:5]:  # Show first 5
        print(f"   • {model}")
    
    # Get PDF file
    if len(sys.argv) < 2:
        print("\n📄 Usage:")
        print(f"   python {sys.argv[0]} <pdf_file> [account_type] [model] [password]")
        print("\n   account_type: debit, credit, or auto (default)")
        print(f"   model: {models[0]} (default)")
        print("   password: PDF password if encrypted")
        print("\n📁 Examples:")
        print(f"   python {sys.argv[0]} ~/Downloads/statement.pdf credit llama3.2")
        print(f"   python {sys.argv[0]} encrypted.pdf auto llama3.2 mypassword")
        return
    
    pdf_path = sys.argv[1]
    account_type = sys.argv[2] if len(sys.argv) > 2 else "auto"
    model = sys.argv[3] if len(sys.argv) > 3 else models[0]
    password = sys.argv[4] if len(sys.argv) > 4 else None
    
    # Process statement
    result = processor.process_statement(pdf_path, account_type, model, password)
    
    if result.get("success"):
        print(f"\n✅ Success!")
        print(f"   📄 File: {result['statement_file']}")
        print(f"   🏦 Type: {result['account_type']}")
        print(f"   📊 Found: {result['transactions_found']} transactions")
        print(f"   💾 Added: {result['transactions_added']} new transactions")
        print(f"   📅 Date: {result['statement_date']}")
        print(f"\n🔍 View results: python view_database.py")
    else:
        print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
        if "raw_response" in result:
            print(f"\n🤖 Model response:\n{result['raw_response'][:500]}...")


if __name__ == "__main__":
    main()