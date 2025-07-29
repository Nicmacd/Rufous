"""
Connect Bank Account Tool - For connecting to Canadian banks via Flinks
"""

import logging
from typing import Any, Dict
from mcp.types import Tool

from .base import BaseTool

logger = logging.getLogger(__name__)


class ConnectBankTool(BaseTool):
    """Tool for connecting to Canadian bank accounts via Flinks"""
    
    def get_tool_definition(self) -> Tool:
        """Return the tool definition"""
        return Tool(
            name="connect_bank_account",
            description="Connect to a Canadian bank account using Flinks API. Returns a login_id for subsequent operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "institution": {
                        "type": "string",
                        "description": "Bank institution identifier (e.g., 'RBC', 'TD', 'BMO', 'Scotiabank', 'CIBC')"
                    },
                    "username": {
                        "type": "string", 
                        "description": "Bank account username/login ID"
                    },
                    "password": {
                        "type": "string",
                        "description": "Bank account password"
                    }
                },
                "required": ["institution", "username", "password"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the bank connection"""
        try:
            # Validate required arguments
            required_args = ["institution", "username", "password"]
            missing_args = self.validate_required_args(arguments, required_args)
            if missing_args:
                return self.create_error_result(f"Missing required arguments: {', '.join(missing_args)}")
            
            institution = arguments["institution"]
            username = arguments["username"]
            password = arguments["password"]
            
            logger.info(f"Attempting to connect to bank: {institution}")
            
            # Connect to bank account via Flinks
            result = await self.flinks_client.connect_bank_account(
                institution=institution,
                username=username,
                password=password
            )
            
            if result.get('status') == 'connected':
                return self.create_success_result(
                    result,
                    f"Successfully connected to {institution}. You can now use the login_id '{result['login_id']}' for other operations."
                )
            else:
                return self.create_error_result(result.get('message', 'Failed to connect to bank account'))
        
        except Exception as e:
            logger.error(f"Error in connect_bank_account: {e}")
            return self.create_error_result(str(e)) 