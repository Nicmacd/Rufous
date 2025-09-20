"""
Category Training UI Components
Streamlit interface for training merchant categorization
"""

import streamlit as st
import pandas as pd
from typing import Dict, List
from .category_manager import CategoryManager


def render_category_training(category_manager: CategoryManager):
    """Render the category training interface"""
    
    st.markdown("### 🎯 Category Training")
    st.markdown("Train the system to automatically categorize merchants")
    
    # Get uncategorized merchants
    uncategorized = category_manager.get_uncategorized_merchants(limit=20)
    
    if not uncategorized:
        st.success("🎉 All merchants are categorized! Great job!")
        return
    
    st.markdown(f"**{len(uncategorized)} merchants** need categorization:")
    
    # Category selection options
    categories = category_manager.get_all_categories()
    category_options = []
    for category, subcategories in categories.items():
        for subcategory in subcategories:
            category_options.append(f"{category} → {subcategory}")
    
    # Training interface
    with st.form("merchant_training"):
        st.markdown("#### 📝 Categorize Merchants")
        
        # Show merchants in a more compact format
        for i, merchant_data in enumerate(uncategorized[:10]):  # Show top 10
            merchant = merchant_data['merchant']
            count = merchant_data['transaction_count']
            amount = merchant_data['total_amount']
            sample = merchant_data['description_sample']
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**{merchant}**")
                st.caption(f"Sample: {sample}")
                st.caption(f"{count} transactions • ${abs(amount):.2f} total")
            
            with col2:
                selected_category = st.selectbox(
                    "Category",
                    [""] + category_options,
                    key=f"category_{i}",
                    label_visibility="collapsed"
                )
                
                # Store the selection
                if selected_category:
                    st.session_state[f"merchant_{i}"] = {
                        'merchant': merchant,
                        'category_full': selected_category
                    }
            
            st.divider()
        
        # Submit button
        submitted = st.form_submit_button("💾 Save Categories", type="primary")
        
        if submitted:
            saved_count = 0
            
            # Process all selections
            for i in range(len(uncategorized[:10])):
                if f"merchant_{i}" in st.session_state:
                    merchant_data = st.session_state[f"merchant_{i}"]
                    if merchant_data.get('category_full'):
                        category_full = merchant_data['category_full']
                        merchant = merchant_data['merchant']
                        
                        # Parse category → subcategory
                        if " → " in category_full:
                            category, subcategory = category_full.split(" → ", 1)
                            
                            # Save the mapping
                            success = category_manager.learn_merchant_mapping(
                                merchant, category, subcategory
                            )
                            
                            if success:
                                saved_count += 1
                                # Clean up session state
                                del st.session_state[f"merchant_{i}"]
            
            if saved_count > 0:
                st.success(f"✅ Saved {saved_count} merchant categories!")
                st.rerun()
            else:
                st.warning("No categories were selected to save.")


def render_category_management(category_manager: CategoryManager):
    """Render category management interface"""
    
    # DEBUG: This should show if file is reloaded
    st.markdown("### ⚙️ Category Management [DEBUG: File loaded v2]")
    
    # Statistics
    stats = category_manager.get_categorization_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Transactions", stats.get('total_transactions', 0))
    
    with col2:
        categorized = stats.get('categorized_transactions', 0)
        st.metric("Categorized", categorized)
    
    with col3:
        rate = stats.get('categorization_rate', 0)
        st.metric("Success Rate", f"{rate:.1f}%")
    
    with col4:
        learned = stats.get('learned_mappings', 0)
        st.metric("Learned Rules", learned)
    
    # Auto-categorization section
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("#### 🚀 Auto-Categorization")
        uncategorized_count = stats.get('total_transactions', 0) - stats.get('categorized_transactions', 0)
        if uncategorized_count > 0:
            st.markdown(f"**{uncategorized_count} transactions** need categorization")
        else:
            st.success("✅ All transactions are categorized!")
    
    with col2:
        if st.button("🚀 Auto-Categorize All", type="primary", disabled=uncategorized_count == 0):
            with st.spinner("Running auto-categorization..."):
                # Get database from session state
                database = st.session_state.database
                categorized_count = database.auto_categorize_transactions()
                
                if categorized_count > 0:
                    st.success(f"✅ Auto-categorized {categorized_count} transactions!")
                    st.rerun()
                else:
                    st.info("No additional transactions could be categorized automatically.")
    
    st.markdown("---")
    
    # Tabs for different management functions
    tab1, tab2, tab3 = st.tabs(["🎯 Train", "📋 Learned Rules", "📊 Categories"])
    
    with tab1:
        render_category_training(category_manager)
    
    with tab2:
        render_learned_mappings(category_manager)
    
    with tab3:
        render_category_overview(category_manager)


def render_learned_mappings(category_manager: CategoryManager):
    """Show learned merchant mappings"""
    
    st.markdown("#### 📚 Learned Merchant Mappings")
    
    mappings = category_manager.get_learned_mappings()
    
    if not mappings:
        st.info("No learned mappings yet. Start training above!")
        return
    
    # Convert to DataFrame for better display
    df = pd.DataFrame(mappings)
    
    # Display as editable table
    st.markdown(f"**{len(mappings)} learned mappings:**")
    
    for mapping in mappings:
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.text(mapping['merchant_pattern'])
        
        with col2:
            st.text(f"{mapping['category']} → {mapping['subcategory']}")
        
        with col3:
            if st.button("🗑️", key=f"delete_{mapping['merchant_pattern']}", 
                        help="Delete this mapping"):
                if category_manager.delete_merchant_mapping(mapping['merchant_pattern']):
                    st.success(f"Deleted mapping for {mapping['merchant_pattern']}")
                    st.rerun()
                else:
                    st.error("Failed to delete mapping")


def render_category_overview(category_manager: CategoryManager):
    """Show category overview"""
    
    st.markdown("#### 📊 Fixed Categories")
    st.markdown("These categories are fixed and cannot be changed:")
    
    categories = category_manager.get_all_categories()
    
    for category, subcategories in categories.items():
        with st.expander(f"**{category}** ({len(subcategories)} subcategories)"):
            for subcategory in subcategories:
                st.markdown(f"• {subcategory}")


def render_quick_categorize(database, category_manager: CategoryManager):
    """Quick categorization interface in sidebar"""
    
    st.sidebar.markdown("### 🎯 Quick Categorize")
    
    # Get a few uncategorized merchants
    uncategorized = category_manager.get_uncategorized_merchants(limit=3)
    
    if uncategorized:
        st.sidebar.markdown(f"**{len(uncategorized)} merchants need attention:**")
        
        for merchant_data in uncategorized:
            merchant = merchant_data['merchant']
            count = merchant_data['transaction_count']
            
            with st.sidebar.expander(f"{merchant} ({count} txns)"):
                # Category selection
                categories = category_manager.get_all_categories()
                category_options = []
                for category, subcategories in categories.items():
                    for subcategory in subcategories:
                        category_options.append(f"{category} → {subcategory}")
                
                selected = st.selectbox(
                    "Assign category:",
                    [""] + category_options,
                    key=f"quick_{merchant}"
                )
                
                if st.button("Save", key=f"save_{merchant}"):
                    if selected and " → " in selected:
                        category, subcategory = selected.split(" → ", 1)
                        
                        success = category_manager.learn_merchant_mapping(
                            merchant, category, subcategory
                        )
                        
                        if success:
                            st.success("✅ Saved!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save")
    else:
        st.sidebar.success("✅ All merchants categorized!")
