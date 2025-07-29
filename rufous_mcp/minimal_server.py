#!/usr/bin/env python3
"""
Minimal Rufous Database Server - Based on working simple_server.py pattern
"""

import asyncio
import json
import logging
import sys
import os
from typing import Any, Dict, List

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp import types
from mcp.types import (
    ServerCapabilities,
    ToolsCapability,
    Tool,
)

from rufous_mcp.config import Config
from rufous_mcp.database import RufousDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MinimalRufousServer:
    """Minimal MCP server following the exact working pattern"""
    
    def __init__(self):
        """Initialize the minimal server"""
        self.config = Config()
        pdf_config = self.config.get_pdf_config()
        
        # Initialize database
        self.database = RufousDatabase(pdf_config.get('database_path'))
        
        # Initialize MCP server
        self.server = Server("rufous-minimal")
        
        # Tool definitions - minimal set
        self.tool_definitions = [
            {
                "name": "store_transactions",
                "description": "Store transaction data that Claude has extracted",
                "inputSchema": {
                    "type": "object", 
                    "properties": {
                        "statement_filename": {"type": "string"},
                        "account_type": {"type": "string", "enum": ["debit", "credit"]},
                        "statement_date": {"type": "string"},
                        "transactions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "date": {"type": "string"},
                                    "description": {"type": "string"},
                                    "amount": {"type": "number"},
                                    "balance": {"type": "number"},
                                    "category": {"type": "string"}
                                },
                                "required": ["date", "description", "amount"]
                            }
                        }
                    },
                    "required": ["statement_filename", "account_type", "transactions"]
                }
            },
            {
                "name": "get_transactions", 
                "description": "Get transactions from database",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "default": 30},
                        "category": {"type": "string"},
                        "search_term": {"type": "string"},
                        "limit": {"type": "integer", "default": 100}
                    }
                }
            }
        ]
        
        # Setup handlers using the exact working pattern
        self._setup_handlers()
        
        logger.info("Rufous MCP Server initialized")
    
    def _create_success_result(self, data: Any, message: str = None) -> types.CallToolResult:
        """Create a successful tool result following exact MCP documentation pattern"""
        if isinstance(data, dict) or isinstance(data, list):
            content_text = json.dumps(data, indent=2, default=str)
        else:
            content_text = str(data)
        
        if message:
            content_text = f"{message}\n\n{content_text}"
        
        # Create TextContent first as a separate object to avoid tuple conversion
        text_content = types.TextContent(
            type="text",
            text=content_text
        )
        
        # Create CallToolResult with explicit keyword arguments to prevent tuple formation
        return types.CallToolResult(
            content=[text_content]
            # Note: isError defaults to False, meta defaults to None, structuredContent defaults to None
        )
    
    def _create_error_result(self, error: str) -> types.CallToolResult:
        """Create an error tool result following exact MCP documentation pattern"""
        # Create TextContent first as a separate object to avoid tuple conversion
        text_content = types.TextContent(
            type="text",
            text=f"Error: {error}"
        )
        
        # Create CallToolResult with explicit keyword arguments - isError first as per docs
        return types.CallToolResult(
            isError=True,
            content=[text_content]
        )
    
    def _setup_handlers(self):
        """Setup MCP server handlers using the working pattern from simple_server.py"""
        
        @self.server.list_tools()
        async def handle_list_tools():
            """List available tools"""
            try:
                tools = []
                
                for tool_def in self.tool_definitions:
                    tool = Tool(
                        name=tool_def["name"],
                        description=tool_def["description"],
                        inputSchema=tool_def["inputSchema"]
                    )
                    tools.append(tool)
                
                logger.info(f"Listed {len(tools)} available tools")
                return tools
                
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                raise
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            """Handle tool calls"""
            try:
                logger.info(f"Executing tool '{name}'")
                
                if name == "store_transactions":
                    # Process the store transactions request
                    statement_filename = arguments.get("statement_filename", "")
                    account_type = arguments.get("account_type", "debit")
                    statement_date_str = arguments.get("statement_date", "")
                    transactions_data = arguments.get("transactions", [])
                    
                    # Simple processing - just store what Claude gives us
                    result = await self._process_store_request(
                        statement_filename, account_type, statement_date_str, transactions_data
                    )
                    
                    return self._create_success_result(result)
                
                elif name == "get_transactions":
                    days = arguments.get("days", 30)
                    category = arguments.get("category")
                    search_term = arguments.get("search_term") 
                    limit = arguments.get("limit", 100)
                    
                    result = await self._process_get_request(days, category, search_term, limit)
                    
                    return self._create_success_result(result)
                
                else:
                    return self._create_error_result(f"Unknown tool: {name}")
                    
            except Exception as e:
                logger.error(f"Tool execution error for '{name}': {e}")
                return self._create_error_result(str(e))
    
    async def _process_store_request(self, statement_filename: str, account_type: str, 
                                   statement_date_str: str, transactions_data: list) -> dict:
        """Process store transactions request"""
        try:
            # Check if already processed
            if self.database.is_statement_processed(statement_filename):
                return {
                    "status": "already_processed",
                    "message": f"Statement {statement_filename} already exists",
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
                    from datetime import datetime
                    txn_date = datetime.strptime(txn_data["date"], '%Y-%m-%d').date()
                    
                    transaction = {
                        'date': txn_date,
                        'description': txn_data["description"].strip(),
                        'amount': float(txn_data["amount"]),
                        'balance': float(txn_data.get("balance")) if txn_data.get("balance") else None,
                        'account_type': account_type,
                        'category': txn_data.get("category"),
                        'is_transfer': 'TRANSFER' in txn_data["description"].upper(),
                        'statement_file': statement_filename
                    }
                    processed_transactions.append(transaction)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid transaction: {txn_data} - Error: {e}")
                    continue
            
            if not processed_transactions:
                return {"status": "error", "message": "No valid transactions found"}
            
            # Use first transaction date if no statement date
            if not statement_date and processed_transactions:
                statement_date = processed_transactions[0]['date']
            
            # Store in database
            statement_id = self.database.add_statement(
                filename=statement_filename,
                statement_date=statement_date,
                account_type=account_type,
                transaction_count=len(processed_transactions)
            )
            
            added_count = self.database.add_transactions(processed_transactions)
            
            return {
                "status": "success",
                "message": f"Stored {added_count} transactions from {statement_filename}",
                "statement_id": statement_id,
                "transactions_stored": added_count,
                "statement_date": statement_date,
                "account_type": account_type
            }
            
        except Exception as e:
            logger.error(f"Error processing store request: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _process_get_request(self, days: int, category: str, search_term: str, limit: int) -> dict:
        """Process get transactions request"""
        try:
            from datetime import date, timedelta
            
            # Simple retrieval logic
            if search_term:
                transactions = self.database.search_transactions(search_term, limit)
            else:
                start_date = date.today() - timedelta(days=days) if days else None
                transactions = self.database.get_transactions(
                    start_date=start_date,
                    category=category,
                    limit=limit
                )
            
            return {
                "status": "success",
                "transactions": transactions,
                "count": len(transactions),
                "message": f"Retrieved {len(transactions)} transactions"
            }
            
        except Exception as e:
            logger.error(f"Error processing get request: {e}")
            return {"status": "error", "message": str(e)}


async def main():
    """Main server entry point - exact pattern from simple_server.py"""
    try:
        server_instance = MinimalRufousServer()
        
        async with stdio_server() as (read_stream, write_stream):
            await server_instance.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="rufous-minimal",
                    server_version="1.0.0",
                    capabilities=ServerCapabilities(tools=ToolsCapability())
                )
            )
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 