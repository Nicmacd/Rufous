"""
Configuration management for Rufous MCP Server
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


class Config(BaseModel):
    """Configuration for Rufous MCP Server"""
    
    # PDF Processing Configuration
    database_path: str = Field(
        default_factory=lambda: os.getenv("RUFOUS_DATABASE_PATH", ""),
        description="Path to SQLite database file (defaults to ~/rufous_data.db if empty)"
    )
    
    statements_directory: str = Field(
        default_factory=lambda: os.getenv("RUFOUS_STATEMENTS_DIRECTORY", "./statements"),
        description="Directory to store uploaded statement files"
    )
    
    auto_categorize_transactions: bool = Field(
        default_factory=lambda: os.getenv("RUFOUS_AUTO_CATEGORIZE", "true").lower() == "true",
        description="Automatically categorize transactions using Claude"
    )
    
    pdf_processing_enabled: bool = Field(
        default_factory=lambda: os.getenv("RUFOUS_PDF_PROCESSING", "true").lower() == "true",
        description="Enable PDF statement processing"
    )
    
    # Data storage strategy
    use_persistent_storage: bool = Field(
        default_factory=lambda: os.getenv("USE_PERSISTENT_STORAGE", "false").lower() == "true",
        description="Whether to use persistent storage or session-based caching"
    )
    
    # Session configuration (for non-persistent mode)
    session_timeout_minutes: int = Field(
        default_factory=lambda: int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
        description="Session timeout in minutes for cached data"
    )
    
    # Logging configuration
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    # Security settings
    max_transaction_days: int = Field(
        default_factory=lambda: int(os.getenv("MAX_TRANSACTION_DAYS", "365")),
        description="Maximum number of days of transactions to fetch"
    )
    
    # Rate limiting
    api_rate_limit_per_minute: int = Field(
        default_factory=lambda: int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60")),
        description="Maximum API calls per minute"
    )
    
    def validate_config(self) -> bool:
        """Validate the configuration"""
        # Basic validation - ensure statements directory exists or can be created
        if self.statements_directory:
            os.makedirs(self.statements_directory, exist_ok=True)
        
        return True
    
    def get_pdf_config(self) -> dict:
        """Get configuration dict for PDF processing"""
        return {
            "database_path": self.database_path or None,  # None triggers default path
            "statements_directory": self.statements_directory,
            "auto_categorize": self.auto_categorize_transactions,
            "processing_enabled": self.pdf_processing_enabled,
            "debug": self.log_level == "DEBUG",
        }