#!/usr/bin/env python3
"""
Rufous MCP Server - Main server implementation for PDF statement processing
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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class RufousMCPServer:
    """Main MCP server for PDF statement processing and financial analysis"""
    
    def __init__(self):
        self.config = Config()
        self.server = Server("rufous-pdf-financial")
        
        # Initialize tools - currently minimal, can be extended with PDF processing tools
        self.tools = {
            # Future PDF processing tools will be added here
        }
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """Handle listing available tools"""
            tool_list = []
            for name, tool in self.tools.items():
                tool_list.append(Tool(
                    name=name,
                    description=tool.description,
                    inputSchema=tool.get_input_schema()
                ))
            
            return ListToolsResult(tools=tool_list)
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any] | None) -> CallToolResult:
            """Handle tool execution"""
            if name not in self.tools:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                    isError=True
                )
            
            try:
                tool = self.tools[name]
                result = await tool.execute(arguments or {})
                
                return CallToolResult(
                    content=[TextContent(type="text", text=result)],
                    isError=False
                )
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error executing {name}: {str(e)}")],
                    isError=True
                )
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Rufous MCP Server for PDF Financial Statement Processing")
        
        # Validate configuration
        self.config.validate_config()
        
        # Run the server with proper initialization
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream, 
                InitializationOptions(
                    server_name="rufous-pdf-financial",
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