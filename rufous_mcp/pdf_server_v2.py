#!/usr/bin/env python3
"""
Rufous PDF Processing MCP Server v2
Leverages Claude's multimodal capabilities for PDF parsing
"""

import asyncio
import json
import logging
import sys
import os
from typing import Any, Dict, List
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import (
    ServerCapabilities,
    ToolsCapability,
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)

from rufous_mcp.config import Config
from rufous_mcp.database import RufousDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RufousPDFServerV2:
    """MCP server that leverages Claude's PDF parsing capabilities"""
    
    def __init__(self):
        """Initialize the PDF processing server"""
        self.config = Config()
        pdf_config = self.config.get_pdf_config()
        
        # Initialize database
        self.database = RufousDatabase(pdf_config.get('database_path'))
        
        # Create statements directory
        self.statements_dir = Path(pdf_config['statements_directory'])
        self.statements_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize MCP server
        self.server = Server("rufous-pdf-v2")
        
        # Tool definitions - Claude does the parsing, we do the storage
        self.tool_definitions = [
            {
                "name": "process_parsed_statement",
                "description": "Store parsed bank statement data after Claude has extracted it from PDF",
                "inputSchema": {
                    "type": "object", 
                    "properties": {
                        "statement_filename": {
                            "type": "string",
                            "description": "Original PDF filename"
                        },
                        "account_type": {
                            "type": "string",
                            "enum": ["debit", "credit"],
                            "description": "Type of account (debit or credit)"
                        },
                        "statement_date": {
                            "type": "string",
                            "description": "Statement date in YYYY-MM-DD format"
                        },
                        "transactions": {
                            "type": "array",
                            "description": "Array of transaction objects parsed by Claude",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "date": {"type": "string", "description": "Transaction date YYYY-MM-DD"},
                                    "description": {"type": "string", "description": "Transaction description"},
                                    "amount": {"type": "number", "description": "Transaction amount (negative for debits)"},
                                    "balance": {"type": "number", "description": "Account balance after transaction (optional)"},
                                    "category": {"type": "string", "description": "Transaction category (optional)"}
                                },
                                "required": ["date", "description", "amount"]
                            }
                        }
                    },
                    "required": ["statement_filename", "account_type", "transactions"]
                }
            },
            {
                "name": "get_parsing_template",
                "description": "Get a template for Claude to use when parsing bank statements",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_recent_transactions",
                "description": "Get recent transactions with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back (default: 30)",
                            "default": 30
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by category (optional)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of transactions to return (default: 50)",
                            "default": 50
                        }
                    }
                }
            },
            {
                "name": "get_spending_summary",
                "description": "Get spending summary for a specific time period",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer", 
                            "description": "Number of days to analyze (default: 30)",
                            "default": 30
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by specific category (optional)"
                        }
                    }
                }
            },
            {
                "name": "search_transactions",
                "description": "Search transactions by description or other criteria",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Term to search for in transaction descriptions"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 50)",
                            "default": 50
                        }
                    },
                    "required": ["search_term"]
                }
            },
            {
                "name": "get_category_breakdown",
                "description": "Get spending breakdown by category",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Number of days to analyze (default: 30)",
                            "default": 30
                        }
                    }
                }
            },
            {
                "name": "categorize_transactions",
                "description": "Get uncategorized transactions for Claude to categorize",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of transactions to return (default: 20)",
                            "default": 20
                        }
                    }
                }
            },
            {
                "name": "update_transaction_categories",
                "description": "Update categories for specific transactions",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category_updates": {
                            "type": "array",
                            "description": "Array of transaction ID and category pairs",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "transaction_id": {"type": "integer"},
                                    "category": {"type": "string"}
                                },
                                "required": ["transaction_id", "category"]
                            }
                        }
                    },
                    "required": ["category_updates"]
                }
            }
        ]
        
        # Setup handlers
        self._setup_handlers()
        
        logger.info("Rufous PDF Server v2 initialized - leveraging Claude's multimodal capabilities")
    
    def _setup_handlers(self):
        """Setup MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools():
            """Return available tools"""
            logger.info("PDF Server v2: Listing tools")
            
            tools = []
            for tool_def in self.tool_definitions:
                tool = Tool(
                    name=tool_def["name"],
                    description=tool_def["description"],
                    inputSchema=tool_def["inputSchema"]
                )
                tools.append(tool)
            
            logger.info(f"PDF Server v2: Returning {len(tools)} tools")
            return tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]):
            """Handle tool execution"""
            logger.info(f"PDF Server v2: Executing tool '{name}' with arguments: {arguments}")
            
            try:
                if name == "get_parsing_template":
                    result = await self._get_parsing_template()
                    
                elif name == "process_parsed_statement":
                    result = await self._process_parsed_statement(arguments)
                    
                elif name == "get_recent_transactions":
                    days = arguments.get("days", 30)
                    category = arguments.get("category")
                    limit = arguments.get("limit", 50)
                    result = await self._get_recent_transactions(days, category, limit)
                
                elif name == "get_spending_summary":
                    days = arguments.get("days", 30)
                    category = arguments.get("category")  
                    result = await self._get_spending_summary(days, category)
                
                elif name == "search_transactions":
                    search_term = arguments.get("search_term", "")
                    limit = arguments.get("limit", 50)
                    result = await self._search_transactions(search_term, limit)
                
                elif name == "get_category_breakdown":
                    days = arguments.get("days", 30)
                    result = await self._get_category_breakdown(days)
                
                elif name == "categorize_transactions":
                    limit = arguments.get("limit", 20)
                    result = await self._get_uncategorized_transactions(limit)
                
                elif name == "update_transaction_categories":
                    category_updates = arguments.get("category_updates", [])
                    result = await self._update_transaction_categories(category_updates)
                
                else:
                    return {
                        "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                        "isError": True
                    }
                
                return {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
                    "isError": False
                }
                    
            except Exception as e:
                logger.error(f"PDF Server v2: Tool execution error: {e}")
                return {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True
                }
    
    async def _get_parsing_template(self) -> Dict[str, Any]:
        """Provide template for Claude to parse bank statements"""
        return {
            "parsing_instructions": """
When you receive a bank statement PDF, please extract the transaction data and format it like this:

Use the process_parsed_statement tool with this structure:
{
  "statement_filename": "BMO_Statement_2024-01.pdf",
  "account_type": "debit" or "credit", 
  "statement_date": "2024-01-31",
  "transactions": [
    {
      "date": "2024-01-15",
      "description": "GROCERY STORE PURCHASE",
      "amount": -45.67,
      "balance": 1234.56,
      "category": "Groceries"
    },
    {
      "date": "2024-01-16", 
      "description": "SALARY DEPOSIT",
      "amount": 2500.00,
      "balance": 3734.56,
      "category": "Income"
    }
  ]
}

Key points:
- Use negative amounts for money going out (debits/expenses)
- Use positive amounts for money coming in (deposits/income)
- Include balance if visible on the statement
- Suggest categories based on transaction descriptions
- Skip duplicate transactions or totals/summary lines
- Focus on actual transactions, not account summaries
            """,
            "example_categories": [
                "Groceries", "Dining", "Transportation", "Utilities", 
                "Entertainment", "Shopping", "Healthcare", "Income", 
                "Transfers", "Bills", "Gas", "Coffee", "Other"
            ],
            "workflow": [
                "1. User uploads/shows you a bank statement PDF",
                "2. You analyze the PDF and extract transaction data",
                "3. You call process_parsed_statement with the formatted data",
                "4. The system stores it and confirms success",
                "5. User can then query their financial data using other tools"
            ]
        }
    
    async def _process_parsed_statement(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Process statement data parsed by Claude"""
        try:
            statement_filename = arguments["statement_filename"]
            account_type = arguments["account_type"]
            statement_date_str = arguments.get("statement_date")
            transactions_data = arguments["transactions"]
            
            # Check if already processed
            if self.database.is_statement_processed(statement_filename):
                return {
                    "status": "already_processed",
                    "message": f"Statement {statement_filename} has already been processed",
                    "filename": statement_filename
                }
            
            # Parse statement date
            statement_date = None
            if statement_date_str:
                from datetime import datetime
                try:
                    statement_date = datetime.strptime(statement_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            # Process transactions
            processed_transactions = []
            for txn_data in transactions_data:
                try:
                    # Parse transaction date
                    txn_date = datetime.strptime(txn_data["date"], '%Y-%m-%d').date()
                    
                    # Build transaction record
                    transaction = {
                        'date': txn_date,
                        'description': txn_data["description"].strip(),
                        'amount': float(txn_data["amount"]),
                        'balance': float(txn_data.get("balance")) if txn_data.get("balance") else None,
                        'account_type': account_type,
                        'category': txn_data.get("category"),
                        'is_transfer': self._detect_transfer(txn_data["description"]),
                        'statement_file': statement_filename
                    }
                    
                    processed_transactions.append(transaction)
                    
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid transaction: {txn_data} - Error: {e}")
                    continue
            
            if not processed_transactions:
                raise ValueError("No valid transactions found in parsed data")
            
            # Use the first transaction date if no statement date provided
            if not statement_date and processed_transactions:
                statement_date = processed_transactions[0]['date']
            
            # Store statement record
            statement_id = self.database.add_statement(
                filename=statement_filename,
                statement_date=statement_date,
                account_type=account_type,
                transaction_count=len(processed_transactions)
            )
            
            # Store transactions
            added_count = self.database.add_transactions(processed_transactions)
            
            return {
                "status": "success",
                "message": f"Successfully processed statement {statement_filename}",
                "statement_id": statement_id,
                "transactions_added": added_count,
                "total_transactions_parsed": len(processed_transactions),
                "statement_date": statement_date,
                "account_type": account_type,
                "filename": statement_filename
            }
            
        except Exception as e:
            logger.error(f"Error processing parsed statement: {e}")
            raise
    
    def _detect_transfer(self, description: str) -> bool:
        """Simple transfer detection based on keywords"""
        transfer_keywords = [
            'TRANSFER', 'E-TRANSFER', 'INTERAC', 'ONLINE TRANSFER',
            'CREDIT CARD PAYMENT', 'CC PAYMENT', 'PAYMENT TO'
        ]
        
        desc_upper = description.upper()
        return any(keyword in desc_upper for keyword in transfer_keywords)
    
    async def _get_recent_transactions(self, days: int, category: str = None, limit: int = 50) -> Dict[str, Any]:
        """Get recent transactions"""
        from datetime import date, timedelta
        
        start_date = date.today() - timedelta(days=days)
        transactions = self.database.get_transactions(
            start_date=start_date,
            category=category,
            limit=limit
        )
        
        return {
            "transactions": transactions,
            "total_count": len(transactions),
            "date_range": f"Last {days} days",
            "start_date": start_date,
            "category_filter": category
        }
    
    async def _get_spending_summary(self, days: int, category: str = None) -> Dict[str, Any]:
        """Get spending summary"""
        from datetime import date, timedelta
        
        start_date = date.today() - timedelta(days=days)
        summary = self.database.get_spending_summary(
            start_date=start_date,
            category=category
        )
        
        summary.update({
            "date_range": f"Last {days} days",
            "start_date": start_date,
            "category_filter": category
        })
        
        return summary
    
    async def _search_transactions(self, search_term: str, limit: int = 50) -> Dict[str, Any]:
        """Search transactions"""
        transactions = self.database.search_transactions(search_term, limit)
        
        return {
            "transactions": transactions,
            "total_count": len(transactions),
            "search_term": search_term,
            "limit": limit
        }
    
    async def _get_category_breakdown(self, days: int) -> Dict[str, Any]:
        """Get category breakdown"""
        from datetime import date, timedelta
        
        start_date = date.today() - timedelta(days=days)
        breakdown = self.database.get_category_breakdown(start_date=start_date)
        
        return {
            "categories": breakdown,
            "date_range": f"Last {days} days",
            "start_date": start_date,
            "total_categories": len(breakdown)
        }
    
    async def _get_uncategorized_transactions(self, limit: int = 20) -> Dict[str, Any]:
        """Get uncategorized transactions for Claude to categorize"""
        transactions = self.database.get_uncategorized_transactions(limit)
        
        return {
            "uncategorized_transactions": transactions,
            "total_count": len(transactions),
            "message": "Analyze these transaction descriptions and suggest appropriate categories.",
            "suggested_categories": [
                "Groceries", "Dining", "Transportation", "Utilities", 
                "Entertainment", "Shopping", "Healthcare", "Income", 
                "Transfers", "Bills", "Gas", "Coffee", "Other"
            ]
        }
    
    async def _update_transaction_categories(self, category_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update categories for specific transactions"""
        updated_count = 0
        
        for update in category_updates:
            try:
                transaction_id = update["transaction_id"]
                category = update["category"]
                
                self.database.update_transaction_category(transaction_id, category)
                updated_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to update transaction {update}: {e}")
                continue
        
        return {
            "status": "success",
            "updated_count": updated_count,
            "total_requested": len(category_updates),
            "message": f"Updated categories for {updated_count} transactions"
        }


async def main():
    """Main server entry point"""
    try:
        server_instance = RufousPDFServerV2()
        
        # Get stdio streams
        read_stream, write_stream = await stdio_server()
        
        # Run the server
        await server_instance.server.run(
            read_stream, 
            write_stream,
            InitializationOptions(
                server_name="rufous-pdf-v2",
                server_version="2.0.0",
                capabilities=ServerCapabilities(tools=ToolsCapability())
            )
        )
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 