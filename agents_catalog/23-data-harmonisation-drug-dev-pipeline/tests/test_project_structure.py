"""
Test project structure and basic functionality.
Validates that the core infrastructure is properly set up.
"""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import settings
from src import __version__


class TestProjectStructure:
    """Test basic project structure and configuration."""
    
    def test_version_defined(self):
        """Test that version is properly defined."""
        assert __version__ == "0.1.0"
    
    def test_settings_loading(self):
        """Test that settings can be loaded successfully."""
        assert settings is not None
        assert settings.environment in ["development", "testing", "staging", "production"]
    
    def test_database_settings(self):
        """Test database configuration."""
        db_settings = settings.database
        
        # Test PostgreSQL settings
        assert db_settings.postgres_host is not None
        assert db_settings.postgres_port > 0
        assert db_settings.postgres_db is not None
        assert db_settings.postgres_user is not None
        
        # Test MongoDB settings
        assert db_settings.mongodb_host is not None
        assert db_settings.mongodb_port > 0
        assert db_settings.mongodb_db is not None
        assert db_settings.mongodb_user is not None
    
    def test_web_scraping_settings(self):
        """Test web scraping configuration."""
        ws_settings = settings.web_scraping
        
        assert ws_settings.user_agent is not None
        assert ws_settings.request_delay_min >= 0
        assert ws_settings.request_delay_max > ws_settings.request_delay_min
        assert ws_settings.max_retries > 0
        assert ws_settings.timeout_seconds > 0
        assert len(ws_settings.target_urls) > 0
    
    def test_logging_settings(self):
        """Test logging configuration."""
        log_settings = settings.logging
        
        assert log_settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert log_settings.log_format in ["json", "text"]
    
    def test_directory_structure(self):
        """Test that required directories exist."""
        project_root = Path(__file__).parent.parent
        
        required_dirs = [
            "src",
            "src/agents",
            "src/agents/web_scraper",
            "src/agents/data_harmonizer", 
            "src/agents/quality_assurance",
            "src/storage",
            "src/models",
            "src/orchestration",
            "src/utils",
            "tests",
            "tests/unit",
            "tests/property",
            "tests/integration",
            "config",
            "scripts",
            "deployment"
        ]
        
        for dir_path in required_dirs:
            full_path = project_root / dir_path
            assert full_path.exists(), f"Required directory {dir_path} does not exist"
            assert full_path.is_dir(), f"Path {dir_path} is not a directory"
    
    def test_required_files(self):
        """Test that required files exist."""
        project_root = Path(__file__).parent.parent
        
        required_files = [
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "README.md",
            ".gitignore",
            ".env.example",
            "docker-compose.yml",
            "pytest.ini",
            "src/__init__.py",
            "src/cli.py",
            "config/settings.py",
            "scripts/init_databases.py"
        ]
        
        for file_path in required_files:
            full_path = project_root / file_path
            assert full_path.exists(), f"Required file {file_path} does not exist"
            assert full_path.is_file(), f"Path {file_path} is not a file"


class TestConfiguration:
    """Test configuration management functionality."""
    
    def test_postgres_url_generation(self):
        """Test PostgreSQL URL generation."""
        db_settings = settings.database
        url = db_settings.postgres_url
        
        assert url.startswith("postgresql://")
        assert db_settings.postgres_user in url
        assert db_settings.postgres_host in url
        assert str(db_settings.postgres_port) in url
        assert db_settings.postgres_db in url
    
    def test_mongodb_url_generation(self):
        """Test MongoDB URL generation."""
        db_settings = settings.database
        url = db_settings.mongodb_url
        
        assert url.startswith("mongodb://")
        assert db_settings.mongodb_user in url
        assert db_settings.mongodb_host in url
        assert str(db_settings.mongodb_port) in url
        assert db_settings.mongodb_db in url
    
    def test_environment_validation(self):
        """Test environment setting validation."""
        # This should not raise an exception
        assert settings.environment in ["development", "testing", "staging", "production"]
    
    def test_delay_range_validation(self):
        """Test that request delay range is valid."""
        ws_settings = settings.web_scraping
        assert ws_settings.request_delay_max > ws_settings.request_delay_min


@pytest.mark.integration
class TestProjectIntegration:
    """Integration tests for project setup."""
    
    def test_cli_import(self):
        """Test that CLI module can be imported."""
        from src.cli import cli
        assert cli is not None
    
    def test_database_initializer_import(self):
        """Test that database initializer can be imported."""
        from scripts.init_databases import DatabaseInitializer
        assert DatabaseInitializer is not None
    
    def test_settings_import_from_config(self):
        """Test that settings can be imported from config module."""
        from config.settings import settings as config_settings
        assert config_settings is not None
        assert config_settings.environment is not None