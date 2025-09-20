#!/usr/bin/env python3
"""
Enhanced PDF processor with multiple extraction methods
For handling tricky PDFs that PyPDF2 can't process
"""

import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pdfplumber
    import PyPDF2
    from local_statement_processor import LocalStatementProcessor
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install pdfplumber PyPDF2")
    sys.exit(1)


class EnhancedPDFProcessor(LocalStatementProcessor):
    """Enhanced processor with multiple PDF extraction methods"""
    
    def extract_text_from_pdf(self, pdf_path: str, password: str = None) -> str:
        """Extract text using multiple methods"""
        
        # Method 1: Try pdfplumber first (better for complex layouts)
        try:
            print("🔧 Trying pdfplumber extraction...")
            with pdfplumber.open(pdf_path, password=password) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if text.strip():
                    print("✅ pdfplumber extraction successful!")
                    return text
        except Exception as e:
            print(f"⚠️  pdfplumber failed: {e}")
        
        # Method 2: Try PyPDF2 with password handling (our enhanced version)
        try:
            print("🔧 Trying PyPDF2 extraction...")
            return super().extract_text_from_pdf(pdf_path, password)
        except Exception as e:
            print(f"⚠️  PyPDF2 failed: {e}")
        
        # Method 3: Try pdfplumber with different settings
        try:
            print("🔧 Trying pdfplumber with alternative settings...")
            with pdfplumber.open(pdf_path, password=password) as pdf:
                text = ""
                for page in pdf.pages:
                    # Try different extraction strategies
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row:
                                    text += " ".join(str(cell) for cell in row if cell) + "\n"
                    
                    # Also try character-level extraction
                    chars = page.chars
                    if chars:
                        page_text = "".join(char['text'] for char in chars)
                        text += page_text + "\n"
                
                if text.strip():
                    print("✅ Alternative pdfplumber extraction successful!")
                    return text
        except Exception as e:
            print(f"⚠️  Alternative pdfplumber failed: {e}")
        
        print("❌ All PDF extraction methods failed")
        return ""


def main():
    """Main CLI with enhanced processing"""
    processor = EnhancedPDFProcessor()
    
    print("🏠 Enhanced PDF Statement Processor")
    print("   Multiple extraction methods for difficult PDFs")
    print("=" * 50)
    
    # Check Ollama
    if not processor.check_ollama():
        print("❌ Ollama not running!")
        print("   Start with: ollama serve")
        return
    
    # Show available models
    models = processor.get_available_models()
    if not models:
        print("❌ No models available!")
        print("   Install a model: ollama pull llama3.2")
        return
    
    print(f"✅ Ollama running with {len(models)} models:")
    for model in models[:3]:
        print(f"   • {model}")
    
    # Get arguments
    if len(sys.argv) < 2:
        print("\n📄 Usage:")
        print(f"   python {sys.argv[0]} <pdf_file> [account_type] [model] [password]")
        print("\n📁 Example:")
        print(f"   python {sys.argv[0]} encrypted_statement.pdf auto llama3.2 mypassword")
        return
    
    pdf_path = sys.argv[1]
    account_type = sys.argv[2] if len(sys.argv) > 2 else "auto"
    model = sys.argv[3] if len(sys.argv) > 3 else models[0]
    password = sys.argv[4] if len(sys.argv) > 4 else None
    
    # Process statement
    result = processor.process_statement(pdf_path, account_type, model, password)
    
    if result.get("success"):
        print(f"\n🎉 Success!")
        print(f"   📄 File: {result['statement_file']}")
        print(f"   🏦 Type: {result['account_type']}")
        print(f"   📊 Found: {result['transactions_found']} transactions")
        print(f"   💾 Added: {result['transactions_added']} new transactions")
        print(f"   📅 Date: {result['statement_date']}")
        print(f"\n🔍 View results: python view_database.py")
    else:
        print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
        if "raw_response" in result:
            print(f"\n🤖 Model response preview:\n{result['raw_response'][:300]}...")


if __name__ == "__main__":
    main()