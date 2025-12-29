"""
Basic test to verify project structure without external dependencies.
"""

import sys
from pathlib import Path


def test_directory_structure():
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
    
    print("✓ All required directories exist")


def test_required_files():
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
    
    print("✓ All required files exist")


def test_version_import():
    """Test that version can be imported."""
    sys.path.append(str(Path(__file__).parent.parent))
    
    try:
        from src import __version__
        assert __version__ == "0.1.0"
        print("✓ Version import successful")
    except ImportError as e:
        print(f"✗ Version import failed: {e}")
        raise


if __name__ == "__main__":
    test_directory_structure()
    test_required_files()
    test_version_import()
    print("\n🎉 All basic structure tests passed!")