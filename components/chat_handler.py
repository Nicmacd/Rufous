"""
Natural Language Query Handler using Groq API
Converts user questions to database operations and provides insights
"""

import logging
import json
import re
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta
import requests
import pandas as pd
from dotenv import load_dotenv

from .database import RufousDatabase
from .sql_agent import SQLAgent

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class ChatHandler:
    """Handles natural language queries about financial data"""
    
    def __init__(self, database: RufousDatabase, model_name: str = "llama-3.3-70b-versatile"):
        """Initialize with database and Groq model"""
        self.db = database
        self.model_name = model_name
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.api_key = os.getenv('GROQ_API_KEY')
        self._check_groq_connection()
        
        # Initialize SQL agent for intelligent querying
        self.sql_agent = SQLAgent(database, self._call_groq_api)
    
    def _check_groq_connection(self):
        """Verify Groq API key and connection"""
        if not self.api_key:
            raise ConnectionError("GROQ_API_KEY environment variable not set")
        
        try:
            # Test connection with a simple request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            test_payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10,
                "temperature": 0.1
            }
            
            response = requests.post(self.groq_url, json=test_payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Chat handler initialized with Groq {self.model_name}")
            
        except Exception as e:
            logger.error(f"Groq connection failed: {e}")
            raise ConnectionError(f"Please check your GROQ_API_KEY: {e}")
    
    def _call_groq_api(self, messages: List[Dict], max_tokens: int = 500, temperature: float = 0.1) -> str:
        """Make API call to Groq"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9
        }
        
        try:
            response = requests.post(self.groq_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process natural language query using SQL agent"""
        try:
            logger.info(f"Processing query: {user_query}")
            
            # Use SQL agent to convert question to SQL and execute
            sql_result = self.sql_agent.process_question(user_query)
            
            if sql_result['status'] != 'success':
                return {
                    'status': 'error',
                    'message': sql_result.get('message', 'Query processing failed'),
                    'query': user_query
                }
            
            # Generate natural language explanation of results
            response = self.sql_agent.explain_results(user_query, sql_result)
            
            # Save successful query to history
            self.db.save_query(
                query_text=user_query,
                query_type='sql_agent',
                results_summary=response.get('summary', ''),
                favorited=False
            )
            
            return {
                'status': 'success',
                'query': user_query,
                'query_type': 'sql_agent',
                'sql_query': sql_result.get('sql_query'),
                'sql_explanation': sql_result.get('explanation'),
                'data': {
                    'results': sql_result.get('results', []),
                    'row_count': sql_result.get('row_count', 0)
                },
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                'status': 'error',
                'message': f"I couldn't process that query: {str(e)}",
                'query': user_query
            }
    
    def _analyze_query(self, user_query: str) -> Dict[str, Any]:
        """Analyze user query to determine intent and parameters"""
        
        analysis_prompt = f"""Analyze this financial query and return JSON with query type and parameters.

Query: "{user_query}"

Types: search, spending_analysis, category_breakdown, trends, comparison, summary, budget

Return JSON format:
{{
  "type": "spending_analysis",
  "parameters": {{"category": "food", "time_period": "august", "location": null}},
  "visualization": "bar_chart"
}}

Examples:
- "spending on food" -> spending_analysis, category: food
- "august spending" -> spending_analysis, time_period: august
- "how much did I spend in august" -> spending_analysis, time_period: august
- "what did I spend the most on last month" -> spending_analysis + category_breakdown
- "biggest purchase in august" -> spending_analysis, time_period: august
- "largest transaction" -> spending_analysis
- "transactions from Starbucks" -> search, search_term: Starbucks  
- "monthly trends" -> trends
- "spending in Toronto" -> search, location: Toronto
- "location of transactions" -> search (for recent transactions with location info)
- "where did I spend" -> search (for location-based analysis)

For spending analysis queries, ALWAYS include category breakdown in the response."""
        
        try:
            messages = [
                {"role": "system", "content": "You are a financial data analyst. Analyze user queries and return structured JSON responses."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response_text = self._call_groq_api(messages, max_tokens=300, temperature=0.1)
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            analysis = json.loads(json_match.group(0))
            
            # Add computed time ranges
            if 'time_range' not in analysis and 'parameters' in analysis:
                time_range = self._compute_time_range(analysis['parameters'].get('time_period'))
                if time_range:
                    analysis['time_range'] = time_range
            
            return analysis
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return {
                'type': 'error',
                'message': f"I couldn't understand that query. Please try rephrasing."
            }
    
    def _compute_time_range(self, time_period: str) -> Optional[Dict[str, str]]:
        """Convert natural language time period to date range based on actual data"""
        if not time_period:
            return None
        
        # Get the actual date range of user's data to make smart calculations
        try:
            recent_df = self.db.get_transactions_df(limit=100)
            if recent_df.empty:
                return None
            
            latest_date = pd.to_datetime(recent_df['date']).max().date()
            earliest_date = pd.to_datetime(recent_df['date']).min().date()
            
            # Use the latest transaction date as reference instead of today
            reference_date = latest_date
            
        except Exception:
            # Fallback to current date if data access fails
            reference_date = date.today()
        
        # Handle specific month names
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        time_period_lower = time_period.lower()
        
        # Check if it's a specific month name
        for month_name, month_num in month_names.items():
            if month_name in time_period_lower:
                # Find the year - use the latest year from data or current year
                year = reference_date.year
                if month_num > reference_date.month:
                    year -= 1  # Previous year if month hasn't occurred yet this year
                
                start_date = date(year, month_num, 1)
                # Get last day of month
                if month_num == 12:
                    end_date = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(year, month_num + 1, 1) - timedelta(days=1)
                
                return {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
        
        # Calculate ranges based on actual data dates
        if time_period_lower == 'last_month':
            # Get the month before the latest transaction month
            first_of_ref_month = reference_date.replace(day=1)
            last_day_of_last_month = first_of_ref_month - timedelta(days=1)
            first_of_last_month = last_day_of_last_month.replace(day=1)
            start_date = first_of_last_month
            end_date = last_day_of_last_month
        elif time_period.lower() == 'last_30_days':
            start_date = reference_date - timedelta(days=30)
            end_date = reference_date
        elif time_period.lower() == 'this_month':
            start_date = reference_date.replace(day=1)
            end_date = reference_date
        elif time_period.lower() == 'last_3_months':
            start_date = reference_date - timedelta(days=90)
            end_date = reference_date
        elif time_period.lower() == 'this_year':
            start_date = reference_date.replace(month=1, day=1)
            end_date = reference_date
        elif time_period.lower() == 'last_year':
            start_date = reference_date.replace(year=reference_date.year-1, month=1, day=1)
            end_date = reference_date.replace(year=reference_date.year-1, month=12, day=31)
        else:
            # Default to last 30 days for unknown periods
            start_date = reference_date - timedelta(days=30)
            end_date = reference_date
        
        return {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
    
    def _execute_data_query(self, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database query based on analysis"""
        query_type = query_analysis.get('type')
        parameters = query_analysis.get('parameters', {})
        time_range = query_analysis.get('time_range', {})
        
        start_date = None
        end_date = None
        if time_range:
            start_date = datetime.fromisoformat(time_range['start_date']).date() if time_range.get('start_date') else None
            end_date = datetime.fromisoformat(time_range['end_date']).date() if time_range.get('end_date') else None
        
        try:
            if query_type == 'search':
                search_term = parameters.get('search_term', '')
                location_filter = parameters.get('location')
                
                # If no specific search term, get recent transactions for location analysis
                if not search_term and not location_filter:
                    df = self.db.get_transactions_df(limit=10)
                elif location_filter:
                    df = self.db.search_transactions_with_location(search_term, location_filter)
                else:
                    df = self.db.search_transactions(search_term, limit=10)
                    
                return {
                    'transactions': df.to_dict('records') if not df.empty else [],
                    'count': len(df),
                    'total_amount': df['amount'].sum() if not df.empty else 0,
                    'has_locations': 'location' in df.columns and df['location'].notna().sum() > 0 if not df.empty else False
                }
            
            elif query_type == 'spending_analysis':
                category = parameters.get('category')
                df = self.db.get_transactions_df(start_date, end_date, category)
                
                if df.empty:
                    return {
                        'transactions': [],
                        'total_spent': 0,
                        'transaction_count': 0,
                        'summary': 'No transactions found for this period'
                    }
                
                expenses = df[df['amount'] > 0]
                total_spent = expenses['amount'].sum() if not expenses.empty else 0
                
                # Get category breakdown for detailed analysis
                category_breakdown = self.db.get_spending_by_category(start_date, end_date)
                
                return {
                    'transactions': df.to_dict('records'),
                    'total_spent': total_spent,
                    'transaction_count': len(expenses),
                    'average_expense': expenses['amount'].mean() if not expenses.empty else 0,
                    'date_range': f"{start_date} to {end_date}" if start_date and end_date else f"Found {len(df)} transactions",
                    'actual_data_range': f"{df['date'].min()} to {df['date'].max()}" if not df.empty else "No data",
                    'category_breakdown': category_breakdown.to_dict('records') if not category_breakdown.empty else [],
                    'top_categories': category_breakdown.head(5).to_dict('records') if not category_breakdown.empty else []
                }
            
            elif query_type == 'category_breakdown':
                df = self.db.get_spending_by_category(start_date, end_date)
                return {
                    'categories': df.to_dict('records') if not df.empty else [],
                    'total_categories': len(df),
                    'top_category': df.iloc[0]['category'] if not df.empty else None
                }
            
            elif query_type == 'trends':
                months = 12  # Default to 12 months
                if 'months' in parameters:
                    months = parameters['months']
                
                df = self.db.get_monthly_trends(months)
                return {
                    'monthly_data': df.to_dict('records') if not df.empty else [],
                    'trend_period': f"Last {months} months"
                }
            
            elif query_type == 'summary':
                stats = self.db.get_database_stats()
                recent_df = self.db.get_transactions_df(
                    start_date=date.today() - timedelta(days=30)
                )
                
                return {
                    'overall_stats': stats,
                    'recent_activity': {
                        'last_30_days_transactions': len(recent_df),
                        'last_30_days_spending': abs(recent_df[recent_df['amount'] < 0]['amount'].sum()) if not recent_df.empty else 0
                    }
                }
            
            else:
                # Default: return recent transactions
                df = self.db.get_transactions_df(limit=20)
                return {
                    'recent_transactions': df.to_dict('records') if not df.empty else [],
                    'message': 'Showing recent transactions'
                }
        
        except Exception as e:
            logger.error(f"Data query execution failed: {e}")
            return {
                'error': str(e),
                'data': []
            }
    
    def _generate_response(self, user_query: str, query_analysis: Dict[str, Any], 
                          data_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate intelligent AI response for complex financial analysis"""
        
        # Get the data we need
        transactions = data_result.get('transactions', [])
        category_breakdown = data_result.get('category_breakdown', [])
        total_spent = data_result.get('total_spent', 0)
        
        # Prepare comprehensive data for AI analysis
        data_for_ai = {
            'total_spent': total_spent,
            'transaction_count': len(transactions),
            'category_breakdown': category_breakdown[:10],  # Top 10 categories
            'sample_transactions': transactions[:10] if transactions else [],
            'date_range': data_result.get('actual_data_range', 'Unknown'),
            'query_type': query_analysis.get('type', 'unknown')
        }
        
        # Create a rich prompt for AI analysis
        analysis_prompt = f"""You are a financial advisor analyzing spending data. Answer the user's SPECIFIC question first, then provide insights.

User Question: "{user_query}"

Financial Data:
- Total Spent: ${total_spent:.2f}
- Transaction Count: {len(transactions)}
- Date Range: {data_for_ai['date_range']}

Top Transactions (sorted by amount):
{self._format_transactions_for_ai(transactions)}

Category Breakdown:
{self._format_categories_for_ai(category_breakdown)}

CRITICAL: If they ask about "biggest purchase" or "largest transaction", look at the transaction list above and identify the specific transaction with the highest dollar amount (most negative number).

Provide intelligent financial insights in this exact JSON format:
{{
  "summary": "Direct answer to their specific question with exact transaction details",
  "detailed_response": "Comprehensive answer starting with the specific transaction/amount they asked about, then broader analysis",
  "key_insights": ["Specific insights about the actual data, not generic advice"],
  "recommendations": ["Actionable recommendations based on their actual spending patterns"]
}}

IMPORTANT: 
- Answer their EXACT question first (biggest purchase = specific transaction and amount)
- Use the ACTUAL transaction data provided above
- Be specific with merchant names, dates, and amounts
- Don't give generic advice - use their real data"""
        
        try:
            messages = [
                {"role": "system", "content": "You are an expert financial advisor. Analyze spending data and provide intelligent, actionable insights. Always respond in valid JSON format."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response_text = self._call_groq_api(messages, max_tokens=600, temperature=0.3)
            
            # Parse JSON response more carefully
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    parsed_response = json.loads(json_match.group(0))
                    # Ensure all required fields exist
                    return {
                        'summary': parsed_response.get('summary', 'Analysis completed'),
                        'detailed_response': parsed_response.get('detailed_response', 'Financial analysis provided'),
                        'key_insights': parsed_response.get('key_insights', []),
                        'recommendations': parsed_response.get('recommendations', [])
                    }
                except json.JSONDecodeError as je:
                    logger.error(f"JSON parsing failed: {je}")
                    return self._create_fallback_response(user_query, data_for_ai)
            else:
                logger.warning("No JSON found in AI response")
                return self._create_fallback_response(user_query, data_for_ai)
        
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            return self._create_fallback_response(user_query, data_for_ai)
    
    def _format_categories_for_ai(self, categories: List[Dict]) -> str:
        """Format category data for AI analysis"""
        if not categories:
            return "No category data available"
        
        formatted = []
        for cat in categories[:8]:  # Top 8 categories
            formatted.append(f"- {cat['category']}: ${cat['total_spent']:.2f} ({cat['transaction_count']} transactions)")
        return "\n".join(formatted)
    
    def _format_transactions_for_ai(self, transactions: List[Dict]) -> str:
        """Format transaction data for AI analysis"""
        if not transactions:
            return "No transaction data available"
        
        # Sort by amount (most negative = biggest purchase) for better analysis
        sorted_transactions = sorted(transactions, key=lambda x: x.get('amount', 0))
        
        formatted = []
        for i, txn in enumerate(sorted_transactions[:10]):  # Show top 10 by amount
            amount = txn.get('amount', 0)
            desc = txn.get('description', 'Unknown')
            date = txn.get('date', 'Unknown')
            category = txn.get('category', 'Uncategorized')
            
            # Mark the biggest purchase
            prefix = "BIGGEST: " if i == 0 and amount > 0 else ""
            formatted.append(f"- {prefix}{date}: ${amount:.2f} | {desc} | {category}")
        
        return "\n".join(formatted)
    
    def _create_fallback_response(self, user_query: str, data: Dict) -> Dict[str, Any]:
        """Create a fallback response when AI fails"""
        total_spent = data['total_spent']
        transaction_count = data['transaction_count']
        
        # Simple pattern matching for common queries
        if 'biggest' in user_query.lower() or 'largest' in user_query.lower():
            return {
                'summary': f"Analysis of your largest expenses",
                'detailed_response': f"Based on your data, you have ${total_spent:.2f} in total spending across {transaction_count} transactions. I can help you identify your largest expenses and spending patterns.",
                'key_insights': [
                    f"Total spending: ${total_spent:.2f}",
                    f"Transaction count: {transaction_count}",
                    "Consider reviewing your largest expense categories"
                ],
                'recommendations': [
                    "Review your top spending categories for optimization opportunities",
                    "Track monthly spending trends to identify patterns"
                ]
            }
        
        return {
            'summary': f"Found ${total_spent:.2f} in spending data",
            'detailed_response': f"I analyzed your spending data and found ${total_spent:.2f} across {transaction_count} transactions. The AI analysis will help identify patterns and opportunities for savings.",
            'key_insights': [
                f"Total analyzed: ${total_spent:.2f}",
                f"Transactions: {transaction_count}",
                "Data ready for detailed analysis"
            ],
            'recommendations': [
                "Ask specific questions about categories or time periods",
                "Try queries like 'where can I save money?' or 'what's my biggest expense category?'"
            ]
        }
    
    def get_query_suggestions(self) -> List[str]:
        """Get common query suggestions for users"""
        return self.sql_agent.get_sample_questions()
    
    def get_recent_transactions_with_locations(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent transactions with location info - dedicated function"""
        try:
            df = self.db.get_transactions_df(limit=limit)
            
            if df.empty:
                return {
                    'status': 'success',
                    'transactions': [],
                    'summary': 'No recent transactions found'
                }
            
            transactions = df.to_dict('records')
            location_count = df['location'].notna().sum() if 'location' in df.columns else 0
            
            return {
                'status': 'success',
                'query_type': 'recent_transactions',
                'data': {
                    'transactions': transactions,
                    'count': len(transactions),
                    'locations_found': location_count,
                    'date_range': f"{df['date'].min()} to {df['date'].max()}",
                    'total_amount': df['amount'].sum()
                },
                'response': {
                    'summary': f"Found {len(transactions)} recent transactions",
                    'detailed_response': f"Here are your {len(transactions)} most recent transactions. {location_count} have location information. Total amount: ${df['amount'].sum():.2f}",
                    'key_insights': [
                        f"Most recent transaction: {transactions[0]['description']}" if transactions else "No transactions",
                        f"{location_count} out of {len(transactions)} transactions have location data",
                        f"Date range: {df['date'].min()} to {df['date'].max()}"
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {e}")
            return {
                'status': 'error',
                'message': f"Failed to retrieve recent transactions: {str(e)}"
            }
    
    def get_spending_by_location(self, location: str = None, limit: int = 50) -> Dict[str, Any]:
        """Get spending breakdown by location - dedicated function"""
        try:
            if location:
                df = self.db.search_transactions_with_location('', location)
            else:
                df = self.db.get_transactions_df(limit=limit)
                df = df[df['location'].notna()] if 'location' in df.columns else df
            
            if df.empty:
                return {
                    'status': 'success',
                    'transactions': [],
                    'summary': f'No transactions found for location: {location}' if location else 'No transactions with location data'
                }
            
            expenses = df[df['amount'] > 0]
            total_spent = expenses['amount'].sum() if not expenses.empty else 0
            
            return {
                'status': 'success',
                'query_type': 'location_spending',
                'data': {
                    'transactions': df.to_dict('records'),
                    'count': len(df),
                    'total_spent': total_spent,
                    'location_filter': location,
                    'unique_locations': df['location'].unique().tolist() if 'location' in df.columns else []
                },
                'response': {
                    'summary': f"Found {len(df)} transactions" + (f" in {location}" if location else " with location data"),
                    'detailed_response': f"Total spending: ${total_spent:.2f} across {len(df)} transactions" + (f" in {location}" if location else ""),
                    'key_insights': [
                        f"Total spent: ${total_spent:.2f}",
                        f"Number of transactions: {len(df)}",
                        f"Average per transaction: ${total_spent/len(df):.2f}" if len(df) > 0 else "No transactions"
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get location spending: {e}")
            return {
                'status': 'error',
                'message': f"Failed to analyze location spending: {str(e)}"
            }