"""
Analyze Spending Tool - For analyzing spending patterns and trends
"""

import logging
from typing import Any, Dict, List
from mcp.types import Tool

from .base import BaseTool

logger = logging.getLogger(__name__)


class AnalyzeSpendingTool(BaseTool):
    """Tool for analyzing spending patterns from transaction data"""
    
    def get_tool_definition(self) -> Tool:
        """Return the tool definition"""
        return Tool(
            name="analyze_spending",
            description="Analyze spending patterns from transaction data. Returns spending insights, category breakdowns, and trends.",
            inputSchema={
                "type": "object",
                "properties": {
                    "login_id": {
                        "type": "string",
                        "description": "Login ID obtained from connecting to a bank account"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 30, max: 365)",
                        "minimum": 1,
                        "maximum": 365,
                        "default": 30
                    }
                },
                "required": ["login_id"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the spending analysis"""
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
            
            logger.info(f"Analyzing spending for {days} days, login_id: {login_id}")
            
            # Get spending analysis via Flinks
            analysis = await self.flinks_client.analyze_spending_patterns(login_id, days)
            
            if 'error' in analysis:
                return self.create_error_result(analysis['error'])
            
            # Enhance the analysis with additional insights
            enhanced_analysis = self._enhance_analysis(analysis, days)
            
            return self.create_success_result(
                enhanced_analysis,
                f"Spending analysis completed for {days} days. Total spent: ${analysis['total_spent']:.2f}"
            )
        
        except Exception as e:
            logger.error(f"Error in analyze_spending: {e}")
            return self.create_error_result(str(e))
    
    def _enhance_analysis(self, analysis: Dict[str, Any], days: int) -> Dict[str, Any]:
        """Enhance the basic analysis with additional insights"""
        total_spent = analysis.get('total_spent', 0)
        categories = analysis.get('categories', {})
        daily_spending = analysis.get('daily_spending', {})
        
        # Calculate category percentages
        category_breakdown = []
        for category, amount in categories.items():
            percentage = (amount / total_spent * 100) if total_spent > 0 else 0
            category_breakdown.append({
                'category': category,
                'amount': amount,
                'percentage': round(percentage, 2)
            })
        
        # Sort by amount descending
        category_breakdown.sort(key=lambda x: x['amount'], reverse=True)
        
        # Calculate daily averages
        daily_average = total_spent / days if days > 0 else 0
        
        # Calculate spending velocity (transactions per day)
        transaction_count = analysis.get('transaction_count', 0)
        transactions_per_day = transaction_count / days if days > 0 else 0
        
        # Identify top spending days
        top_spending_days = []
        if daily_spending:
            sorted_days = sorted(daily_spending.items(), key=lambda x: x[1], reverse=True)
            top_spending_days = sorted_days[:5]  # Top 5 days
        
        # Calculate spending trends
        spending_trend = self._calculate_spending_trend(daily_spending)
        
        return {
            'period_summary': {
                'total_spent': total_spent,
                'days_analyzed': days,
                'daily_average': round(daily_average, 2),
                'transaction_count': transaction_count,
                'transactions_per_day': round(transactions_per_day, 2),
                'average_transaction_amount': analysis.get('average_transaction', 0)
            },
            'category_breakdown': category_breakdown,
            'top_spending_days': [
                {'date': date, 'amount': amount} 
                for date, amount in top_spending_days
            ],
            'spending_trend': spending_trend,
            'daily_spending': daily_spending,
            'insights': self._generate_insights(analysis, days)
        }
    
    def _calculate_spending_trend(self, daily_spending: Dict[str, float]) -> Dict[str, Any]:
        """Calculate spending trend over the period"""
        if not daily_spending or len(daily_spending) < 2:
            return {'trend': 'insufficient_data', 'description': 'Not enough data to determine trend'}
        
        # Convert to sorted list by date
        sorted_spending = sorted(daily_spending.items())
        
        # Calculate trend using simple linear regression approach
        # First half vs second half comparison
        mid_point = len(sorted_spending) // 2
        first_half_avg = sum(amount for _, amount in sorted_spending[:mid_point]) / mid_point
        second_half_avg = sum(amount for _, amount in sorted_spending[mid_point:]) / (len(sorted_spending) - mid_point)
        
        if second_half_avg > first_half_avg * 1.1:  # 10% threshold
            trend = 'increasing'
            description = 'Spending is trending upward'
        elif second_half_avg < first_half_avg * 0.9:  # 10% threshold
            trend = 'decreasing'
            description = 'Spending is trending downward'
        else:
            trend = 'stable'
            description = 'Spending is relatively stable'
        
        return {
            'trend': trend,
            'description': description,
            'first_half_average': round(first_half_avg, 2),
            'second_half_average': round(second_half_avg, 2)
        }
    
    def _generate_insights(self, analysis: Dict[str, Any], days: int) -> List[str]:
        """Generate spending insights"""
        insights = []
        
        total_spent = analysis.get('total_spent', 0)
        categories = analysis.get('categories', {})
        daily_average = total_spent / days if days > 0 else 0
        
        # Top category insight
        if categories:
            top_category = max(categories.items(), key=lambda x: x[1])
            insights.append(f"Your highest spending category is {top_category[0]} at ${top_category[1]:.2f}")
        
        # Daily spending insight
        if daily_average > 0:
            insights.append(f"You spend an average of ${daily_average:.2f} per day")
        
        # Category diversity insight
        if len(categories) > 5:
            insights.append("Your spending is well-diversified across multiple categories")
        elif len(categories) <= 2:
            insights.append("Your spending is concentrated in few categories")
        
        # High transaction frequency insight
        transaction_count = analysis.get('transaction_count', 0)
        if transaction_count > 0:
            avg_transaction = total_spent / transaction_count
            if avg_transaction < 20:
                insights.append("You tend to make many small purchases")
            elif avg_transaction > 100:
                insights.append("You tend to make fewer, larger purchases")
        
        return insights 