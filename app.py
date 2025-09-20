"""
Rufous v2 - Personal Financial Analysis Tool
Streamlit app with local PDF processing and natural language queries
"""

import streamlit as st
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our components
from components.database import RufousDatabase
from components.clean_pdf_processor import CleanPDFProcessor  
from components.chat_handler import ChatHandler
from components.visualizations import FinancialVisualizer
from components.category_manager import CategoryManager
from components.category_training_ui import render_category_management, render_quick_categorize

# Page config
st.set_page_config(
    page_title="Rufous v2 - Financial Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E86C1;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
    }
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        border-left: 4px solid #2E86C1;
        background-color: #f8f9fa;
    }
    .upload-section {
        background-color: #e8f4f8;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if 'database' not in st.session_state:
        st.session_state.database = RufousDatabase()
    
    if 'pdf_processor' not in st.session_state:
        try:
            st.session_state.pdf_processor = CleanPDFProcessor()
        except Exception as e:
            st.error(f"Failed to initialize PDF processor: {e}")
            st.session_state.pdf_processor = None
    
    if 'chat_handler' not in st.session_state:
        try:
            st.session_state.chat_handler = ChatHandler(st.session_state.database)
        except ConnectionError as e:
            st.error(f"Failed to initialize chat handler: {e}")
            st.info("💡 **Setup Instructions:** Set your GROQ_API_KEY environment variable to enable chat features.")
            st.session_state.chat_handler = None
    
    if 'visualizer' not in st.session_state:
        st.session_state.visualizer = FinancialVisualizer()
    
    if 'category_manager' not in st.session_state:
        st.session_state.category_manager = CategoryManager(st.session_state.database.db_path)
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = []

# Sidebar removed for cleaner interface


def process_uploaded_files(uploaded_files: List, default_account_type: str):
    """Process uploaded PDF files"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results = []
    
    for i, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Processing {uploaded_file.name}...")
        progress_bar.progress((i + 1) / len(uploaded_files))
        
        try:
            # Save uploaded file temporarily
            temp_path = Path(f"/tmp/{uploaded_file.name}")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Check if already processed
            if st.session_state.database.is_statement_processed(uploaded_file.name):
                st.warning(f"Statement {uploaded_file.name} already processed. Skipping.")
                continue
            
            # Process PDF
            result = st.session_state.pdf_processor.process_pdf_statement(
                temp_path, 
                default_account_type
            )
            
            if result['status'] == 'success':
                # Store in database
                transactions = result['transactions']
                if transactions:
                    # Add statement record
                    statement_date = transactions[0]['date'] if transactions else None
                    total_amount = sum(t['amount'] for t in transactions)
                    
                    statement_id = st.session_state.database.add_statement(
                        filename=uploaded_file.name,
                        statement_date=statement_date,
                        account_type=default_account_type,
                        transaction_count=len(transactions),
                        total_amount=total_amount
                    )
                    
                    # Add transactions
                    added_count = st.session_state.database.add_transactions(transactions)
                    
                    result['transactions_stored'] = added_count
                    
                    # Run auto-categorization as part of mandatory pipeline
                    if added_count > 0:
                        try:
                            categorized_count = st.session_state.database.auto_categorize_transactions()
                            result['transactions_categorized'] = categorized_count
                            
                            if categorized_count > 0:
                                st.success(f"✅ {uploaded_file.name}: {added_count} transactions stored, {categorized_count} auto-categorized")
                            else:
                                st.success(f"✅ {uploaded_file.name}: {added_count} transactions stored")
                                st.info("💡 No transactions could be auto-categorized. Visit 'Manage Categories' to train the system.")
                        except Exception as e:
                            logger.warning(f"Auto-categorization failed: {e}")
                            st.success(f"✅ {uploaded_file.name}: {added_count} transactions stored")
                            st.warning("⚠️ Auto-categorization failed. Visit 'Manage Categories' to categorize manually.")
                    else:
                        st.success(f"✅ {uploaded_file.name}: {added_count} transactions stored")
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: No transactions extracted")
            else:
                st.error(f"❌ {uploaded_file.name}: {result.get('message', 'Processing failed')}")
            
            results.append({
                'filename': uploaded_file.name,
                'status': result['status'],
                'total_transactions': len(result.get('transactions', [])),
                'message': result.get('message', '')
            })
            
            # Clean up temp file
            temp_path.unlink(missing_ok=True)
            
        except Exception as e:
            st.error(f"❌ Error processing {uploaded_file.name}: {str(e)}")
            results.append({
                'filename': uploaded_file.name,
                'status': 'error',
                'total_transactions': 0,
                'message': str(e)
            })
    
    # Update session state
    st.session_state.processed_files.extend(results)
    
    status_text.text("Processing complete!")
    progress_bar.progress(1.0)
    
    # Show summary
    successful = sum(1 for r in results if r['status'] == 'success')
    total_transactions = sum(r['total_transactions'] for r in results)
    
    st.success(f"Processing Summary: {successful}/{len(results)} files processed successfully. {total_transactions} total transactions added.")

# Old render functions removed - now using unified dashboard
    
    # Check for pre-filled queries (from sidebar or suggestions)
    user_query = None
    
    # Quick query from sidebar
    if hasattr(st.session_state, 'quick_query'):
        user_query = st.session_state.quick_query
        del st.session_state.quick_query
    
    # Query suggestions
    with st.expander("💡 Query Suggestions", expanded=False):
        suggestions = st.session_state.chat_handler.get_query_suggestions()
        cols = st.columns(2)
        for i, suggestion in enumerate(suggestions[:6]):
            with cols[i % 2]:
                if st.button(suggestion, key=f"suggest_{i}"):
                    user_query = suggestion
    
    # Chat input (only get input if no pre-filled query)
    if not user_query:
        user_query = st.chat_input("Ask about your finances...")
    
    if user_query:
        # Add user message to chat history
        st.session_state.chat_history.append({
            'role': 'user',
            'content': user_query,
            'timestamp': datetime.now()
        })
        
        # Process query
        with st.spinner("Analyzing your question..."):
            try:
                result = st.session_state.chat_handler.process_query(user_query)
                
                # Add assistant response
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': result,
                    'timestamp': datetime.now()
                })
                
            except Exception as e:
                st.error(f"Query processing failed: {str(e)}")
    
    # Display chat history
    for message in st.session_state.chat_history[-10:]:  # Show last 10 messages
        with st.container():
            if message['role'] == 'user':
                st.markdown(f"**You:** {message['content']}")
            else:
                result = message['content']
                if isinstance(result, dict) and result.get('status') == 'success':
                    response = result.get('response', {})
                    
                    # Show SQL query if available (for transparency)
                    sql_query = result.get('sql_query')
                    if sql_query:
                        with st.expander("🔍 SQL Query Generated", expanded=False):
                            st.code(sql_query, language='sql')
                            if result.get('sql_explanation'):
                                st.caption(result['sql_explanation'])
                    
                    # Show debug info if available
                    debug_info = result.get('debug_info')
                    if debug_info:
                        with st.expander("🐛 Debug Information", expanded=False):
                            st.json(debug_info)
                    
                    # Show recommendations if available
                    recommendations = response.get('recommendations', [])
                    if recommendations:
                        st.markdown("**💡 Recommendations:**")
                        for rec in recommendations:
                            st.markdown(f"• {rec}")
                    
                    # Show data if available
                    data = result.get('data', {})
                    if data:
                        render_query_results(result)
                elif isinstance(result, dict) and result.get('status') == 'error':
                    st.error(f"**Assistant:** {result.get('message', 'Something went wrong')}")
                    
                    # Show debug info for errors too
                    debug_info = result.get('debug_info')
                    if debug_info:
                        with st.expander("🐛 Error Debug Information", expanded=False):
                            st.json(debug_info)
                else:
                    # Handle unexpected result format
                    if isinstance(result, str):
                        st.markdown(f"**Assistant:** {result}")
                    else:
                        st.error("**Assistant:** I encountered an unexpected error processing your query.")
            
            st.markdown("---")

def render_query_results(query_result: Dict[str, Any]):
    """Render query results with data and visualizations"""
    data = query_result.get('data', {})
    query_type = query_result.get('query_type', '')
    
    # Show key insights
    response = query_result.get('response', {})
    insights = response.get('key_insights', [])
    if insights:
        st.markdown("**Key Insights:**")
        for insight in insights:
            st.markdown(f"• {insight}")
    
    # Handle SQL agent results
    if query_type == 'sql_agent':
        results = data.get('results', [])
        row_count = data.get('row_count', 0)
        
        if results and len(results) > 0:
            with st.expander(f"📋 Query Results ({row_count} rows)", expanded=True):
                df = pd.DataFrame(results)
                if not df.empty:
                    # Format amounts if present
                    if 'amount' in df.columns:
                        df['amount'] = df['amount'].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")
                    
                    st.dataframe(df, use_container_width=True)
        
        return  # Skip legacy visualization code for SQL agent
    
    # Legacy visualization code for backward compatibility
    try:
        fig = None
        
        if query_type == 'category_breakdown':
            categories = data.get('categories', [])
            if categories:
                fig = st.session_state.visualizer.create_spending_by_category_chart(categories)
        
        elif query_type == 'trends':
            monthly_data = data.get('monthly_data', [])
            if monthly_data:
                fig = st.session_state.visualizer.create_monthly_trends_chart(monthly_data)
        
        elif query_type == 'search' or query_type == 'spending_analysis':
            transactions = data.get('transactions', [])
            if transactions:
                fig = st.session_state.visualizer.create_transaction_timeline(transactions)
        
        elif query_type == 'summary':
            stats = data.get('overall_stats', {})
            if stats:
                fig = st.session_state.visualizer.create_dashboard_summary(stats)
        
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        
        # Show data table if relevant
        if 'transactions' in data and len(data['transactions']) > 0:
            with st.expander("📋 Transaction Details", expanded=False):
                df = pd.DataFrame(data['transactions'])
                if not df.empty:
                    # Format for display - include location if available
                    available_cols = ['date', 'description', 'amount', 'category']
                    if 'location' in df.columns:
                        available_cols.insert(2, 'location')
                    
                    display_df = df[available_cols].copy()
                    display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(display_df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Visualization error: {str(e)}")
        logger.error(f"Visualization error: {e}")

def render_dashboard():
    """Render main dashboard with overview"""
    st.markdown("### 📊 Financial Dashboard")
    
    try:
        # Get database stats
        stats = st.session_state.database.get_database_stats()
        
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", stats['total_transactions'])
        with col2:
            st.metric("Total Spent", f"${stats['total_spent']:,.2f}")
        with col3:
            st.metric("Total Returns", f"${stats['total_returns']:,.2f}")
        with col4:
            st.metric("Net Change", f"${stats['net_worth_change']:,.2f}")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Category breakdown
            category_data = st.session_state.database.get_spending_by_category()
            if not category_data.empty:
                fig = st.session_state.visualizer.create_spending_by_category_chart(
                    category_data.to_dict('records')
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Monthly trends
            trends_data = st.session_state.database.get_monthly_trends(6)
            if not trends_data.empty:
                fig = st.session_state.visualizer.create_monthly_trends_chart(
                    trends_data.to_dict('records')
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Recent transactions
        st.markdown("### 🕐 Recent Transactions")
        recent_df = st.session_state.database.get_transactions_df(limit=10)
        if not recent_df.empty:
            # Include location if available
            available_cols = ['date', 'description', 'amount', 'category']
            if 'location' in recent_df.columns:
                available_cols.insert(2, 'location')
            
            display_df = recent_df[available_cols].copy()
            display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No transactions found. Upload some statements to get started!")
    
    except Exception as e:
        st.error(f"Dashboard error: {str(e)}")
        logger.error(f"Dashboard error: {e}")

def render_unified_dashboard():
    """Render the unified main dashboard with chat as primary focus"""
    
    # Main layout: Chat on left (2/3), Upload on right (1/3)
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Chat Analysis Section - Primary focus
        st.markdown("### 💬 Financial Chat")
        render_chat_section()
    
    with col2:
        # PDF Upload Section - Compact on the right
        st.markdown("### 📄 Upload")
        with st.container():
            uploaded_files = st.file_uploader(
                "Drop PDF statements",
                type=['pdf'],
                accept_multiple_files=True,
                help="Upload credit card statements",
                label_visibility="collapsed"
            )
            
            # Always credit since user only uploads credit statements
            default_account_type = "credit"
            
            if uploaded_files and st.session_state.pdf_processor:
                if st.button("🚀 Process", type="primary", use_container_width=True):
                    process_uploaded_files(uploaded_files, default_account_type)

def render_chat_section():
    """Render the chat analysis section for the unified dashboard"""
    
    if not st.session_state.chat_handler:
        st.warning("💡 Chat analysis requires GROQ_API_KEY environment variable")
        return
    
    # Quick query buttons
    st.markdown("#### Quick Insights")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("💰 Monthly Spending", use_container_width=True):
            st.session_state.quick_query = "How much did I spend this month?"
    
    with col2:
        if st.button("🏪 Top Merchants", use_container_width=True):
            st.session_state.quick_query = "What are my top 5 merchants by spending?"
    
    with col3:
        if st.button("📈 Spending Trends", use_container_width=True):
            st.session_state.quick_query = "Show me my spending trends over time"
    
    with col4:
        if st.button("🎯 Category Breakdown", use_container_width=True):
            st.session_state.quick_query = "Break down my spending by category"
    
    # Chat input with clearer labeling
    st.markdown("#### 💬 Ask a Question")
    query = st.text_area(
        "Type your question here:",
        value=getattr(st.session_state, 'quick_query', ''),
        placeholder="e.g., How much did I spend on food last month?",
        key="chat_input",
        label_visibility="collapsed",
        height=100
    )
    
    if st.button("🔍 Analyze", type="primary") and query:
        with st.spinner("Analyzing your financial data..."):
            try:
                result = st.session_state.chat_handler.process_query(query)
                
                # Handle error responses
                if isinstance(result, dict) and result.get('status') == 'error':
                    error_msg = result.get('message', 'Unknown error')
                    
                    # Check for common SQL errors and provide helpful suggestions
                    if 'syntax error' in error_msg.lower():
                        if 'median' in query.lower():
                            st.error("**SQL Error:** SQLite doesn't support MEDIAN function directly.")
                            st.info("💡 **Try instead:** 'average spend in august' or 'spending in august sorted by amount'")
                        else:
                            st.error(f"**SQL Syntax Error:** {error_msg}")
                            st.info("💡 Try rephrasing your question or use simpler terms.")
                    else:
                        st.error(f"**Query Error:** {error_msg}")
                    
                    # Show debug info for errors too
                    with st.expander("🔍 Debug - Error Details", expanded=False):
                        st.json(result)
                    return
                
                # Debug: Show what we're getting (developer requested)
                with st.expander("🔍 Debug - Query Details", expanded=False):
                    st.json(result)
                
                # Extract readable response from the nested structure
                response = "No response generated"
                
                if isinstance(result, dict):
                    # For single transaction queries, create a concise custom response
                    if ('data' in result and 'results' in result['data'] and 
                        len(result['data']['results']) == 1 and 
                        'description' in result['data']['results'][0]):
                        
                        r = result['data']['results'][0]
                        amount = r.get('amount', 0)
                        date = r.get('date', '')
                        description = r.get('description', '')
                        category = r.get('category', '')
                        
                        # Format date nicely
                        try:
                            from datetime import datetime
                            date_obj = datetime.strptime(date, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%B %d, %Y')
                        except:
                            formatted_date = date
                        
                        # Create concise response
                        if 'biggest' in result.get('query', '').lower() or 'largest' in result.get('query', '').lower():
                            response = f"The largest transaction was ${amount:,.2f}, which occurred on {formatted_date}, at {description}."
                        elif 'smallest' in result.get('query', '').lower():
                            response = f"The smallest transaction was ${amount:,.2f}, which occurred on {formatted_date}, at {description}."
                        else:
                            response = f"The transaction was ${amount:,.2f}, which occurred on {formatted_date}, at {description}."
                    
                    # Check if there's a nested response dict (fallback)
                    elif 'response' in result and isinstance(result['response'], dict):
                        nested_response = result['response']
                        if 'summary' in nested_response and nested_response['summary'] != "Found 6 results":
                            response = nested_response['summary']
                        elif 'detailed_response' in nested_response and "Your query returned" not in nested_response['detailed_response']:
                            response = nested_response['detailed_response']
                        else:
                            # AI response failed, create manual response from data
                            response = create_manual_response(result)
                    # Check direct fields (fallback)
                    elif 'summary' in result and result['summary'] != "Found 6 results":
                        response = result['summary']
                    elif 'detailed_response' in result and "Your query returned" not in result['detailed_response']:
                        response = result['detailed_response']
                    else:
                        # AI response failed, create manual response from data
                        response = create_manual_response(result)
                
                # Clean up concatenated text issues (more aggressive)
                if isinstance(response, str):
                    import re
                    # Fix bullet point formatting first
                    response = re.sub(r'•([A-Z])', r'• \1', response)  # "•Uncategorized" -> "• Uncategorized"
                    response = re.sub(r'(\))•', r')\n• ', response)  # "%)•" -> "%)\n• "
                    
                    # Fix number formatting
                    response = re.sub(r'(\d+),(\d+)', r'\1,\2', response)  # Keep commas in numbers
                    response = re.sub(r'(\d+)([a-zA-Z])', r'\1 \2', response)  # "2025broken" -> "2025 broken"
                    response = re.sub(r'([a-zA-Z])(\d+)', r'\1 \2', response)  # "year2025" -> "year 2025"
                    
                    # Fix currency and percentage formatting
                    response = re.sub(r'(\$\d+(?:\.\d+)?)([a-zA-Z])', r'\1 \2', response)  # "$1,953.14The" -> "$1,953.14 The"
                    response = re.sub(r'(\d+(?:\.\d+)?%?)([A-Z])', r'\1 \2', response)  # "22.9•Shopping" -> "22.9 •Shopping"
                    
                    # Fix punctuation spacing
                    response = re.sub(r'([.,])([a-zA-Z])', r'\1 \2', response)  # ",broken" -> ", broken"
                    response = re.sub(r'([a-zA-Z])([.,])', r'\1\2', response)  # "year ," -> "year,"
                    
                    # Fix parentheses
                    response = re.sub(r'(\d+(?:\.\d+)?)(\()', r'\1 \2', response)  # "794.60(" -> "794.60 ("
                    response = re.sub(r'(\))([A-Z])', r'\1 \2', response)  # ")Bills" -> ") Bills"
                
                # Display response in a cleaner format
                with st.container():
                    st.markdown(f"**You:** {query}")
                    st.markdown(f"**Analysis:** {response}")
                    st.markdown("---")
                
                # Add to chat history
                st.session_state.chat_history.append({
                    'query': query,
                    'response': response,
                    'timestamp': datetime.now()
                })
                
                # Clear quick query
                if hasattr(st.session_state, 'quick_query'):
                    del st.session_state.quick_query
                
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                logger.error(f"Chat analysis error: {e}")
    
    # Recent chat history (last 3)
    if st.session_state.chat_history:
        st.markdown("#### Recent Analysis")
        for chat in st.session_state.chat_history[-3:]:
            with st.expander(f"🔍 {chat['query'][:50]}..."):
                st.markdown(f"**Query:** {chat['query']}")
                st.markdown(f"**Response:** {chat['response']}")
                st.caption(f"Asked: {chat['timestamp'].strftime('%Y-%m-%d %H:%M')}")

def create_manual_response(result):
    """Create a manual response when AI generation fails"""
    if not (isinstance(result, dict) and 'data' in result and 'results' in result['data']):
        return "Unable to process query results"
    
    results = result['data']['results']
    if not results:
        return "No results found for your query"
    
    # Check if this is a category breakdown query
    if all('category' in r and 'total_spent' in r for r in results):
        total_spent = sum(float(r.get('total_spent', 0)) for r in results)
        response_parts = [f"You spent a total of ${total_spent:,.2f} in 2025, broken down by category:"]
        
        for r in results:
            category = r.get('category') or 'Uncategorized'
            amount = float(r.get('total_spent', 0))
            percentage = (amount / total_spent * 100) if total_spent > 0 else 0
            response_parts.append(f"• {category}: ${amount:,.2f} ({percentage:.1f}%)")
        
        return "\n".join(response_parts)
    
    # Check if this is a single transaction query (biggest/smallest expense, etc.)
    if len(results) == 1 and all(field in results[0] for field in ['date', 'description', 'amount']):
        r = results[0]
        amount = r.get('amount', 0)
        date = r.get('date', 'Unknown date')
        description = r.get('description', 'Unknown merchant')
        category = r.get('category') or 'Uncategorized'
        
        # Format the date nicely
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%B %d, %Y')
        except:
            formatted_date = date
        
        return f"The transaction was ${amount:,.2f} at {description} on {formatted_date} (Category: {category})"
    
    # Generic fallback for other query types
    return f"Found {len(results)} results from your query."

def render_management_tab():
    """Render the management tab with statements, categories and transactions"""
    
    # Sub-tabs for management functions
    mgmt_tab1, mgmt_tab2, mgmt_tab3 = st.tabs(["📄 Statements", "🎯 Categories", "📋 Transactions"])
    
    with mgmt_tab1:
        st.markdown("### 📄 Statement Management")
        render_statement_management()
    
    with mgmt_tab2:
        st.markdown("### 🎯 Category Management")
        render_category_management(st.session_state.category_manager)
    
    with mgmt_tab3:
        st.markdown("### 📋 All Transactions")
        render_transaction_list()

def render_statement_management():
    """Render statement management with uploaded files and missing months"""
    try:
        # Get all processed statements from the database
        # Since get_processed_statements doesn't exist, let's query directly
        try:
            import sqlite3
            conn = sqlite3.connect(st.session_state.database.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT filename, statement_date, transaction_count, total_amount, processed_at 
                FROM statements 
                ORDER BY statement_date DESC
            """)
            statements = [dict(zip([col[0] for col in cursor.description], row)) 
                         for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            st.error(f"Error querying statements: {e}")
            statements = []
        
        if not statements:
            st.info("No statements uploaded yet. Go to the Dashboard tab to upload your first statement.")
            return
        
        st.markdown("#### 📊 Quick Stats")
        col1, col2, col3, col4 = st.columns(4)
        stats = st.session_state.database.get_database_stats()
        
        with col1:
            st.metric("Total Transactions", stats['total_transactions'])
        with col2:
            st.metric("Total Spent", f"${stats['total_spent']:,.2f}")
        with col3:
            st.metric("Net Change", f"${stats['net_worth_change']:,.2f}")
        with col4:
            st.metric("Statements Processed", stats['total_statements'])
        
        st.markdown("---")
        
        # Uploaded statements list
        st.markdown("#### 📋 Uploaded Statements")
        
        # Convert to DataFrame for better display
        import pandas as pd
        df = pd.DataFrame(statements)
        
        if not df.empty:
            # Format the data for display
            display_df = df.copy()
            if 'statement_date' in display_df.columns:
                display_df['statement_date'] = pd.to_datetime(display_df['statement_date']).dt.strftime('%Y-%m')
            if 'total_amount' in display_df.columns:
                display_df['total_amount'] = display_df['total_amount'].apply(lambda x: f"${x:,.2f}")
            if 'processed_at' in display_df.columns:
                display_df['processed_at'] = pd.to_datetime(display_df['processed_at']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Select columns to show
            columns_to_show = ['filename', 'statement_date', 'transaction_count', 'total_amount', 'processed_at']
            available_columns = [col for col in columns_to_show if col in display_df.columns]
            
            st.dataframe(
                display_df[available_columns],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "filename": "Statement File",
                    "statement_date": "Month",
                    "transaction_count": "Transactions",
                    "total_amount": "Total Amount",
                    "processed_at": "Processed"
                }
            )
            
            # Missing months analysis
            st.markdown("---")
            st.markdown("#### 📅 Missing Months Analysis")
            
            # Get unique months from statements
            if 'statement_date' in df.columns:
                uploaded_months = set()
                for date_str in df['statement_date'].dropna():
                    try:
                        date_obj = pd.to_datetime(date_str)
                        uploaded_months.add(date_obj.strftime('%Y-%m'))
                    except:
                        continue
                
                if uploaded_months:
                    # Find gaps in months
                    from datetime import datetime, timedelta
                    import calendar
                    
                    # Get date range
                    min_date = min([pd.to_datetime(d) for d in df['statement_date'].dropna()])
                    max_date = max([pd.to_datetime(d) for d in df['statement_date'].dropna()])
                    
                    # Generate all months in range
                    current = min_date.replace(day=1)
                    all_months = set()
                    
                    while current <= max_date:
                        all_months.add(current.strftime('%Y-%m'))
                        # Move to next month
                        if current.month == 12:
                            current = current.replace(year=current.year + 1, month=1)
                        else:
                            current = current.replace(month=current.month + 1)
                    
                    missing_months = sorted(all_months - uploaded_months)
                    
                    if missing_months:
                        st.warning(f"**Missing {len(missing_months)} months:** {', '.join(missing_months)}")
                        st.info("💡 Upload statements for these months to get complete financial analysis.")
                    else:
                        st.success("✅ No missing months detected in your date range!")
                else:
                    st.info("Unable to analyze missing months - no valid dates found.")
            else:
                st.info("Statement dates not available for missing month analysis.")
        
    except Exception as e:
        st.error(f"Error loading statement management: {e}")
        logger.error(f"Statement management error: {e}")

def render_transaction_list():
    """Render searchable transaction list"""
    try:
        # Get all transactions using the available method
        transactions_df = st.session_state.database.get_transactions_df()
        transactions = transactions_df.to_dict('records') if not transactions_df.empty else []
        
        if not transactions:
            st.info("No transactions found. Upload some bank statements first!")
            return
        
        # Convert to DataFrame for better display
        import pandas as pd
        df = pd.DataFrame(transactions)
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Date range filter
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                min_date = df['date'].min().date()
                max_date = df['date'].max().date()
                
                date_range = st.date_input(
                    "Date Range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
        
        with col2:
            # Category filter
            categories = df['category'].unique() if 'category' in df.columns else []
            selected_categories = st.multiselect(
                "Categories",
                options=categories,
                default=[]
            )
        
        with col3:
            # Amount filter
            if 'amount' in df.columns:
                min_amount = float(df['amount'].min())
                max_amount = float(df['amount'].max())
                
                amount_range = st.slider(
                    "Amount Range",
                    min_value=min_amount,
                    max_value=max_amount,
                    value=(min_amount, max_amount),
                    step=0.01
                )
        
        # Apply filters
        filtered_df = df.copy()
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['date'].dt.date >= start_date) & 
                (filtered_df['date'].dt.date <= end_date)
            ]
        
        if selected_categories:
            filtered_df = filtered_df[filtered_df['category'].isin(selected_categories)]
        
        if 'amount' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['amount'] >= amount_range[0]) & 
                (filtered_df['amount'] <= amount_range[1])
            ]
        
        # Display results
        st.markdown(f"**Showing {len(filtered_df)} of {len(df)} transactions**")
        
        # Format for display
        display_columns = ['date', 'description', 'amount', 'category', 'merchant']
        display_df = filtered_df[display_columns].copy()
        
        if 'date' in display_df.columns:
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        
        if 'amount' in display_df.columns:
            display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:.2f}")
        
        # Display table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Export option
        if st.button("📥 Export to CSV"):
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
    except Exception as e:
        st.error(f"Error loading transactions: {e}")
        logger.error(f"Transaction list error: {e}")

def process_uploaded_files(uploaded_files, default_account_type):
    """Process multiple uploaded PDF files"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_files = len(uploaded_files)
    processed_count = 0
    
    for i, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Processing {uploaded_file.name}...")
        progress_bar.progress((i) / total_files)
        
        try:
            # Save temporary file
            temp_path = Path("temp") / uploaded_file.name
            temp_path.parent.mkdir(exist_ok=True)
            
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Check if already processed
            if st.session_state.database.is_statement_processed(uploaded_file.name):
                st.warning(f"Statement {uploaded_file.name} already processed. Skipping.")
                continue
            
            # Process PDF
            result = st.session_state.pdf_processor.process_pdf_statement(
                temp_path, 
                default_account_type
            )
            
            if result['status'] == 'success':
                # Store in database (this was missing!)
                transactions = result['transactions']
                if transactions:
                    # Add statement record
                    statement_date = transactions[0]['date'] if transactions else None
                    total_amount = sum(t['amount'] for t in transactions)
                    
                    statement_id = st.session_state.database.add_statement(
                        filename=uploaded_file.name,
                        statement_date=statement_date,
                        account_type=default_account_type,
                        transaction_count=len(transactions),
                        total_amount=total_amount
                    )
                    
                    # Add transactions to database
                    added_count = st.session_state.database.add_transactions(transactions)
                    
                    # Run auto-categorization
                    try:
                        categorized_count = st.session_state.database.auto_categorize_transactions()
                        if categorized_count > 0:
                            st.success(f"✅ {uploaded_file.name}: {added_count} transactions added, {categorized_count} auto-categorized")
                        else:
                            st.success(f"✅ {uploaded_file.name}: {added_count} transactions added")
                            st.info("💡 No transactions auto-categorized. Visit Management → Categories to set up rules.")
                    except Exception as e:
                        st.success(f"✅ {uploaded_file.name}: {added_count} transactions added")
                        st.warning(f"⚠️ Auto-categorization failed: {e}")
                    
                    processed_count += 1
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: No transactions extracted")
            else:
                error_msg = result.get('message', result.get('error', 'Processing failed'))
                st.error(f"❌ {uploaded_file.name}: {error_msg}")
            
            # Clean up
            temp_path.unlink(missing_ok=True)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            st.error(f"❌ {uploaded_file.name}: Processing failed - {str(e)}")
            
            # Show detailed error in expander
            with st.expander(f"🔍 Error Details for {uploaded_file.name}", expanded=False):
                st.code(error_details)
            
            logger.error(f"File processing error for {uploaded_file.name}: {e}")
            logger.error(f"Full traceback: {error_details}")
    
    progress_bar.progress(1.0)
    status_text.text(f"Complete! Processed {processed_count} of {total_files} files.")
    
    if processed_count > 0:
        st.balloons()
        st.success(f"🎉 Successfully processed {processed_count} statement(s)!")
        st.info("💡 Page will refresh in a moment to show your new data...")
        
        # Add a small delay before rerun so user can see the messages
        import time
        time.sleep(2)
        st.rerun()

def main():
    """Main application with unified interface"""
    # Initialize session state
    initialize_session_state()
    
    # Compact header
    st.markdown('<h2 style="margin-bottom: 0.5rem;">📊 Rufous v2</h2>', unsafe_allow_html=True)
    
    # No sidebar - cleaner interface
    
    # Main tabs
    tab1, tab2 = st.tabs(["🏠 Dashboard", "⚙️ Management"])
    
    with tab1:
        render_unified_dashboard()
    
    with tab2:
        render_management_tab()
    
    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; color: #666; font-size: 0.8rem;">Rufous v2 - Local Financial Analysis • Data stays on your device</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()