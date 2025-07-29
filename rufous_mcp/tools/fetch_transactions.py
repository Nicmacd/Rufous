"""
Fetch Transactions Tool - For retrieving transaction data from connected accounts
"""

import logging
from typing import Any, Dict
from mcp.types import Tool

from .base import BaseTool

logger = logging.getLogger(__name__)


class FetchTransactionsTool(BaseTool):
    """Tool for fetching transaction data from connected bank accounts"""
    
    def get_tool_definition(self) -> Tool:
        """Return the tool definition"""
        return Tool(
            name="fetch_transactions",
            description="Fetch transaction data from a connected bank account. Returns structured transaction data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "login_id": {
                        "type": "string",
                        "description": "Login ID obtained from connecting to a bank account"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of transaction history to fetch (default: 30, max: 365)",
                        "minimum": 1,
                        "maximum": 365,
                        "default": 30
                    }
                },
                "required": ["login_id"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the transaction fetch"""
        try:
            # Validate required arguments
            required_args = ["login_id"]
            missing_args = self.validate_required_args(arguments, required_args)
            if missing_args:
                return self.create_error_result(f"Missing required arguments: {', '.join(missing_args)}")
            
            login_id = arguments["login_id"]
            days = arguments.get("days", 30)
            
            # Validate days parameter
            if not isinstance(days, int) or days < 1 or days > 365:
                return self.create_error_result("Days must be an integer between 1 and 365")
            
            logger.info(f"Fetching {days} days of transactions for login_id: {login_id}")
            
            # Get transactions via Flinks
            transactions = await self.flinks_client.get_transactions(login_id, days)
            
            if not transactions:
                return self.create_success_result(
                    {
                        "transactions": [],
                        "count": 0,
                        "days_requested": days,
                        "message": "No transactions found for the specified period"
                    },
                    "No transactions found for the specified period"
                )
            
            # Prepare response data
            response_data = {
                "transactions": transactions,
                "count": len(transactions),
                "days_requested": days,
                "period_summary": {
                    "total_transactions": len(transactions),
                    "accounts_included": len(set(t.get('account_id') for t in transactions if t.get('account_id'))),
                    "date_range": {
                        "from": min(t.get('Date', '') for t in transactions if t.get('Date')),
                        "to": max(t.get('Date', '') for t in transactions if t.get('Date'))
                    }
                }
            }
            
            return self.create_success_result(
                response_data,
                f"Successfully fetched {len(transactions)} transactions from the last {days} days"
            )
        
        except Exception as e:
            logger.error(f"Error in fetch_transactions: {e}")
            return self.create_error_result(str(e)) 