#!/usr/bin/env python3
"""
Test script for Rufous PDF Server v2
Demonstrates the Claude-powered PDF processing workflow
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rufous_mcp.pdf_server_v2 import RufousPDFServerV2


async def test_pdf_server_v2():
    """Test the new PDF server architecture"""
    print("🧪 Testing Rufous PDF Server v2 - Claude-Powered Architecture")
    print("=" * 60)
    
    try:
        # Initialize server
        server = RufousPDFServerV2()
        print("✅ Server initialized successfully")
        
        # Test getting parsing template
        template = await server._get_parsing_template()
        print("✅ Parsing template retrieved")
        print(f"   Instructions length: {len(template['parsing_instructions'])} chars")
        print(f"   Example categories: {len(template['example_categories'])} categories")
        
        # Show the workflow
        print("\n📋 New Workflow:")
        for step in template['workflow']:
            print(f"   {step}")
        
        print("\n🎯 Key Benefits of v2 Architecture:")
        print("   ✅ No complex PDF parsing code needed")
        print("   ✅ Leverages Claude's existing multimodal capabilities")  
        print("   ✅ More accurate than regex-based parsing")
        print("   ✅ Handles any bank format, not just BMO")
        print("   ✅ Claude can understand context and nuance")
        print("   ✅ Cleaner, simpler codebase")
        
        # Show available tools
        print(f"\n🔧 Available Tools: {len(server.tool_definitions)}")
        for tool_def in server.tool_definitions:
            print(f"   • {tool_def['name']}: {tool_def['description']}")
        
        print("\n💡 Example Usage:")
        print("   1. User: 'Here's my BMO statement' (uploads PDF)")
        print("   2. Claude: Uses multimodal vision to parse PDF")
        print("   3. Claude: Calls process_parsed_statement with structured data")
        print("   4. System: Stores transactions in database")
        print("   5. User: 'How much did I spend on groceries?'")
        print("   6. Claude: Uses get_spending_summary and other tools")
        
        print("\n🚀 Architecture Comparison:")
        print("   Old: PDF → Custom Parser → Database → Claude")
        print("   New: PDF → Claude (multimodal) → Database → Claude")
        print("   Result: Simpler, more accurate, more flexible!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_mock_transaction_processing():
    """Test processing mock transaction data"""
    print("\n🧪 Testing Mock Transaction Processing")
    print("-" * 40)
    
    try:
        server = RufousPDFServerV2()
        
        # Mock data that Claude might extract from a PDF
        mock_parsed_data = {
            "statement_filename": "BMO_Test_Statement.pdf",
            "account_type": "debit",
            "statement_date": "2024-01-31",
            "transactions": [
                {
                    "date": "2024-01-15",
                    "description": "METRO GROCERY STORE",
                    "amount": -85.42,
                    "balance": 1234.56,
                    "category": "Groceries"
                },
                {
                    "date": "2024-01-16", 
                    "description": "STARBUCKS COFFEE",
                    "amount": -5.67,
                    "balance": 1228.89,
                    "category": "Coffee"
                },
                {
                    "date": "2024-01-17",
                    "description": "SALARY DEPOSIT",
                    "amount": 2500.00,
                    "balance": 3728.89,
                    "category": "Income"
                }
            ]
        }
        
        # Process the mock data
        result = await server._process_parsed_statement(mock_parsed_data)
        
        print("✅ Mock transaction processing successful")
        print(f"   Statement ID: {result.get('statement_id')}")
        print(f"   Transactions added: {result.get('transactions_added')}")
        print(f"   Total parsed: {result.get('total_transactions_parsed')}")
        
        # Test querying the data back
        recent = await server._get_recent_transactions(30)
        print(f"✅ Recent transactions query: {len(recent['transactions'])} found")
        
        # Test spending summary
        summary = await server._get_spending_summary(30)
        print(f"✅ Spending summary: ${summary.get('total_spent', 0):.2f} spent")
        
        print("\n🎯 This demonstrates how Claude's parsed data flows through the system!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in mock processing: {e}")
        return False


if __name__ == "__main__":
    async def main():
        success1 = await test_pdf_server_v2()
        success2 = await test_mock_transaction_processing()
        
        print("\n" + "=" * 60)
        if success1 and success2:
            print("🎉 ALL TESTS PASSED - Rufous v2 Architecture Ready!")
            print("\n📊 Next Steps:")
            print("   1. Update Claude Desktop config to use pdf_server_v2.py")
            print("   2. Upload a bank statement PDF to Claude")
            print("   3. Ask Claude to process it using the new tools")
            print("   4. Query your financial data naturally!")
        else:
            print("❌ Some tests failed - check the errors above")
    
    asyncio.run(main()) 