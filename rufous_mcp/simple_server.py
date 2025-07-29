#!/usr/bin/env python3
"""
Simplified Rufous MCP Server - Minimal implementation to test tool loading
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
from mcp.types import (
    ServerCapabilities,
    ToolsCapability,
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)

from rufous_mcp.config import Config
from rufous_mcp.flinks_client import FlinksClient

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SimpleRufousServer:
    """Simplified MCP server for testing"""
    
    def __init__(self):
        self.config = Config()
        self.flinks_client = FlinksClient(self.config)
        self.server = Server("simple-rufous")
        
        # Define tools as simple dictionaries
        self.tool_definitions = [
            {
                "name": "connect_bank_account",
                "description": "Connect to a Canadian bank account using Flinks API",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "institution": {
                            "type": "string",
                            "description": "Bank institution (e.g., 'FlinksCapital')"
                        },
                        "username": {
                            "type": "string",
                            "description": "Bank username"
                        },
                        "password": {
                            "type": "string", 
                            "description": "Bank password"
                        }
                    },
                    "required": ["institution", "username", "password"]
                }
            },
            {
                "name": "fetch_transactions",
                "description": "Fetch transaction data from connected bank account",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "login_id": {
                            "type": "string",
                            "description": "Login ID from bank connection"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days of transactions (default: 30)"
                        }
                    },
                    "required": ["login_id"]
                }
            },
            {
                "name": "analyze_spending",
                "description": "Analyze spending patterns from transaction data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "login_id": {
                            "type": "string",
                            "description": "Login ID from bank connection"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to analyze (default: 30)"
                        }
                    },
                    "required": ["login_id"]
                }
            }
        ]
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools():
            """List available tools"""
            try:
                logger.info("SimpleServer: Starting handle_list_tools")
                tools = []
                
                for tool_def in self.tool_definitions:
                    logger.info(f"SimpleServer: Creating tool {tool_def['name']}")
                    tool = Tool(
                        name=tool_def["name"],
                        description=tool_def["description"],
                        inputSchema=tool_def["inputSchema"]
                    )
                    tools.append(tool)
                    logger.info(f"SimpleServer: Added tool {tool.name}")
                
                # For MCP v1.0.0, return raw list instead of ListToolsResult
                logger.info(f"SimpleServer: Successfully created tools list with {len(tools)} tools")
                return tools
                
            except Exception as e:
                logger.error(f"SimpleServer: Error in handle_list_tools: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            """Handle tool calls"""
            try:
                logger.info(f"SimpleServer: Tool call: {name} with args: {arguments}")
                
                if name == "connect_bank_account":
                    institution = arguments.get("institution", "")
                    username = arguments.get("username", "")
                    password = arguments.get("password", "")
                    
                    # Mock mode for when Flinks API is down (502 errors)
                    logger.info(f"Checking mock mode: username={username}, password={password}")
                    if username.lower() == "greatday":
                        mock_result = {
                            "login_id": f"mock_login_{institution}_123456",
                            "status": "connected", 
                            "institution": institution,
                            "message": f"Successfully connected to {institution} (MOCK MODE - API temporarily unavailable)"
                        }
                        return {
                            "content": [{"type": "text", "text": json.dumps(mock_result, indent=2)}],
                            "isError": False
                        }
                    
                    # Real API call
                    result = await self.flinks_client.connect_bank_account(
                        institution, username, password
                    )
                    
                    return {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                        "isError": False
                    }
                
                elif name == "fetch_transactions":
                    login_id = arguments.get("login_id", "")
                    days = arguments.get("days", 30)
                    
                    # Mock mode for testing
                    if login_id.startswith("mock_login_"):
                        mock_transactions = [
                            {
                                "id": "txn_001",
                                "amount": -45.67,
                                "date": "2024-07-25T10:30:00Z",
                                "description": "Coffee Shop Purchase",
                                "category": "Dining",
                                "account_id": "acc_123"
                            },
                            {
                                "id": "txn_002", 
                                "amount": -125.50,
                                "date": "2024-07-24T15:45:00Z",
                                "description": "Grocery Store",
                                "category": "Groceries",
                                "account_id": "acc_123"
                            }
                        ]
                        return {
                            "content": [{"type": "text", "text": json.dumps(mock_transactions, indent=2)}],
                            "isError": False
                        }
                    
                    transactions = await self.flinks_client.get_transactions(login_id, days)
                    return {
                        "content": [{"type": "text", "text": json.dumps(transactions, indent=2, default=str)}],
                        "isError": False
                    }
                
                elif name == "analyze_spending":
                    login_id = arguments.get("login_id", "")
                    days = arguments.get("days", 30)
                    
                    # Mock mode for testing
                    if login_id.startswith("mock_login_"):
                        mock_analysis = {
                            "total_spent": 171.17,
                            "categories": {
                                "Dining": 45.67,
                                "Groceries": 125.50
                            },
                            "daily_spending": {
                                "2024-07-24": 125.50,
                                "2024-07-25": 45.67
                            },
                            "transaction_count": 2,
                            "average_transaction": 85.59,
                            "analysis_period_days": days
                        }
                        return {
                            "content": [{"type": "text", "text": json.dumps(mock_analysis, indent=2)}],
                            "isError": False
                        }
                    
                    analysis = await self.flinks_client.analyze_spending_patterns(login_id, days)
                    return {
                        "content": [{"type": "text", "text": json.dumps(analysis, indent=2, default=str)}],
                        "isError": False
                    }
                
                else:
                    return {
                        "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                        "isError": True
                    }
                    
            except Exception as e:
                logger.error(f"SimpleServer: Tool execution error: {e}")
                return {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True
                }
    
    async def run(self):
        """Run the simple MCP server"""
        logger.info("Starting Simple Rufous MCP Server")
        
        # Initialize Flinks client
        await self.flinks_client.initialize()
        
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="simple-rufous",
                    server_version="0.1.0",
                    capabilities=ServerCapabilities(
                        tools=ToolsCapability()
                    )
                )
            )


async def main():
    """Main entry point"""
    server = SimpleRufousServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main()) 