"""
SQL Agent for Natural Language to SQL Query Generation
Intelligent database querying based on user questions
"""

import sqlite3
import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
import pandas as pd
from .database import RufousDatabase

logger = logging.getLogger(__name__)


class SQLAgent:
    """Agent that converts natural language questions to SQL queries"""
    
    def __init__(self, database: RufousDatabase, groq_api_caller=None):
        """Initialize SQL agent with database connection"""
        self.db = database
        self.groq_api_caller = groq_api_caller
        self.schema_info = self._get_schema_info()
        self.data_context = self._get_data_context()
    
    def _get_schema_info(self) -> str:
        """Get database schema information for the AI"""
        return """
DATABASE SCHEMA:

transactions table:
- id (INTEGER PRIMARY KEY)
- date (DATE) - Transaction date in YYYY-MM-DD format
- description (TEXT) - Transaction description/merchant name
- amount (DECIMAL) - Transaction amount (POSITIVE values represent money spent/expenses, NEGATIVE values represent income/credits/refunds)
- balance (DECIMAL) - Account balance after transaction
- account_type (TEXT) - 'debit' or 'credit'
- category (TEXT) - Spending category (Food & Dining, Transportation, etc.)
- subcategory (TEXT) - More specific category
- merchant (TEXT) - Extracted merchant name
- location (TEXT) - Transaction location if available
- is_transfer (BOOLEAN) - True if this is a transfer/payment
- statement_file (TEXT) - Source PDF filename
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

IMPORTANT NOTES:
- Expenses/spending are POSITIVE amounts (purchases, money going out)
- Income/credits/refunds are NEGATIVE amounts (money coming in)
- For spending queries, use WHERE amount > 0 (money spent)
- For income queries, use WHERE amount < 0 (money received)
- When calculating "money spent" or "expenses", sum positive amounts
- When user asks about "spending" or "expenses", they want positive amounts
- Use date >= and date <= for date ranges
- Use LIKE for text matching (case insensitive with UPPER())
- Use ABS(amount) when calculating total spending
- Exclude transfers with: WHERE is_transfer = FALSE
"""
    
    def process_question(self, question: str) -> Dict[str, Any]:
        """Convert natural language question to SQL and execute"""
        try:
            logger.info(f"SQL Agent processing: {question}")
            
            # Refresh data context in case new data was added
            self.data_context = self._get_data_context()
            
            # Generate SQL query from question
            logger.info("Step 1: Generating SQL query...")
            sql_result = self._generate_sql_query(question)
            logger.info(f"SQL generation result: {sql_result}")
            
            if sql_result is None:
                logger.error("SQL generation returned None - likely Groq API failure")
                return {
                    'status': 'error',
                    'message': 'SQL generation failed - AI service returned None',
                    'question': question,
                    'debug_info': {'sql_result': None}
                }
            
            if sql_result.get('status') != 'success':
                logger.error(f"SQL generation failed: {sql_result}")
                return sql_result
            
            # Execute the SQL query
            query = sql_result['query']
            explanation = sql_result['explanation']
            
            logger.info(f"Step 2: Executing SQL: {query}")
            
            # Execute query and get results
            results = self._execute_query(query)
            logger.info(f"Step 3: Query executed, got {len(results) if isinstance(results, list) else 'unknown'} results")
            
            return {
                'status': 'success',
                'question': question,
                'sql_query': query,
                'explanation': explanation,
                'results': results,
                'row_count': len(results) if isinstance(results, list) else 1,
                'debug_info': {
                    'sql_generation': sql_result,
                    'execution_success': True,
                    'result_type': type(results).__name__
                }
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"SQL Agent error: {e}")
            logger.error(f"Full traceback: {error_trace}")
            return {
                'status': 'error',
                'message': f"Failed to process question: {str(e)}",
                'question': question,
                'debug_info': {
                    'error': str(e),
                    'traceback': error_trace
                }
            }
    
    def _generate_sql_query(self, question: str) -> Dict[str, Any]:
        """Use AI to generate SQL query from natural language"""
        
        if not self.groq_api_caller:
            logger.error("Groq API caller is None")
            return {
                'status': 'error',
                'message': 'AI service not available - groq_api_caller is None'
            }
        
        logger.info(f"Groq API caller available: {type(self.groq_api_caller)}")
        
        # Get current date for context
        current_date = date.today()
        current_year = current_date.year
        
        # Temporarily disable data context to debug
        data_context_safe = ""
        try:
            data_context_safe = self.data_context
            logger.info(f"Data context loaded: {data_context_safe[:100]}...")
        except Exception as e:
            logger.error(f"Error loading data context: {e}")
            data_context_safe = "\nDATA CONTEXT: Error loading context"
        
        prompt = f"""You are a SQL expert. Convert this natural language question to a SQL query.

QUESTION: "{question}"

CURRENT DATE: {current_date.isoformat()} (Today is {current_date.strftime('%B %d, %Y')})
CURRENT YEAR: {current_year}

{self.schema_info}

{data_context_safe}

EXAMPLES:
Q: "What was my biggest purchase in August?"
SQL: SELECT date, description, amount, category FROM transactions WHERE date >= '2024-08-01' AND date <= '2024-08-31' AND amount > 0 AND is_transfer = FALSE ORDER BY amount DESC LIMIT 1;

Q: "How much did I spend on food last month?"
SQL: SELECT SUM(amount) as total_spent FROM transactions WHERE category LIKE '%Food%' AND date >= '2024-07-01' AND date <= '2024-07-31' AND amount > 0 AND is_transfer = FALSE;

Q: "How much did I spend on coffee this year?"
SQL: SELECT SUM(amount) as total_spent, COUNT(*) as transaction_count FROM transactions WHERE (UPPER(description) LIKE '%STARBUCKS%' OR UPPER(description) LIKE '%TIM HORTONS%' OR UPPER(description) LIKE '%COFFEE%' OR category LIKE '%Coffee%') AND date >= '{current_year}-01-01' AND date <= '{current_year}-12-31' AND amount > 0 AND is_transfer = FALSE;

Q: "Show me all transactions over $100"
SQL: SELECT date, description, amount, category FROM transactions WHERE ABS(amount) > 100 AND is_transfer = FALSE ORDER BY date DESC;

Q: "What are my top 5 spending categories this year?"
SQL: SELECT category, SUM(amount) as total_spent, COUNT(*) as transaction_count FROM transactions WHERE amount > 0 AND is_transfer = FALSE AND date >= '{current_year}-01-01' GROUP BY category ORDER BY total_spent DESC LIMIT 5;

Q: "Show me spending this year"
SQL: SELECT SUM(amount) as total_spent FROM transactions WHERE amount > 0 AND is_transfer = FALSE AND date >= '{current_year}-01-01' AND date <= '{current_year}-12-31';

Return ONLY this JSON format:
{{
  "query": "SELECT statement here",
  "explanation": "Brief explanation of what this query does",
  "query_type": "single_transaction|summary|list|aggregate"
}}

CRITICAL RULES:
- Always exclude transfers: WHERE is_transfer = FALSE
- Expenses are positive amounts: WHERE amount > 0 for spending
- Returns/refunds are negative amounts: WHERE amount < 0 for returns
- Use SUM(amount) when summing expenses (no ABS needed)
- Use proper date formats: YYYY-MM-DD
- For "biggest/largest purchase" use ORDER BY amount DESC LIMIT 1 (highest positive)
- For spending totals, use SUM(amount) WHERE amount > 0
- IMPORTANT: "this year" means {current_year}, "last year" means {current_year-1}
- For coffee/restaurants: Search description text (STARBUCKS, TIM HORTONS, etc.) not just category
- Use UPPER(description) LIKE '%KEYWORD%' for text matching
- Current date context: Today is {current_date.isoformat()}"""

        try:
            # Debug: Check API key availability
            import os
            api_key = os.getenv('GROQ_API_KEY')
            logger.info(f"API Key available: {'Yes' if api_key else 'No'} (length: {len(api_key) if api_key else 0})")
            
            messages = [
                {"role": "system", "content": "You are a SQL expert. Generate accurate SQL queries for financial data analysis. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ]
            
            logger.info(f"Calling Groq API with prompt length: {len(prompt)}")
            logger.info(f"About to call self.groq_api_caller with {len(messages)} messages")
            
            response_text = self.groq_api_caller(messages, max_tokens=300, temperature=0.1)
            
            logger.info(f"Groq API call completed. Response type: {type(response_text)}")
            logger.info(f"Groq API response: {response_text[:200]}..." if response_text else "RESPONSE IS NONE OR EMPTY")
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            sql_result = json.loads(json_match.group(0))
            
            # Validate required fields
            if not sql_result.get('query'):
                raise ValueError("No SQL query generated")
            
            return {
                'status': 'success',
                'query': sql_result['query'],
                'explanation': sql_result.get('explanation', 'SQL query generated'),
                'query_type': sql_result.get('query_type', 'unknown')
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"SQL generation failed: {e}")
            logger.error(f"Full traceback: {error_trace}")
            error_result = {
                'status': 'error',
                'message': f"Could not generate SQL query: {str(e)}",
                'debug_info': {
                    'error': str(e),
                    'traceback': error_trace
                }
            }
            logger.info(f"Returning error result: {error_result}")
            return error_result
        
        # This should never be reached, but adding as a safety net
        logger.error("CRITICAL: _generate_sql_query reached end without returning anything!")
        return {
            'status': 'error',
            'message': 'Internal error: method completed without proper return'
        }
    
    def _get_data_context(self) -> str:
        """Get information about what data is actually available"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Simple count first
                cursor.execute("SELECT COUNT(*) FROM transactions")
                count_result = cursor.fetchone()
                
                if not count_result or count_result[0] == 0:
                    return "\nDATA CONTEXT: No transaction data available"
                
                total_transactions = count_result[0]
                
                # Get date range
                cursor.execute("SELECT MIN(date), MAX(date) FROM transactions")
                date_result = cursor.fetchone()
                
                if date_result and date_result[0]:
                    earliest, latest = date_result
                    
                    # Extract year from latest date for "this year" context
                    latest_year = latest[:4] if latest else "unknown"
                    
                    return f"""
DATA CONTEXT:
- Total transactions: {total_transactions}
- Date range: {earliest} to {latest}
- Most recent data year: {latest_year}

IMPORTANT: When user says "this year", use {latest_year} (the year with actual data), not the current calendar year!
"""
                else:
                    return f"\nDATA CONTEXT: {total_transactions} transactions found, but date information unavailable"
                    
        except Exception as e:
            logger.error(f"Failed to get data context: {e}")
            return "\nDATA CONTEXT: Could not determine data availability"
    
    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                results = []
                for row in rows:
                    row_dict = dict(row)
                    # Convert any date objects to strings
                    for key, value in row_dict.items():
                        if isinstance(value, (date, datetime)):
                            row_dict[key] = value.isoformat()
                    results.append(row_dict)
                
                return results
                
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise
    
    def explain_results(self, question: str, sql_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate natural language explanation of SQL results"""
        
        if not self.groq_api_caller:
            return {
                'summary': 'Query completed',
                'detailed_response': f"Found {sql_result.get('row_count', 0)} results",
                'key_insights': []
            }
        
        results = sql_result.get('results', [])
        sql_query = sql_result.get('sql_query', '')
        
        # Format results for AI explanation
        results_text = json.dumps(results[:5], indent=2, default=str)  # Show first 5 results
        
        prompt = f"""Explain these SQL query results in natural language.

ORIGINAL QUESTION: "{question}"
SQL QUERY: {sql_query}
RESULTS: {results_text}
TOTAL ROWS: {len(results)}

Provide a clear, conversational explanation in JSON format:
{{
  "summary": "Direct answer to the user's question",
  "detailed_response": "Comprehensive explanation with specific details from the results",
  "key_insights": ["2-3 specific insights from the actual data"]
}}

CRITICAL FORMATTING RULES - FOLLOW EXACTLY:
- ALWAYS put spaces around ALL words and numbers
- NEVER run words together like "meaningthatthe" - use "meaning that the"
- NEVER run numbers with words like "was14.99" - use "was $14.99"
- ALWAYS use spaces: "largest transaction in this group was $14.99" NOT "largesttransactioninthisgroupwas14.99"

EXAMPLES OF CORRECT FORMATTING:
✅ GOOD: "The total number of transactions under $15 is 40."
❌ BAD: "Thetotalnumberoftransactionsunder$15is40."

✅ GOOD: "All of these 40 transactions have amounts less than $15."
❌ BAD: "Allofthese40transactionshaveamountslessthan$15."

✅ GOOD: "The largest transaction was $14.99 on August 8, 2025."
❌ BAD: "Thelargesttransactionwas$14.99onAugust8,2025."

- Read each sentence out loud to check spacing
- Every word must be separated by spaces
- Every number must have spaces around it

IMPORTANT:
- Answer their exact question first
- Use specific numbers, dates, and amounts from the results
- Be conversational and helpful
- If it's a single transaction, mention the merchant, date, and amount
- If it's a summary, provide the total and context"""
        
        try:
            messages = [
                {"role": "system", "content": "You are a financial advisor explaining query results. CRITICAL: Always use proper spacing between ALL words and numbers. Never run words together. Be specific and conversational with perfect formatting."},
                {"role": "user", "content": prompt}
            ]
            
            response_text = self.groq_api_caller(messages, max_tokens=400, temperature=0.3)
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    # Clean up formatting issues in the response
                    result = self._clean_response_formatting(result)
                    return result
                except json.JSONDecodeError:
                    pass
            
            # Fallback response
            return {
                'summary': f"Found {len(results)} results",
                'detailed_response': f"Your query returned {len(results)} results. The data shows specific information about your financial transactions.",
                'key_insights': [f"Query returned {len(results)} records", "Data available for analysis"]
            }
            
        except Exception as e:
            logger.error(f"Result explanation failed: {e}")
            return {
                'summary': 'Query completed',
                'detailed_response': f"Found {len(results)} results for your question.",
                'key_insights': []
            }
    
    def _clean_response_formatting(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up common formatting issues in AI responses"""
        import re
        
        def clean_text(text: str) -> str:
            if not isinstance(text, str):
                return text
            
            # Fix unicode minus signs
            text = text.replace('−', '-')
            text = text.replace('–', '-')
            text = text.replace('—', '-')
            
            # Fix common concatenation issues
            text = re.sub(r'(\d+)([A-Za-z])', r'\1 \2', text)  # "10August" -> "10 August"
            text = re.sub(r'([A-Za-z])(\d+)', r'\1 \2', text)  # "August10" -> "August 10"
            text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)   # "onAugust" -> "on August"
            
            # Fix currency formatting
            text = re.sub(r'(\$?)(-?\d+\.?\d*)(on|at|for|in)', r'\1\2 \3', text)
            
            # Fix date formatting issues
            text = re.sub(r'(\d{4}),?and', r'\1, and', text)
            text = re.sub(r'(\d{4}),?at', r'\1, at', text)
            
            # Fix common word concatenations
            text = re.sub(r'andthe', 'and the', text)
            text = re.sub(r'onthe', 'on the', text)
            text = re.sub(r'forthe', 'for the', text)
            text = re.sub(r'atthe', 'at the', text)
            text = re.sub(r'ofthe', 'of the', text)
            text = re.sub(r'inthe', 'in the', text)
            text = re.sub(r'tothe', 'to the', text)
            
            # Clean up extra spaces
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            return text
        
        # Clean all text fields in the response
        cleaned_response = {}
        for key, value in response.items():
            if isinstance(value, str):
                cleaned_response[key] = clean_text(value)
            elif isinstance(value, list):
                cleaned_response[key] = [clean_text(item) if isinstance(item, str) else item for item in value]
            else:
                cleaned_response[key] = value
        
        return cleaned_response
    
    def get_sample_questions(self) -> List[str]:
        """Get sample questions that work well with SQL agent"""
        return [
            "What was my biggest purchase in August?",
            "How much did I spend on food last month?",
            "Show me all transactions over $100",
            "What are my top 5 spending categories this year?",
            "How much did I spend at Shoppers Drug Mart?",
            "What's my average transaction amount?",
            "Show me all my transactions in Toronto",
            "How much did I spend between July 1st and August 31st?",
            "What was my most expensive restaurant purchase?",
            "How many transactions did I have in August?"
        ]

