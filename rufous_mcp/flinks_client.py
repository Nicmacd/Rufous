"""
Flinks API Client Wrapper for Rufous MCP Server
"""

import asyncio
import logging
import requests
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from .config import Config
from .models import Transaction, Account, FinancialSummary

logger = logging.getLogger(__name__)


class FlinksClient:
    """Direct HTTP client for Flinks API"""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.flinks_api_url.rstrip('/')
        self.customer_id = config.flinks_customer_id
        self.bearer_token = config.flinks_bearer_token
        self.auth_key = config.flinks_auth_key  
        self.x_api_key = config.flinks_x_api_key
        self._session_cache: Dict[str, Any] = {}
        self._rate_limiter = RateLimiter(config.api_rate_limit_per_minute)
        
    async def initialize(self) -> bool:
        """Initialize the Flinks client"""
        try:
            # Validate configuration
            self.config.validate_config()
            logger.info(f"Flinks client initialized for {'sandbox' if self.config.is_sandbox else 'production'}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Flinks client: {e}")
            raise
    
    def _get_headers(self, auth_type: str = "bearer") -> Dict[str, str]:
        """Get appropriate headers for Flinks API calls"""
        headers = {
            "Content-Type": "application/json",
            "Instance": self.customer_id,
        }
        
        if auth_type == "bearer" and self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        elif auth_type == "auth_key" and self.auth_key:
            headers["flinks-auth-key"] = self.auth_key
        elif auth_type == "x_api" and self.x_api_key:
            headers["x-api-key"] = self.x_api_key
            
        return headers
    
    async def connect_bank_account(self, institution: str, username: str, password: str) -> Dict[str, Any]:
        """
        Connect to a bank account using direct API calls
        
        Args:
            institution: Bank institution identifier
            username: Bank username
            password: Bank password
            
        Returns:
            Dict containing login_id and connection status
        """
        await self._rate_limiter.wait()
        
        try:
            logger.info(f"Attempting to connect to {institution}")
            
            # Use the authorize endpoint
            payload = {
                "username": username,
                "password": password,
                "institution": institution,
                "save": True,
                "schedule_refresh": False
            }
            
            headers = self._get_headers("bearer")
            
            response = requests.post(
                f"{self.base_url}/BankingServices/Authorize",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            logger.info(f"API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"API Response: {result}")
                
                if result.get('LoginId'):
                    login_id = result['LoginId']
                    
                    # Cache the login_id
                    self._session_cache[login_id] = {
                        'institution': institution,
                        'connected_at': datetime.now(),
                        'status': 'connected'
                    }
                    
                    logger.info(f"Successfully connected to {institution}")
                    
                    return {
                        'login_id': login_id,
                        'status': 'connected',
                        'institution': institution,
                        'message': f'Successfully connected to {institution}'
                    }
            
            # Handle error response
            error_msg = f"Failed to connect: HTTP {response.status_code}"
            if response.text:
                error_msg += f" - {response.text}"
                
            return {
                'status': 'failed',
                'message': error_msg
            }
                
        except Exception as e:
            logger.error(f"Bank connection error: {e}")
            return {
                'status': 'error',
                'message': f'Connection error: {str(e)}'
            }
    
    async def get_accounts_summary(self, login_id: str) -> Dict[str, Any]:
        """Get accounts summary for a login_id"""
        await self._rate_limiter.wait()
        
        try:
            # First authorize to get request_id
            auth_payload = {
                "loginId": login_id,
                "most_recent_cached": True
            }
            
            headers = self._get_headers("bearer")
            
            auth_response = requests.post(
                f"{self.base_url}/BankingServices/Authorize",
                json=auth_payload,
                headers=headers,
                timeout=30
            )
            
            if auth_response.status_code != 200:
                return {'error': f'Failed to authorize: HTTP {auth_response.status_code}'}
            
            auth_result = auth_response.json()
            if 'RequestId' not in auth_result:
                return {'error': 'Failed to get request ID'}
            
            request_id = auth_result['RequestId']
            
            # Get accounts summary
            summary_response = requests.get(
                f"{self.base_url}/BankingServices/GetAccountsSummary/{request_id}",
                headers=headers,
                timeout=30
            )
            
            if summary_response.status_code == 200:
                summary_result = summary_response.json()
                return {
                    'request_id': request_id,
                    'accounts': summary_result.get('Accounts', []),
                    'status': 'success'
                }
            else:
                return {'error': f'Failed to get accounts summary: HTTP {summary_response.status_code}'}
            
        except Exception as e:
            logger.error(f"Error getting accounts summary: {e}")
            return {'error': str(e)}
    
    async def get_accounts_detail(self, login_id: str, days: int = 30) -> Dict[str, Any]:
        """Get detailed account information including transactions"""
        await self._rate_limiter.wait()
        
        try:
            # Limit days to max allowed
            days = min(days, self.config.max_transaction_days)
            
            # First authorize to get request_id
            auth_payload = {
                "loginId": login_id,
                "most_recent_cached": True
            }
            
            headers = self._get_headers("bearer")
            
            auth_response = requests.post(
                f"{self.base_url}/BankingServices/Authorize",
                json=auth_payload,
                headers=headers,
                timeout=30
            )
            
            if auth_response.status_code != 200:
                return {'error': f'Failed to authorize: HTTP {auth_response.status_code}'}
            
            auth_result = auth_response.json()
            if 'RequestId' not in auth_result:
                return {'error': 'Failed to get request ID'}
            
            request_id = auth_result['RequestId']
            
            # Get detailed accounts data
            detail_response = requests.get(
                f"{self.base_url}/BankingServices/GetAccountsDetail/{request_id}?DaysOfTransactions=Days{days}",
                headers=headers,
                timeout=30
            )
            
            if detail_response.status_code == 200:
                detail_result = detail_response.json()
                return {
                    'request_id': request_id,
                    'accounts': detail_result.get('Accounts', []),
                    'status': 'success',
                    'days_requested': days
                }
            else:
                return {'error': f'Failed to get accounts detail: HTTP {detail_response.status_code}'}
            
        except Exception as e:
            logger.error(f"Error getting accounts detail: {e}")
            return {'error': str(e)}
    
    async def get_transactions(self, login_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get all transactions for the specified period"""
        accounts_data = await self.get_accounts_detail(login_id, days)
        
        if 'error' in accounts_data:
            return []
        
        transactions = []
        for account in accounts_data.get('accounts', []):
            account_transactions = account.get('Transactions', [])
            for transaction in account_transactions:
                # Enrich transaction with account info
                transaction['account_id'] = account.get('Id')
                transaction['account_type'] = account.get('Type')
                transaction['account_name'] = account.get('Title')
                transactions.append(transaction)
        
        return transactions
    
    async def analyze_spending_patterns(self, login_id: str, days: int = 30) -> Dict[str, Any]:
        """Analyze spending patterns from transaction data"""
        transactions = await self.get_transactions(login_id, days)
        
        if not transactions:
            return {'error': 'No transactions found'}
        
        # Basic spending analysis
        total_spent = 0
        categories = {}
        daily_spending = {}
        
        for transaction in transactions:
            amount = float(transaction.get('Amount', 0))
            date_str = transaction.get('Date', '')
            category = transaction.get('Category', 'Other')
            
            # Only count outgoing transactions (negative amounts typically)
            if amount < 0:
                amount = abs(amount)
                total_spent += amount
                
                # Category breakdown
                if category not in categories:
                    categories[category] = 0
                categories[category] += amount
                
                # Daily spending
                if date_str:
                    date_key = date_str.split('T')[0]  # Get just the date part
                    if date_key not in daily_spending:
                        daily_spending[date_key] = 0
                    daily_spending[date_key] += amount
        
        return {
            'total_spent': total_spent,
            'categories': categories,
            'daily_spending': daily_spending,
            'transaction_count': len(transactions),
            'average_transaction': total_spent / len(transactions) if transactions else 0,
            'analysis_period_days': days
        }
    
    async def compare_spending_periods(self, login_id: str, period1_days: int, period2_days: int) -> Dict[str, Any]:
        """Compare spending between two periods"""
        # Get transactions for both periods
        current_analysis = await self.analyze_spending_patterns(login_id, period1_days)
        previous_analysis = await self.analyze_spending_patterns(login_id, period2_days)
        
        if 'error' in current_analysis or 'error' in previous_analysis:
            return {'error': 'Could not retrieve transaction data for comparison'}
        
        # Calculate changes
        current_total = current_analysis['total_spent']
        previous_total = previous_analysis['total_spent']
        
        change_amount = current_total - previous_total
        change_percentage = (change_amount / previous_total * 100) if previous_total > 0 else 0
        
        # Category comparisons
        category_changes = {}
        all_categories = set(current_analysis['categories'].keys()) | set(previous_analysis['categories'].keys())
        
        for category in all_categories:
            current_amount = current_analysis['categories'].get(category, 0)
            previous_amount = previous_analysis['categories'].get(category, 0)
            category_change = current_amount - previous_amount
            
            category_changes[category] = {
                'current': current_amount,
                'previous': previous_amount,
                'change': category_change,
                'change_percentage': (category_change / previous_amount * 100) if previous_amount > 0 else 0
            }
        
        return {
            'current_period': {
                'total': current_total,
                'days': period1_days
            },
            'previous_period': {
                'total': previous_total,
                'days': period2_days
            },
            'comparison': {
                'change_amount': change_amount,
                'change_percentage': change_percentage,
                'trend': 'increased' if change_amount > 0 else 'decreased' if change_amount < 0 else 'unchanged'
            },
            'category_changes': category_changes
        }
    
    def clear_session_cache(self):
        """Clear session cache"""
        self._session_cache.clear()
        logger.info("Session cache cleared")
    
    def is_login_id_cached(self, login_id: str) -> bool:
        """Check if login_id is in session cache"""
        return login_id in self._session_cache


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls_per_minute: int):
        self.max_calls = max_calls_per_minute
        self.calls = []
    
    async def wait(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()
        
        # Remove calls older than 1 minute
        self.calls = [call_time for call_time in self.calls if now - call_time < 60]
        
        # If we've made too many calls, wait
        if len(self.calls) >= self.max_calls:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        # Record this call
        self.calls.append(now) 