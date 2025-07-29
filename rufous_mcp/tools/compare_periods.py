"""
Compare Periods Tool - For comparing spending across different time periods
"""

import logging
from typing import Any, Dict, List
from mcp.types import Tool

from .base import BaseTool

logger = logging.getLogger(__name__)


class ComparePeriodsTools(BaseTool):
    """Tool for comparing spending across different time periods"""
    
    def get_tool_definition(self) -> Tool:
        """Return the tool definition"""
        return Tool(
            name="compare_periods",
            description="Compare spending between two different time periods. Returns comparison data and insights.",
            inputSchema={
                "type": "object",
                "properties": {
                    "login_id": {
                        "type": "string",
                        "description": "Login ID obtained from connecting to a bank account"
                    },
                    "current_period_days": {
                        "type": "integer",
                        "description": "Number of days for the current period to analyze (default: 30, max: 365)",
                        "minimum": 1,
                        "maximum": 365,
                        "default": 30
                    },
                    "previous_period_days": {
                        "type": "integer",
                        "description": "Number of days for the previous period to compare against (default: 30, max: 365)",
                        "minimum": 1,
                        "maximum": 365,
                        "default": 30
                    }
                },
                "required": ["login_id"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the period comparison"""
        try:
            # Validate required arguments
            required_args = ["login_id"]
            missing_args = self.validate_required_args(arguments, required_args)
            if missing_args:
                return self.create_error_result(f"Missing required arguments: {', '.join(missing_args)}")
            
            login_id = arguments["login_id"]
            current_period_days = arguments.get("current_period_days", 30)
            previous_period_days = arguments.get("previous_period_days", 30)
            
            # Validate days parameters
            if not isinstance(current_period_days, int) or current_period_days < 1 or current_period_days > 365:
                return self.create_error_result("Current period days must be an integer between 1 and 365")
            
            if not isinstance(previous_period_days, int) or previous_period_days < 1 or previous_period_days > 365:
                return self.create_error_result("Previous period days must be an integer between 1 and 365")
            
            logger.info(f"Comparing spending periods: current {current_period_days} days vs previous {previous_period_days} days")
            
            # Get spending comparison via Flinks
            comparison = await self.flinks_client.compare_spending_periods(
                login_id, 
                current_period_days, 
                previous_period_days
            )
            
            if 'error' in comparison:
                return self.create_error_result(comparison['error'])
            
            # Enhance the comparison with additional insights
            enhanced_comparison = self._enhance_comparison(comparison)
            
            return self.create_success_result(
                enhanced_comparison,
                f"Spending comparison completed. Current period: ${comparison['current_period']['total']:.2f}, "
                f"Previous period: ${comparison['previous_period']['total']:.2f}"
            )
        
        except Exception as e:
            logger.error(f"Error in compare_periods: {e}")
            return self.create_error_result(str(e))
    
    def _enhance_comparison(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance the comparison with additional insights"""
        current_total = comparison['current_period']['total']
        previous_total = comparison['previous_period']['total']
        change_amount = comparison['comparison']['change_amount']
        change_percentage = comparison['comparison']['change_percentage']
        
        # Generate insights
        insights = []
        
        # Overall trend insight
        if change_percentage > 10:
            insights.append(f"Your spending has increased significantly by {change_percentage:.1f}% (${change_amount:.2f})")
        elif change_percentage > 5:
            insights.append(f"Your spending has increased moderately by {change_percentage:.1f}% (${change_amount:.2f})")
        elif change_percentage < -10:
            insights.append(f"Your spending has decreased significantly by {abs(change_percentage):.1f}% (${abs(change_amount):.2f})")
        elif change_percentage < -5:
            insights.append(f"Your spending has decreased moderately by {abs(change_percentage):.1f}% (${abs(change_amount):.2f})")
        else:
            insights.append("Your spending has remained relatively stable between periods")
        
        # Category-specific insights
        category_changes = comparison.get('category_changes', {})
        if category_changes:
            # Find biggest increases and decreases
            biggest_increase = max(category_changes.items(), key=lambda x: x[1]['change'])
            biggest_decrease = min(category_changes.items(), key=lambda x: x[1]['change'])
            
            if biggest_increase[1]['change'] > 0:
                insights.append(f"Biggest spending increase: {biggest_increase[0]} (+${biggest_increase[1]['change']:.2f})")
            
            if biggest_decrease[1]['change'] < 0:
                insights.append(f"Biggest spending decrease: {biggest_decrease[0]} (-${abs(biggest_decrease[1]['change']):.2f})")
        
        # Daily average comparison
        current_days = comparison['current_period']['days']
        previous_days = comparison['previous_period']['days']
        
        current_daily_avg = current_total / current_days if current_days > 0 else 0
        previous_daily_avg = previous_total / previous_days if previous_days > 0 else 0
        
        daily_change = current_daily_avg - previous_daily_avg
        
        if abs(daily_change) > 5:
            direction = "increased" if daily_change > 0 else "decreased"
            insights.append(f"Daily spending average {direction} by ${abs(daily_change):.2f}")
        
        return {
            'comparison_summary': {
                'current_period': {
                    'total': current_total,
                    'days': current_days,
                    'daily_average': round(current_daily_avg, 2)
                },
                'previous_period': {
                    'total': previous_total,
                    'days': previous_days,
                    'daily_average': round(previous_daily_avg, 2)
                },
                'change': {
                    'amount': change_amount,
                    'percentage': round(change_percentage, 2),
                    'trend': comparison['comparison']['trend'],
                    'daily_change': round(daily_change, 2)
                }
            },
            'category_analysis': self._analyze_category_changes(category_changes),
            'insights': insights,
            'recommendations': self._generate_recommendations(comparison)
        }
    
    def _analyze_category_changes(self, category_changes: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Analyze category changes"""
        if not category_changes:
            return {'message': 'No category data available'}
        
        categories_increased = []
        categories_decreased = []
        categories_stable = []
        
        for category, changes in category_changes.items():
            change_amount = changes['change']
            change_percentage = changes['change_percentage']
            
            if change_amount > 10:  # $10 threshold
                categories_increased.append({
                    'category': category,
                    'change_amount': change_amount,
                    'change_percentage': change_percentage
                })
            elif change_amount < -10:
                categories_decreased.append({
                    'category': category,
                    'change_amount': abs(change_amount),
                    'change_percentage': abs(change_percentage)
                })
            else:
                categories_stable.append({
                    'category': category,
                    'change_amount': change_amount,
                    'change_percentage': change_percentage
                })
        
        # Sort by change amount
        categories_increased.sort(key=lambda x: x['change_amount'], reverse=True)
        categories_decreased.sort(key=lambda x: x['change_amount'], reverse=True)
        
        return {
            'categories_increased': categories_increased,
            'categories_decreased': categories_decreased,
            'categories_stable': categories_stable,
            'summary': {
                'increased_count': len(categories_increased),
                'decreased_count': len(categories_decreased),
                'stable_count': len(categories_stable)
            }
        }
    
    def _generate_recommendations(self, comparison: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on comparison"""
        recommendations = []
        
        change_percentage = comparison['comparison']['change_percentage']
        category_changes = comparison.get('category_changes', {})
        
        # Overall spending recommendations
        if change_percentage > 15:
            recommendations.append("Consider reviewing your budget as spending has increased significantly")
            recommendations.append("Identify areas where you can reduce discretionary spending")
        elif change_percentage < -15:
            recommendations.append("Good job on reducing spending! Consider maintaining this trend")
        
        # Category-specific recommendations
        if category_changes:
            # Find categories with biggest increases
            biggest_increases = sorted(
                [(cat, data['change']) for cat, data in category_changes.items()],
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            for category, change in biggest_increases:
                if change > 50:  # $50 threshold
                    recommendations.append(f"Monitor {category} spending - it increased by ${change:.2f}")
        
        if not recommendations:
            recommendations.append("Your spending patterns look stable - keep monitoring regularly")
        
        return recommendations 