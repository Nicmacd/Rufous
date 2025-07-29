"""
Category Breakdown Tool - For detailed spending analysis by category
"""

import logging
from typing import Any, Dict, List
from mcp.types import Tool

from .base import BaseTool

logger = logging.getLogger(__name__)


class CategoryBreakdownTool(BaseTool):
    """Tool for breaking down spending by categories with detailed analysis"""
    
    def get_tool_definition(self) -> Tool:
        """Return the tool definition"""
        return Tool(
            name="categorize_expenses",
            description="Get detailed breakdown of expenses by category with insights and comparisons.",
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
                    },
                    "include_subcategories": {
                        "type": "boolean",
                        "description": "Whether to include subcategory analysis (default: false)",
                        "default": False
                    }
                },
                "required": ["login_id"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the category breakdown analysis"""
        try:
            # Validate required arguments
            required_args = ["login_id"]
            missing_args = self.validate_required_args(arguments, required_args)
            if missing_args:
                return self.create_error_result(f"Missing required arguments: {', '.join(missing_args)}")
            
            login_id = arguments["login_id"]
            days = arguments.get("days", 30)
            include_subcategories = arguments.get("include_subcategories", False)
            
            # Validate days parameter
            if not isinstance(days, int) or days < 1 or days > 365:
                return self.create_error_result("Days must be an integer between 1 and 365")
            
            logger.info(f"Creating category breakdown for {days} days, login_id: {login_id}")
            
            # Get spending analysis via Flinks
            analysis = await self.flinks_client.analyze_spending_patterns(login_id, days)
            
            if 'error' in analysis:
                return self.create_error_result(analysis['error'])
            
            # Create detailed category breakdown
            breakdown = self._create_category_breakdown(analysis, days, include_subcategories)
            
            return self.create_success_result(
                breakdown,
                f"Category breakdown completed for {days} days. Found {len(breakdown['categories'])} spending categories."
            )
        
        except Exception as e:
            logger.error(f"Error in categorize_expenses: {e}")
            return self.create_error_result(str(e))
    
    def _create_category_breakdown(self, analysis: Dict[str, Any], days: int, include_subcategories: bool) -> Dict[str, Any]:
        """Create detailed category breakdown with analysis"""
        total_spent = analysis.get('total_spent', 0)
        categories = analysis.get('categories', {})
        
        # Create category analysis
        category_details = []
        for category, amount in categories.items():
            percentage = (amount / total_spent * 100) if total_spent > 0 else 0
            daily_average = amount / days if days > 0 else 0
            
            category_info = {
                'category': category,
                'amount': round(amount, 2),
                'percentage': round(percentage, 2),
                'daily_average': round(daily_average, 2),
                'classification': self._classify_category(category),
                'priority': self._get_category_priority(category, percentage)
            }
            
            if include_subcategories:
                category_info['subcategories'] = self._analyze_subcategories(category, amount)
            
            category_details.append(category_info)
        
        # Sort by amount descending
        category_details.sort(key=lambda x: x['amount'], reverse=True)
        
        # Generate category insights
        insights = self._generate_category_insights(category_details, total_spent)
        
        # Calculate category metrics
        metrics = self._calculate_category_metrics(category_details, total_spent)
        
        return {
            'summary': {
                'total_spent': total_spent,
                'days_analyzed': days,
                'category_count': len(category_details),
                'top_category': category_details[0]['category'] if category_details else None,
                'most_diverse_spending': len(category_details) > 5
            },
            'categories': category_details,
            'metrics': metrics,
            'insights': insights,
            'recommendations': self._generate_category_recommendations(category_details)
        }
    
    def _classify_category(self, category: str) -> str:
        """Classify category as essential, discretionary, or investment"""
        essential_keywords = [
            'groceries', 'grocery', 'food', 'utilities', 'rent', 'mortgage', 
            'insurance', 'medical', 'healthcare', 'pharmacy', 'gas', 'fuel',
            'transportation', 'phone', 'internet'
        ]
        
        discretionary_keywords = [
            'restaurant', 'dining', 'entertainment', 'shopping', 'retail',
            'travel', 'vacation', 'hobby', 'clothing', 'electronics',
            'subscription', 'streaming', 'coffee', 'bar', 'alcohol'
        ]
        
        investment_keywords = [
            'investment', 'savings', 'retirement', 'mutual fund', 'stock',
            'bond', 'rrsp', 'tfsa', 'education', 'tuition'
        ]
        
        category_lower = category.lower()
        
        if any(keyword in category_lower for keyword in essential_keywords):
            return 'essential'
        elif any(keyword in category_lower for keyword in investment_keywords):
            return 'investment'
        elif any(keyword in category_lower for keyword in discretionary_keywords):
            return 'discretionary'
        else:
            return 'other'
    
    def _get_category_priority(self, category: str, percentage: float) -> str:
        """Get priority level for category monitoring"""
        if percentage > 30:
            return 'high'
        elif percentage > 15:
            return 'medium'
        elif percentage > 5:
            return 'low'
        else:
            return 'minimal'
    
    def _analyze_subcategories(self, category: str, amount: float) -> Dict[str, Any]:
        """Analyze subcategories (placeholder for future enhancement)"""
        # This would be enhanced with actual transaction-level analysis
        return {
            'note': 'Subcategory analysis requires transaction-level data',
            'estimated_breakdown': {
                'primary': amount * 0.7,
                'secondary': amount * 0.3
            }
        }
    
    def _calculate_category_metrics(self, category_details: List[Dict[str, Any]], total_spent: float) -> Dict[str, Any]:
        """Calculate category metrics"""
        if not category_details:
            return {}
        
        # Classification breakdown
        classifications = {}
        for category in category_details:
            classification = category['classification']
            if classification not in classifications:
                classifications[classification] = {'count': 0, 'amount': 0}
            classifications[classification]['count'] += 1
            classifications[classification]['amount'] += category['amount']
        
        # Calculate percentages for classifications
        for classification in classifications:
            classifications[classification]['percentage'] = (
                classifications[classification]['amount'] / total_spent * 100
            ) if total_spent > 0 else 0
        
        # Priority distribution
        priority_distribution = {}
        for category in category_details:
            priority = category['priority']
            if priority not in priority_distribution:
                priority_distribution[priority] = 0
            priority_distribution[priority] += 1
        
        # Concentration metrics
        top_3_percentage = sum(cat['percentage'] for cat in category_details[:3])
        diversity_score = len(category_details) / total_spent * 100 if total_spent > 0 else 0
        
        return {
            'classification_breakdown': classifications,
            'priority_distribution': priority_distribution,
            'concentration_metrics': {
                'top_3_categories_percentage': round(top_3_percentage, 2),
                'diversity_score': round(diversity_score, 4),
                'concentration_level': 'high' if top_3_percentage > 70 else 'medium' if top_3_percentage > 50 else 'low'
            }
        }
    
    def _generate_category_insights(self, category_details: List[Dict[str, Any]], total_spent: float) -> List[str]:
        """Generate insights about category spending"""
        insights = []
        
        if not category_details:
            return ["No spending categories found"]
        
        # Top category insight
        top_category = category_details[0]
        insights.append(f"Your highest spending category is {top_category['category']} at {top_category['percentage']:.1f}% of total spending")
        
        # Essential vs discretionary breakdown
        essential_amount = sum(cat['amount'] for cat in category_details if cat['classification'] == 'essential')
        discretionary_amount = sum(cat['amount'] for cat in category_details if cat['classification'] == 'discretionary')
        
        if essential_amount > 0 and discretionary_amount > 0:
            essential_percentage = (essential_amount / total_spent * 100) if total_spent > 0 else 0
            discretionary_percentage = (discretionary_amount / total_spent * 100) if total_spent > 0 else 0
            
            insights.append(f"Essential expenses: {essential_percentage:.1f}%, Discretionary: {discretionary_percentage:.1f}%")
            
            if discretionary_percentage > 40:
                insights.append("High discretionary spending - consider reviewing optional expenses")
            elif essential_percentage > 70:
                insights.append("Most spending is on essentials - you have good spending discipline")
        
        # Concentration insight
        top_3_percentage = sum(cat['percentage'] for cat in category_details[:3])
        if top_3_percentage > 70:
            insights.append("Spending is highly concentrated in few categories")
        elif len(category_details) > 8:
            insights.append("Spending is well-diversified across many categories")
        
        return insights
    
    def _generate_category_recommendations(self, category_details: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on category analysis"""
        recommendations = []
        
        if not category_details:
            return ["Unable to generate recommendations without spending data"]
        
        # High spending category recommendations
        high_spending_categories = [cat for cat in category_details if cat['priority'] == 'high']
        if high_spending_categories:
            for category in high_spending_categories:
                if category['classification'] == 'discretionary':
                    recommendations.append(f"Consider reducing {category['category']} spending - it's {category['percentage']:.1f}% of your budget")
        
        # Essential spending optimization
        essential_categories = [cat for cat in category_details if cat['classification'] == 'essential' and cat['percentage'] > 10]
        if essential_categories:
            recommendations.append("Review essential expenses for potential savings opportunities")
        
        # Discretionary spending advice
        discretionary_total = sum(cat['percentage'] for cat in category_details if cat['classification'] == 'discretionary')
        if discretionary_total > 50:
            recommendations.append("Consider setting limits on discretionary spending categories")
        
        # Investment recommendations
        investment_categories = [cat for cat in category_details if cat['classification'] == 'investment']
        if not investment_categories:
            recommendations.append("Consider allocating budget for savings and investments")
        
        if not recommendations:
            recommendations.append("Your category spending looks balanced - continue monitoring regularly")
        
        return recommendations 