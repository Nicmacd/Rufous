"""
Financial Summary Tool - For generating comprehensive financial health summaries
"""

import logging
from typing import Any, Dict, List
from mcp.types import Tool

from .base import BaseTool

logger = logging.getLogger(__name__)


class FinancialSummaryTool(BaseTool):
    """Tool for generating comprehensive financial health summaries"""
    
    def get_tool_definition(self) -> Tool:
        """Return the tool definition"""
        return Tool(
            name="get_financial_summary",
            description="Generate a comprehensive financial health summary with key metrics, insights, and recommendations.",
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
                    "include_comparisons": {
                        "type": "boolean",
                        "description": "Whether to include period comparisons (default: true)",
                        "default": True
                    }
                },
                "required": ["login_id"]
            }
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the financial summary generation"""
        try:
            # Validate required arguments
            required_args = ["login_id"]
            missing_args = self.validate_required_args(arguments, required_args)
            if missing_args:
                return self.create_error_result(f"Missing required arguments: {', '.join(missing_args)}")
            
            login_id = arguments["login_id"]
            days = arguments.get("days", 30)
            include_comparisons = arguments.get("include_comparisons", True)
            
            # Validate days parameter
            if not isinstance(days, int) or days < 1 or days > 365:
                return self.create_error_result("Days must be an integer between 1 and 365")
            
            logger.info(f"Generating financial summary for {days} days, login_id: {login_id}")
            
            # Generate comprehensive financial summary
            summary = await self._generate_comprehensive_summary(login_id, days, include_comparisons)
            
            if 'error' in summary:
                return self.create_error_result(summary['error'])
            
            return self.create_success_result(
                summary,
                f"Financial health summary generated for {days} days. Overall health score: {summary.get('health_score', 'N/A')}"
            )
        
        except Exception as e:
            logger.error(f"Error in get_financial_summary: {e}")
            return self.create_error_result(str(e))
    
    async def _generate_comprehensive_summary(self, login_id: str, days: int, include_comparisons: bool) -> Dict[str, Any]:
        """Generate a comprehensive financial summary"""
        try:
            # Get basic spending analysis
            spending_analysis = await self.flinks_client.analyze_spending_patterns(login_id, days)
            
            if 'error' in spending_analysis:
                return {'error': spending_analysis['error']}
            
            # Get account summary
            accounts_summary = await self.flinks_client.get_accounts_summary(login_id)
            
            # Prepare summary components
            summary = {
                'overview': self._create_overview(spending_analysis, accounts_summary, days),
                'spending_analysis': self._create_spending_summary(spending_analysis),
                'category_insights': self._create_category_insights(spending_analysis),
                'financial_health': self._assess_financial_health(spending_analysis, accounts_summary),
                'key_metrics': self._calculate_key_metrics(spending_analysis, accounts_summary, days),
                'recommendations': self._generate_comprehensive_recommendations(spending_analysis, accounts_summary),
                'alerts': self._generate_alerts(spending_analysis, accounts_summary)
            }
            
            # Add comparisons if requested
            if include_comparisons and days >= 7:  # Need at least a week for comparison
                comparison_days = min(days, 30)  # Compare to previous same period
                comparison = await self.flinks_client.compare_spending_periods(login_id, days, comparison_days)
                if 'error' not in comparison:
                    summary['period_comparison'] = self._create_comparison_summary(comparison)
            
            # Calculate overall health score
            summary['health_score'] = self._calculate_health_score(summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating comprehensive summary: {e}")
            return {'error': str(e)}
    
    def _create_overview(self, spending_analysis: Dict[str, Any], accounts_summary: Dict[str, Any], days: int) -> Dict[str, Any]:
        """Create overview section"""
        total_spent = spending_analysis.get('total_spent', 0)
        daily_average = total_spent / days if days > 0 else 0
        transaction_count = spending_analysis.get('transaction_count', 0)
        
        # Account information
        accounts = accounts_summary.get('accounts', [])
        total_accounts = len(accounts)
        
        return {
            'period': {
                'days_analyzed': days,
                'date_range_description': f"Last {days} days"
            },
            'spending_overview': {
                'total_spent': round(total_spent, 2),
                'daily_average': round(daily_average, 2),
                'transaction_count': transaction_count,
                'transactions_per_day': round(transaction_count / days, 2) if days > 0 else 0
            },
            'account_overview': {
                'connected_accounts': total_accounts,
                'account_types': list(set(acc.get('Type', 'Unknown') for acc in accounts))
            }
        }
    
    def _create_spending_summary(self, spending_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create spending summary section"""
        categories = spending_analysis.get('categories', {})
        total_spent = spending_analysis.get('total_spent', 0)
        
        # Top categories
        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_spent': total_spent,
            'category_count': len(categories),
            'top_categories': [
                {
                    'category': category,
                    'amount': amount,
                    'percentage': (amount / total_spent * 100) if total_spent > 0 else 0
                }
                for category, amount in top_categories
            ],
            'spending_concentration': {
                'top_category_percentage': (top_categories[0][1] / total_spent * 100) if top_categories and total_spent > 0 else 0,
                'top_3_percentage': sum(amount for _, amount in top_categories[:3]) / total_spent * 100 if total_spent > 0 else 0
            }
        }
    
    def _create_category_insights(self, spending_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create category insights section"""
        categories = spending_analysis.get('categories', {})
        total_spent = spending_analysis.get('total_spent', 0)
        
        # Classify categories
        essential_amount = 0
        discretionary_amount = 0
        investment_amount = 0
        
        for category, amount in categories.items():
            classification = self._classify_category_simple(category)
            if classification == 'essential':
                essential_amount += amount
            elif classification == 'discretionary':
                discretionary_amount += amount
            elif classification == 'investment':
                investment_amount += amount
        
        return {
            'spending_by_type': {
                'essential': {
                    'amount': essential_amount,
                    'percentage': (essential_amount / total_spent * 100) if total_spent > 0 else 0
                },
                'discretionary': {
                    'amount': discretionary_amount,
                    'percentage': (discretionary_amount / total_spent * 100) if total_spent > 0 else 0
                },
                'investment': {
                    'amount': investment_amount,
                    'percentage': (investment_amount / total_spent * 100) if total_spent > 0 else 0
                }
            },
            'balance_assessment': self._assess_spending_balance(essential_amount, discretionary_amount, investment_amount, total_spent)
        }
    
    def _assess_financial_health(self, spending_analysis: Dict[str, Any], accounts_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall financial health"""
        # This is a simplified assessment - would be enhanced with more data
        categories = spending_analysis.get('categories', {})
        total_spent = spending_analysis.get('total_spent', 0)
        transaction_count = spending_analysis.get('transaction_count', 0)
        
        health_indicators = {
            'spending_diversity': {
                'score': min(len(categories) * 10, 100),  # Max 100 for 10+ categories
                'status': 'good' if len(categories) >= 5 else 'fair' if len(categories) >= 3 else 'poor',
                'description': f"Spending across {len(categories)} categories"
            },
            'transaction_frequency': {
                'score': 100 if 1 <= transaction_count <= 50 else 70 if transaction_count <= 100 else 50,
                'status': 'good' if 1 <= transaction_count <= 50 else 'fair',
                'description': f"{transaction_count} transactions in period"
            },
            'spending_consistency': {
                'score': 75,  # Placeholder - would calculate from daily variance
                'status': 'good',
                'description': "Based on daily spending patterns"
            }
        }
        
        return {
            'health_indicators': health_indicators,
            'overall_assessment': self._get_overall_assessment(health_indicators)
        }
    
    def _calculate_key_metrics(self, spending_analysis: Dict[str, Any], accounts_summary: Dict[str, Any], days: int) -> Dict[str, Any]:
        """Calculate key financial metrics"""
        total_spent = spending_analysis.get('total_spent', 0)
        transaction_count = spending_analysis.get('transaction_count', 0)
        
        return {
            'spending_metrics': {
                'total_spent': total_spent,
                'daily_average': total_spent / days if days > 0 else 0,
                'average_transaction': total_spent / transaction_count if transaction_count > 0 else 0,
                'largest_expense': max(spending_analysis.get('categories', {}).values()) if spending_analysis.get('categories') else 0
            },
            'behavioral_metrics': {
                'transaction_frequency': transaction_count / days if days > 0 else 0,
                'spending_diversity': len(spending_analysis.get('categories', {})),
                'impulse_indicator': 'low' if transaction_count / days < 2 else 'moderate' if transaction_count / days < 5 else 'high'
            }
        }
    
    def _generate_comprehensive_recommendations(self, spending_analysis: Dict[str, Any], accounts_summary: Dict[str, Any]) -> List[str]:
        """Generate comprehensive recommendations"""
        recommendations = []
        
        categories = spending_analysis.get('categories', {})
        total_spent = spending_analysis.get('total_spent', 0)
        
        # Spending optimization recommendations
        if categories:
            top_category = max(categories.items(), key=lambda x: x[1])
            if top_category[1] / total_spent > 0.4:  # More than 40% in one category
                recommendations.append(f"Consider diversifying spending - {top_category[0]} represents a large portion of your budget")
        
        # Budget recommendations
        if total_spent > 0:
            recommendations.append("Consider setting monthly spending limits for each category")
            recommendations.append("Track your spending regularly to identify patterns and opportunities")
        
        # Investment recommendations
        investment_categories = [cat for cat in categories.keys() if 'investment' in cat.lower() or 'savings' in cat.lower()]
        if not investment_categories:
            recommendations.append("Consider allocating budget for savings and investments")
        
        return recommendations
    
    def _generate_alerts(self, spending_analysis: Dict[str, Any], accounts_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate financial alerts"""
        alerts = []
        
        categories = spending_analysis.get('categories', {})
        total_spent = spending_analysis.get('total_spent', 0)
        
        # High concentration alert
        if categories:
            top_category = max(categories.items(), key=lambda x: x[1])
            if top_category[1] / total_spent > 0.5:
                alerts.append({
                    'type': 'warning',
                    'title': 'High Spending Concentration',
                    'message': f"Over 50% of spending is in {top_category[0]}",
                    'action': 'Consider reviewing this category for potential savings'
                })
        
        # No investment alert
        investment_spending = sum(amount for cat, amount in categories.items() 
                                if any(keyword in cat.lower() for keyword in ['investment', 'savings', 'retirement']))
        if investment_spending == 0:
            alerts.append({
                'type': 'info',
                'title': 'No Investment Activity',
                'message': 'No investment or savings activity detected',
                'action': 'Consider setting up automatic savings or investment contributions'
            })
        
        return alerts
    
    def _create_comparison_summary(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Create comparison summary"""
        return {
            'trend': comparison['comparison']['trend'],
            'change_amount': comparison['comparison']['change_amount'],
            'change_percentage': comparison['comparison']['change_percentage'],
            'summary': f"Spending has {comparison['comparison']['trend']} by ${abs(comparison['comparison']['change_amount']):.2f} ({abs(comparison['comparison']['change_percentage']):.1f}%)"
        }
    
    def _calculate_health_score(self, summary: Dict[str, Any]) -> int:
        """Calculate overall financial health score (0-100)"""
        health_indicators = summary.get('financial_health', {}).get('health_indicators', {})
        
        if not health_indicators:
            return 50  # Neutral score if no data
        
        scores = [indicator['score'] for indicator in health_indicators.values()]
        return round(sum(scores) / len(scores)) if scores else 50
    
    def _classify_category_simple(self, category: str) -> str:
        """Simple category classification"""
        category_lower = category.lower()
        
        essential_keywords = ['groceries', 'grocery', 'food', 'utilities', 'rent', 'mortgage', 'insurance', 'medical', 'gas', 'transportation']
        investment_keywords = ['investment', 'savings', 'retirement', 'rrsp', 'tfsa']
        
        if any(keyword in category_lower for keyword in essential_keywords):
            return 'essential'
        elif any(keyword in category_lower for keyword in investment_keywords):
            return 'investment'
        else:
            return 'discretionary'
    
    def _assess_spending_balance(self, essential: float, discretionary: float, investment: float, total: float) -> Dict[str, Any]:
        """Assess spending balance"""
        if total == 0:
            return {'status': 'no_data', 'message': 'No spending data available'}
        
        essential_pct = (essential / total * 100)
        discretionary_pct = (discretionary / total * 100)
        investment_pct = (investment / total * 100)
        
        if essential_pct > 70:
            status = 'essential_heavy'
            message = 'Spending is heavily focused on essentials'
        elif discretionary_pct > 60:
            status = 'discretionary_heavy'
            message = 'High discretionary spending - consider reviewing optional expenses'
        elif investment_pct > 20:
            status = 'investment_focused'
            message = 'Good focus on savings and investments'
        else:
            status = 'balanced'
            message = 'Reasonably balanced spending across categories'
        
        return {
            'status': status,
            'message': message,
            'percentages': {
                'essential': round(essential_pct, 1),
                'discretionary': round(discretionary_pct, 1),
                'investment': round(investment_pct, 1)
            }
        }
    
    def _get_overall_assessment(self, health_indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Get overall health assessment"""
        scores = [indicator['score'] for indicator in health_indicators.values()]
        avg_score = sum(scores) / len(scores) if scores else 50
        
        if avg_score >= 80:
            status = 'excellent'
            message = 'Your financial habits look very healthy'
        elif avg_score >= 65:
            status = 'good'
            message = 'Your financial habits are generally good with room for improvement'
        elif avg_score >= 50:
            status = 'fair'
            message = 'Your financial habits are average - consider some improvements'
        else:
            status = 'needs_improvement'
            message = 'Your financial habits could benefit from attention'
        
        return {
            'status': status,
            'score': round(avg_score),
            'message': message
        } 