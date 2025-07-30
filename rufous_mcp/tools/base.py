"""
Base class for MCP tools
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from mcp.types import CallToolResult, TextContent, Tool

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all MCP tools"""
    
    def __init__(self, config=None):
        self.config = config
    
    @abstractmethod
    def get_tool_definition(self) -> Tool:
        """Return the tool definition for MCP"""
        pass
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Execute the tool with given arguments"""
        pass
    
    def create_success_result(self, data: Any, message: str = None) -> CallToolResult:
        """Create a successful tool result"""
        if isinstance(data, dict) or isinstance(data, list):
            content_text = json.dumps(data, indent=2, default=str)
        else:
            content_text = str(data)
        
        if message:
            content_text = f"{message}\n\n{content_text}"
        
        return CallToolResult(
            content=[TextContent(type="text", text=content_text)],
            isError=False
        )
    
    def create_error_result(self, error: str) -> CallToolResult:
        """Create an error tool result"""
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {error}")],
            isError=True
        )
    
    def validate_required_args(self, arguments: Dict[str, Any], required_args: List[str]) -> List[str]:
        """Validate that required arguments are present"""
        missing_args = []
        for arg in required_args:
            if arg not in arguments or arguments[arg] is None:
                missing_args.append(arg)
        return missing_args 