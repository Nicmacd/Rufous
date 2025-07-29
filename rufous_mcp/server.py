#!/usr/bin/env python3
"""
Rufous MCP Server - Main server implementation
"""

import asyncio
import logging
import sys
import os
from typing import Any, Dict, List, Optional
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
    ServerCapabilities,
    ToolsCapability,
)

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rufous_mcp.config import Config
from rufous_mcp.flinks_client import FlinksClient
from rufous_mcp.tools import (
    ConnectBankTool,
    FetchTransactionsTool,
    AnalyzeSpendingTool,
    ComparePeriodsTools,
    CategoryBreakdownTool,
    FinancialSummaryTool,
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class RufousMCPServer:
    """Main MCP server for financial health tracking with Flinks"""
    
    def __init__(self):
        self.config = Config()
        self.flinks_client = FlinksClient(self.config)
        self.server = Server("rufous-financial-health")
        
        # Initialize tools
        self.tools = {
            "connect_bank_account": ConnectBankTool(self.flinks_client),
            "fetch_transactions": FetchTransactionsTool(self.flinks_client),
            "analyze_spending": AnalyzeSpendingTool(self.flinks_client),
            "compare_periods": ComparePeriodsTools(self.flinks_client),
            "categorize_expenses": CategoryBreakdownTool(self.flinks_client),
            "get_financial_summary": FinancialSummaryTool(self.flinks_client),
        }
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List available tools"""
            try:
                logger.info("Starting handle_list_tools")
                tools = []
                for tool_name, tool_instance in self.tools.items():
                    logger.info(f"Processing tool: {tool_name}")
                    tool_def = tool_instance.get_tool_definition()
                    logger.info(f"Got tool definition: {tool_def.name} ({type(tool_def)})")
                    
                    # Create a fresh Tool object to avoid any serialization issues
                    fresh_tool = Tool(
                        name=tool_def.name,
                        description=tool_def.description,
                        inputSchema=tool_def.inputSchema
                    )
                    tools.append(fresh_tool)
                
                logger.info(f"Creating ListToolsResult with {len(tools)} tools")
                result = ListToolsResult(tools=tools)
                logger.info(f"Successfully created ListToolsResult: {type(result)}")
                return result
            except Exception as e:
                logger.error(f"Error in handle_list_tools: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> CallToolResult:
            """Handle tool calls"""
            try:
                if name not in self.tools:
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                        isError=True
                    )
                
                tool = self.tools[name]
                result = await tool.execute(arguments)
                return result
                
            except Exception as e:
                logger.error(f"Tool execution error for {name}: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error executing {name}: {str(e)}")],
                    isError=True
                )
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Rufous MCP Server for Financial Health Tracking")
        
        # Initialize Flinks client
        await self.flinks_client.initialize()
        
        # Run the server with proper initialization
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream, 
                InitializationOptions(
                    server_name="rufous-financial-health",
                    server_version="0.1.0",
                    capabilities=ServerCapabilities(
                        tools=ToolsCapability()
                    )
                )
            )


async def main():
    """Main entry point"""
    server = RufousMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main()) 