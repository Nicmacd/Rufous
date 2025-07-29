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
    
    # Flinks API Configuration
    flinks_customer_id: str = Field(
        default_factory=lambda: os.getenv("FLINKS_CUSTOMER_ID", ""),
        description="Flinks Customer ID for API authentication"
    )
    
    flinks_api_url: str = Field(
        default_factory=lambda: os.getenv(
            "FLINKS_API_URL", 
            "https://toolbox-api.private.fin.ag/v3"  # Default to sandbox
        ),
        description="Flinks API base URL (sandbox or production)"
    )
    
    # Additional Flinks credentials
    flinks_bearer_token: str = Field(
        default_factory=lambda: os.getenv("FLINKS_BEARER_TOKEN", ""),
        description="Flinks Bearer token for authentication"
    )
    
    flinks_auth_key: str = Field(
        default_factory=lambda: os.getenv("FLINKS_AUTH_KEY", ""),
        description="Flinks auth key for GenerateAuthorizeToken"
    )
    
    flinks_x_api_key: str = Field(
        default_factory=lambda: os.getenv("FLINKS_X_API_KEY", ""),
        description="Flinks X-API-Key for aggregation endpoints"
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
        if not self.flinks_customer_id:
            raise ValueError("FLINKS_CUSTOMER_ID is required")
        
        if not self.flinks_api_url:
            raise ValueError("FLINKS_API_URL is required")
        
        return True
    
    @property
    def is_sandbox(self) -> bool:
        """Check if we're using the sandbox environment"""
        return "toolbox-api" in self.flinks_api_url or "sandbox" in self.flinks_api_url
    
    @property
    def is_production(self) -> bool:
        """Check if we're using the production environment"""
        return not self.is_sandbox
    
    def get_flinks_config(self) -> dict:
        """Get configuration dict for Flinks client"""
        return {
            "customer_id": self.flinks_customer_id,
            "api_endpoint": self.flinks_api_url,
            "bearer_token": self.flinks_bearer_token,
            "auth_key": self.flinks_auth_key,
            "x_api_key": self.flinks_x_api_key,
            "debug": self.log_level == "DEBUG",
        } 