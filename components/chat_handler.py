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
        """Process natural language query using hybrid++ approach"""
        try:
            # Ultra-fast lane: Exact pattern matching for common queries
            pattern_result = self._try_exact_patterns(user_query)
            if pattern_result:
                return pattern_result
            
            # Smart lane: Direct LLM with relevant data
            return self._llm_with_smart_data(user_query)
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                'status': 'error',
                'message': f"I couldn't process that query: {str(e)}",
                'query': user_query
            }
    
    def _try_exact_patterns(self, user_query: str) -> Optional[Dict[str, Any]]:
        """Try exact pattern matching for ultra-common queries"""
        query_lower = user_query.lower()
        
        # Pattern: Last N transactions (e.g., "last 5 transactions", "show me my last 10 transactions")
        last_n_match = re.search(r'(?:last|recent)\s+(\d+)\s+transaction', query_lower)
        if last_n_match:
            n = int(last_n_match.group(1))
            return self.get_last_n_transactions(n)
        
        # Pattern: Recent transactions (general)
        if any(phrase in query_lower for phrase in ['last transactions', 'recent transactions']) and not any(phrase in query_lower for phrase in ['where', 'location']):
            return self.get_last_n_transactions(10)  # Default to 10
        
        # Pattern: Recent transactions with locations
        if any(phrase in query_lower for phrase in ['where', 'location', 'recent transactions']):
            if any(phrase in query_lower for phrase in ['recent', 'last', 'latest']):
                return self.get_recent_transactions_with_locations()
                
        # Pattern: Location-based spending
        location_keywords = ['in toronto', 'in kingston', 'in vancouver', 'in calgary']
        for keyword in location_keywords:
            if keyword in query_lower:
                location = keyword.replace('in ', '').title()
                return self.get_spending_by_location(location)
        
        return None  # No exact pattern matched
    
    def _smart_data_fetch(self, user_query: str) -> List[Dict[str, Any]]:
        """Intelligently fetch relevant data based on query content"""
        query_lower = user_query.lower()
        
        # Determine data scope based on query keywords
        limit = 10  # Conservative default
        search_term = None
        location_filter = None
        category_filter = None
        start_date = None
        end_date = None
        
        # Look for queries that need more comprehensive data
        comprehensive_keywords = ['all', 'total', 'analyze', 'analysis', 'pattern', 'trend', 'summary', 'overview', 'breakdown']
        if any(keyword in query_lower for keyword in comprehensive_keywords):
            limit = 500  # Much larger scope for comprehensive analysis (6+ months)
            
        # Look for queries that explicitly want everything
        if any(phrase in query_lower for phrase in ['all my transactions', 'all transactions', 'everything', 'complete history']):
            limit = 1000  # Get full history
        
        # Extract numbers for transaction counts
        number_matches = re.findall(r'\b(\d+)\b', query_lower)
        if number_matches:
            # Use the first reasonable number as limit
            for num_str in number_matches:
                num = int(num_str)
                if 1 <= num <= 100:  # Reasonable transaction count
                    limit = num
                    break
        
        # Look for specific time periods (be more precise to avoid false matches)
        if any(period in query_lower for period in ['last month only', 'past month only', 'previous month only']) or \
           (('last month' in query_lower or 'past month' in query_lower) and 'months' not in query_lower):
            # Get actual data date range for single month analysis
            recent_df = self.db.get_transactions_df(limit=100)
            if not recent_df.empty:
                latest_date = pd.to_datetime(recent_df['date']).max().date()
                first_of_month = latest_date.replace(day=1)
                last_month_end = first_of_month - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
                start_date = last_month_start
                end_date = last_month_end
                limit = max(limit, 50)  # Don't override comprehensive limits
        
        elif any(period in query_lower for period in ['last year', 'this year', 'past year']):
            limit = 200  # Get more for yearly analysis
            
        elif any(period in query_lower for period in ['last week', 'this week']):
            limit = 20
            
        # Look for spending queries (need more data for analysis)
        if any(word in query_lower for word in ['spending', 'spent', 'expenses', 'expense', 'cost', 'budget']):
            limit = max(limit, 100)  # Get more data for spending analysis
            
        # Look for comparison or superlative queries (biggest, most, least, etc.)
        if any(word in query_lower for word in ['biggest', 'largest', 'most', 'least', 'smallest', 'top', 'bottom', 'expensive', 'cheapest']):
            limit = max(limit, 300)  # Need more data to find real extremes across time
            
        # Look for location mentions
        cities = ['toronto', 'kingston', 'vancouver', 'calgary', 'ottawa', 'montreal', 'fernie']
        for city in cities:
            if city in query_lower:
                location_filter = city.title()
                limit = 50  # Get more for location analysis
                break
        
        # Look for category mentions
        categories = ['food', 'grocery', 'gas', 'restaurant', 'coffee', 'health', 'shopping']
        for category in categories:
            if category in query_lower:
                category_filter = category
                limit = 30
                break
        
        # Look for amount-based queries (but don't override comprehensive limits)
        if any(phrase in query_lower for phrase in ['over $', 'above $', 'more than $', 'greater than $']):
            limit = max(limit, 50)  # Get more data for filtering, but don't override larger limits
            
        # Look for merchant/search terms
        if 'from ' in query_lower:
            # Extract text after 'from'
            from_match = re.search(r'from ([a-zA-Z\s]+)', query_lower)
            if from_match:
                search_term = from_match.group(1).strip()
                limit = 20
        
        # Fetch the appropriate data
        if search_term or location_filter:
            if location_filter:
                df = self.db.search_transactions_with_location(search_term or '', location_filter)
            else:
                df = self.db.search_transactions(search_term, limit=limit)
        else:
            df = self.db.get_transactions_df(start_date, end_date, category_filter, limit)
        
        # Convert to clean format for LLM (optimize for API limits)
        clean_transactions = []
        for txn in df.to_dict('records'):
            # Handle potential None values safely
            category = txn.get('category') or 'Unknown'
            location = txn.get('location') or 'No location'
            description = str(txn['description']) if txn['description'] else 'No description'
            
            clean_transactions.append({
                'date': str(txn['date']).split()[0],  # Just date part
                'description': description[:40],  # Truncate long descriptions
                'amount': txn['amount'],
                'category': category[:20],  # Truncate categories
                'location': location[:30]  # Truncate locations
            })
        
        # If we have too much data for the API, create a summary approach
        if len(clean_transactions) > 100:
            # For large datasets, send summary + sample instead of all data
            summary_data = self._create_transaction_summary(clean_transactions)
            return summary_data
        
        return clean_transactions
    
    def _create_transaction_summary(self, transactions: List[Dict]) -> List[Dict]:
        """Create a summary representation for large datasets"""
        import pandas as pd
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(transactions)
        
        # Create summary statistics
        summary = []
        
        # Add date range info
        summary.append({
            'type': 'summary',
            'date_range': f"{df['date'].min()} to {df['date'].max()}",
            'total_transactions': len(transactions),
            'total_amount': df['amount'].sum(),
            'spending_total': df[df['amount'] < 0]['amount'].sum() if (df['amount'] < 0).any() else 0
        })
        
        # Add monthly breakdown
        df['month'] = df['date'].str[:7]  # YYYY-MM
        monthly = df.groupby('month').agg({
            'amount': ['count', 'sum'],
            'date': 'first'
        }).round(2)
        
        for month in monthly.index:
            summary.append({
                'type': 'monthly_summary',
                'month': month,
                'transaction_count': int(monthly.loc[month, ('amount', 'count')]),
                'total_amount': float(monthly.loc[month, ('amount', 'sum')])
            })
        
        # Add category breakdown (top categories)
        if 'category' in df.columns:
            cat_summary = df[df['amount'] < 0].groupby('category')['amount'].sum().sort_values().head(10)
            for cat, amount in cat_summary.items():
                summary.append({
                    'type': 'category_summary',
                    'category': cat,
                    'total_spent': float(amount)
                })
        
        # Add sample transactions (recent ones)
        recent_samples = transactions[:20]  # Most recent 20
        for txn in recent_samples:
            txn['type'] = 'sample_transaction'
            summary.append(txn)
        
        return summary
    
    def _llm_with_smart_data(self, user_query: str) -> Dict[str, Any]:
        """Send query with relevant clean data directly to LLM"""
        try:
            # Get relevant data
            transactions = self._smart_data_fetch(user_query)
            
            if not transactions:
                return {
                    'status': 'success',
                    'query': user_query,
                    'query_type': 'no_data',
                    'data': {'transactions': [], 'count': 0},
                    'response': {
                        'summary': 'No transactions found',
                        'detailed_response': 'I couldn\'t find any transactions matching your query.',
                        'key_insights': ['No transaction data available']
                    }
                }
            
            # Create system prompt for financial analysis
            system_prompt = """You are a helpful financial assistant. Answer user questions about their transaction data precisely and conversationally.

Rules:
1. Answer based ONLY on the provided transaction data
2. Be specific with numbers, dates, and amounts
3. If asked for N items, return exactly N items
4. Format currency as $X.XX
5. Return response as JSON with: summary, detailed_response, key_insights"""
            
            # Create user prompt with clean data
            user_prompt = f"""Transaction Data:
{json.dumps(transactions, indent=2)}

User Question: {user_query}

Please analyze this data and answer the user's question. Return your response as JSON with:
- summary: Brief one-line summary
- detailed_response: Detailed answer to their question  
- key_insights: Array of 2-3 insights from the data"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Call LLM
            response_text = self._call_groq_api(messages, max_tokens=500, temperature=0.3)
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    response_data = json.loads(json_match.group(0))
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed: {e}")
                    # Fallback if JSON parsing fails
                    response_data = {
                        'summary': 'Analysis complete',
                        'detailed_response': response_text.replace('\n', ' ').replace('\t', ' '),
                        'key_insights': []
                    }
            else:
                # Fallback if no JSON found
                response_data = {
                    'summary': 'Analysis complete',
                    'detailed_response': response_text.replace('\n', ' ').replace('\t', ' '),
                    'key_insights': []
                }
            
            # Save to query history
            self.db.save_query(
                query_text=user_query,
                query_type='llm_analysis',
                results_summary=response_data.get('summary', ''),
                favorited=False
            )
            
            return {
                'status': 'success',
                'query': user_query,
                'query_type': 'llm_analysis',
                'data': {
                    'transactions': transactions,
                    'count': len(transactions),
                    'data_scope': f"Analyzed {len(transactions)} transactions"
                },
                'response': response_data
            }
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                'status': 'error',
                'message': f"I couldn't analyze your data: {str(e)}",
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
  "parameters": {{"category": "food", "time_period": "last_30_days", "location": null}},
  "visualization": "bar_chart"
}}

Examples:
- "spending on food" -> spending_analysis, category: food
- "transactions from Starbucks" -> search, search_term: Starbucks  
- "monthly trends" -> trends
- "spending in Toronto" -> search, location: Toronto
- "location of transactions" -> search (for recent transactions with location info)
- "where did I spend" -> search (for location-based analysis)"""
        
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
        
        # Calculate ranges based on actual data dates
        if time_period.lower() == 'last_month':
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
                
                expenses = df[df['amount'] < 0]
                total_spent = abs(expenses['amount'].sum()) if not expenses.empty else 0
                
                return {
                    'transactions': df.to_dict('records'),
                    'total_spent': total_spent,
                    'transaction_count': len(expenses),
                    'average_expense': abs(expenses['amount'].mean()) if not expenses.empty else 0,
                    'date_range': f"{start_date} to {end_date}" if start_date and end_date else f"Found {len(df)} transactions",
                    'actual_data_range': f"{df['date'].min()} to {df['date'].max()}" if not df.empty else "No data"
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
        """Generate natural language response from data results"""
        
        # Format data for AI with clear structure
        transactions = data_result.get('transactions', [])
        
        data_summary = {
            'total_spent': data_result.get('total_spent', 0),
            'transaction_count': data_result.get('transaction_count', len(transactions)),
            'date_range': data_result.get('actual_data_range', 'Unknown'),
            'sample_transactions': transactions[:3] if transactions else []
        }
        
        response_prompt = f"""User asked: "{user_query}"

Found {len(transactions)} transactions with total spending of ${data_summary['total_spent']:.2f}

Data range: {data_summary['date_range']}
Sample transactions: {json.dumps(data_summary['sample_transactions'], default=str)[:300]}

Generate helpful response as JSON:
{{
  "summary": "Brief summary with actual numbers",
  "detailed_response": "Answer with specific amounts and dates from the data",
  "key_insights": ["insight based on actual data"]
}}"""
        
        try:
            messages = [
                {"role": "system", "content": "You are a helpful financial assistant. Generate conversational responses about financial data."},
                {"role": "user", "content": response_prompt}
            ]
            
            response_text = self._call_groq_api(messages, max_tokens=400, temperature=0.3)
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                # Fallback to simple text response
                return {
                    'summary': 'Query completed',
                    'detailed_response': response_text,
                    'key_insights': [],
                    'suggested_followup': None
                }
        
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            # Fallback response
            return {
                'summary': 'Data retrieved successfully',
                'detailed_response': f"I found {len(data_result.get('data', []))} results for your query.",
                'key_insights': [],
                'suggested_followup': None
            }
    
    def get_query_suggestions(self) -> List[str]:
        """Get common query suggestions for users"""
        return [
            "How much did I spend last month?",
            "Show me all transactions over $100",
            "What are my top spending categories?",
            "Where are my recent transactions?",
            "Show me all transactions from Amazon", 
            "What's my monthly spending trend?",
            "How much did I spend on food this year?",
            "Show me all transactions in Kingston",
            "What was my biggest expense last week?",
            "How much did I spend in Toronto last month?"
        ]
    
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
            
            expenses = df[df['amount'] < 0]
            total_spent = abs(expenses['amount'].sum()) if not expenses.empty else 0
            
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
    
    def get_last_n_transactions(self, n: int = 5) -> Dict[str, Any]:
        """Get the last N transactions - dedicated function for simple transaction lists"""
        try:
            df = self.db.get_transactions_df(limit=n)
            
            if df.empty:
                return {
                    'status': 'success',
                    'query_type': 'last_transactions',
                    'data': {
                        'transactions': [],
                        'count': 0
                    },
                    'response': {
                        'summary': 'No transactions found',
                        'detailed_response': 'No transactions were found in your account.',
                        'key_insights': ['No transaction history available']
                    }
                }
            
            transactions = df.to_dict('records')
            total_amount = df['amount'].sum()
            
            # Format transactions for display
            formatted_transactions = []
            for i, txn in enumerate(transactions, 1):
                formatted_transactions.append({
                    'rank': i,
                    'date': txn['date'],
                    'description': txn['description'],
                    'amount': txn['amount'],
                    'location': txn.get('location', 'No location'),
                    'category': txn.get('category', 'Uncategorized')
                })
            
            return {
                'status': 'success',
                'query_type': 'last_transactions',
                'data': {
                    'transactions': formatted_transactions,
                    'count': len(transactions),
                    'total_amount': total_amount,
                    'date_range': f"{df['date'].min()} to {df['date'].max()}",
                    'requested_count': n
                },
                'response': {
                    'summary': f"Here are your last {len(transactions)} transactions",
                    'detailed_response': f"Showing your {len(transactions)} most recent transactions from {df['date'].min()} to {df['date'].max()}. Total amount: ${total_amount:.2f}",
                    'key_insights': [
                        f"Most recent: {transactions[0]['description']} for ${transactions[0]['amount']:.2f}" if transactions else "No transactions",
                        f"Date range: {df['date'].min()} to {df['date'].max()}",
                        f"Total amount: ${total_amount:.2f}"
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get last {n} transactions: {e}")
            return {
                'status': 'error',
                'message': f"Failed to retrieve last {n} transactions: {str(e)}"
            }