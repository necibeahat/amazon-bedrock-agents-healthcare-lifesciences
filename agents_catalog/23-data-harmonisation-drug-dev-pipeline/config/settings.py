"""
Configuration management for the Agentic Pharmaceutical Pipeline.
Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    # PostgreSQL settings
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_db: str = Field(default="pharma_pipeline", env="POSTGRES_DB")
    postgres_user: str = Field(default="pharma_user", env="POSTGRES_USER")
    postgres_password: str = Field(env="POSTGRES_PASSWORD")
    
    # MongoDB settings
    mongodb_host: str = Field(default="localhost", env="MONGODB_HOST")
    mongodb_port: int = Field(default=27017, env="MONGODB_PORT")
    mongodb_db: str = Field(default="pharma_pipeline", env="MONGODB_DB")
    mongodb_user: str = Field(default="pharma_user", env="MONGODB_USER")
    mongodb_password: str = Field(env="MONGODB_PASSWORD")
    
    @property
    def postgres_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def mongodb_url(self) -> str:
        """Generate MongoDB connection URL."""
        return (
            f"mongodb://{self.mongodb_user}:{self.mongodb_password}"
            f"@{self.mongodb_host}:{self.mongodb_port}/{self.mongodb_db}"
        )


class WebScrapingSettings(BaseSettings):
    """Web scraping configuration settings."""
    
    user_agent: str = Field(
        default="AgenticPharmaPipeline/1.0 (+https://example.com/contact)",
        env="USER_AGENT"
    )
    request_delay_min: float = Field(default=1.0, env="REQUEST_DELAY_MIN")
    request_delay_max: float = Field(default=3.0, env="REQUEST_DELAY_MAX")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    timeout_seconds: int = Field(default=30, env="TIMEOUT_SECONDS")
    
    # Target pharmaceutical company URLs
    target_urls: List[str] = Field(default=[
        "https://www.merck.com/research/product-pipeline/",
        "https://www.novonordisk.com/science-and-technology/r-d-pipeline.html",
        "https://www.novartis.com/research-development/novartis-pipeline"
    ])
    
    @validator("request_delay_max")
    def validate_delay_range(cls, v, values):
        """Ensure max delay is greater than min delay."""
        if "request_delay_min" in values and v <= values["request_delay_min"]:
            raise ValueError("request_delay_max must be greater than request_delay_min")
        return v


class AWSSettings(BaseSettings):
    """AWS and AgentCore configuration settings."""
    
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    
    agentcore_endpoint: Optional[str] = Field(default=None, env="AGENTCORE_ENDPOINT")
    agentcore_api_key: Optional[str] = Field(default=None, env="AGENTCORE_API_KEY")


class ObservabilitySettings(BaseSettings):
    """Observability and monitoring configuration settings."""
    
    # Langfuse settings
    langfuse_public_key: Optional[str] = Field(default=None, env="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(default=None, env="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", env="LANGFUSE_HOST")
    
    # OpenTelemetry settings
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317", 
        env="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(
        default="agentic-pharma-pipeline", 
        env="OTEL_SERVICE_NAME"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is supported."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @validator("log_format")
    def validate_log_format(cls, v):
        """Validate log format is supported."""
        valid_formats = ["json", "text"]
        if v.lower() not in valid_formats:
            raise ValueError(f"log_format must be one of {valid_formats}")
        return v.lower()


class AppSettings(BaseSettings):
    """Main application configuration settings."""
    
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    web_scraping: WebScrapingSettings = Field(default_factory=WebScrapingSettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment is supported."""
        valid_envs = ["development", "testing", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return v.lower()


# Global settings instance
settings = AppSettings()