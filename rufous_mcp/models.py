"""
Data models for Rufous MCP Server
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Transaction data model"""
    id: str
    amount: float
    date: datetime
    description: str
    category: Optional[str] = None
    account_id: Optional[str] = None
    account_type: Optional[str] = None
    account_name: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class Account(BaseModel):
    """Account data model"""
    id: str
    name: str
    type: str
    balance: Optional[float] = None
    currency: Optional[str] = "CAD"
    institution: Optional[str] = None
    last_updated: Optional[datetime] = None


class CategorySummary(BaseModel):
    """Category spending summary"""
    category: str
    amount: float
    transaction_count: int
    percentage_of_total: float


class FinancialSummary(BaseModel):
    """Financial health summary"""
    total_spent: float
    total_income: float
    net_change: float
    categories: List[CategorySummary]
    period_days: int
    last_updated: datetime
    account_count: int
    transaction_count: int


class SpendingComparison(BaseModel):
    """Comparison between spending periods"""
    current_period: Dict[str, Any]
    previous_period: Dict[str, Any]
    change_amount: float
    change_percentage: float
    trend: str  # 'increased', 'decreased', 'unchanged'
    category_changes: Dict[str, Dict[str, float]] 