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
    """Render the unified main dashboard with all key features"""
    
    # PDF Upload Section
    st.markdown("### 📄 Upload Bank Statements")
    with st.container():
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            uploaded_files = st.file_uploader(
                "Drop your PDF bank statements here",
                type=['pdf'],
                accept_multiple_files=True,
                help="Upload multiple PDF statements to process them all at once"
            )
        
        with col2:
            # Always credit since user only uploads credit statements
            default_account_type = "credit"
            st.info("💳 Credit Card Statements")
        
        if uploaded_files and st.session_state.pdf_processor:
            if st.button("🚀 Process All Statements", type="primary"):
                process_uploaded_files(uploaded_files, default_account_type)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Financial Overview Section
    st.markdown("### 📊 Financial Overview")
    
    try:
        # Get monthly data for visualization  
        monthly_data = None  # Simplified for now - will implement charts later
        
        # Key metrics in a clean layout
        stats = st.session_state.database.get_database_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", stats['total_transactions'])
        with col2:
            st.metric("Total Spent", f"${stats['total_spent']:,.2f}")
        with col3:
            st.metric("Net Change", f"${stats['net_worth_change']:,.2f}")
        with col4:
            st.metric("Statements Processed", stats['total_statements'])
        
        if stats['total_transactions'] == 0:
            st.info("📈 Upload your first credit card statement to see financial insights!")
            
    except Exception as e:
        st.error(f"Error loading financial overview: {e}")
        logger.error(f"Dashboard overview error: {e}")
    
    st.markdown("---")
    
    # Chat Analysis Section
    st.markdown("### 💬 Chat Analysis")
    render_chat_section()

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
    
    # Chat input
    query = st.text_input(
        "Ask about your finances:",
        value=getattr(st.session_state, 'quick_query', ''),
        placeholder="e.g., How much did I spend on food last month?",
        key="chat_input"
    )
    
    if st.button("🔍 Analyze", type="primary") and query:
        with st.spinner("Analyzing your financial data..."):
            try:
                response = st.session_state.chat_handler.handle_query(query)
                
                # Display response
                st.markdown('<div class="chat-message">', unsafe_allow_html=True)
                st.markdown(f"**You:** {query}")
                st.markdown(f"**Analysis:** {response}")
                st.markdown('</div>', unsafe_allow_html=True)
                
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

def render_management_tab():
    """Render the management tab with categories and transactions"""
    
    # Sub-tabs for management functions
    mgmt_tab1, mgmt_tab2 = st.tabs(["🎯 Category Management", "📋 Transaction List"])
    
    with mgmt_tab1:
        st.markdown("### 🎯 Category Management")
        render_category_management(st.session_state.category_manager)
    
    with mgmt_tab2:
        st.markdown("### 📋 All Transactions")
        render_transaction_list()

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
                st.success(f"✅ {uploaded_file.name}: {result['transactions_added']} transactions added")
                processed_count += 1
            else:
                st.error(f"❌ {uploaded_file.name}: {result['message']}")
            
            # Clean up
            temp_path.unlink(missing_ok=True)
            
        except Exception as e:
            st.error(f"❌ {uploaded_file.name}: Processing failed - {e}")
            logger.error(f"File processing error: {e}")
    
    progress_bar.progress(1.0)
    status_text.text(f"Complete! Processed {processed_count} of {total_files} files.")
    
    if processed_count > 0:
        st.balloons()
        st.rerun()

def main():
    """Main application with unified interface"""
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.markdown('<h1 class="main-header">📊 Rufous v2</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">Personal Financial Analysis with Natural Language Queries</p>', unsafe_allow_html=True)
    
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