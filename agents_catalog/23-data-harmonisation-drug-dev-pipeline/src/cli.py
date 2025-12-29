"""
Command Line Interface for the Agentic Pharmaceutical Pipeline.
Provides commands for database initialization, agent management, and system operations.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from loguru import logger
from rich.console import Console
from rich.table import Table

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import settings
from scripts.init_databases import DatabaseInitializer

console = Console()


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
def cli(verbose: bool, config: Optional[str]):
    """Agentic Pharmaceutical Pipeline CLI."""
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    
    if config:
        # Load custom configuration if provided
        pass  # TODO: Implement custom config loading


@cli.group()
def db():
    """Database management commands."""
    pass


@db.command()
def init():
    """Initialize PostgreSQL and MongoDB databases."""
    console.print("[bold blue]Initializing databases...[/bold blue]")
    
    async def run_init():
        initializer = DatabaseInitializer()
        success = await initializer.initialize_all()
        return success
    
    success = asyncio.run(run_init())
    
    if success:
        console.print("[bold green]✓ Database initialization completed successfully![/bold green]")
    else:
        console.print("[bold red]✗ Database initialization failed![/bold red]")
        sys.exit(1)


@db.command()
def test():
    """Test database connections."""
    console.print("[bold blue]Testing database connections...[/bold blue]")
    
    async def run_test():
        initializer = DatabaseInitializer()
        success = await initializer.test_connections()
        return success
    
    success = asyncio.run(run_test())
    
    if success:
        console.print("[bold green]✓ All database connections successful![/bold green]")
    else:
        console.print("[bold red]✗ Database connection test failed![/bold red]")
        sys.exit(1)


@db.command()
def status():
    """Show database status and configuration."""
    table = Table(title="Database Configuration")
    table.add_column("Database", style="cyan")
    table.add_column("Host", style="magenta")
    table.add_column("Port", style="green")
    table.add_column("Database Name", style="yellow")
    table.add_column("User", style="blue")
    
    table.add_row(
        "PostgreSQL",
        settings.database.postgres_host,
        str(settings.database.postgres_port),
        settings.database.postgres_db,
        settings.database.postgres_user
    )
    
    table.add_row(
        "MongoDB",
        settings.database.mongodb_host,
        str(settings.database.mongodb_port),
        settings.database.mongodb_db,
        settings.database.mongodb_user
    )
    
    console.print(table)


@cli.group()
def agents():
    """Agent management commands."""
    pass


@agents.command()
def list():
    """List available agents."""
    table = Table(title="Available Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Status", style="green")
    
    table.add_row("Web Scraper", "Collects data from pharmaceutical websites", "Not Implemented")
    table.add_row("Data Harmonizer", "Harmonizes and standardizes collected data", "Not Implemented")
    table.add_row("Quality Assurance", "Performs data quality assessments", "Not Implemented")
    
    console.print(table)


@agents.command()
@click.argument('agent_name')
def start(agent_name: str):
    """Start a specific agent."""
    console.print(f"[bold blue]Starting {agent_name} agent...[/bold blue]")
    console.print(f"[bold yellow]Agent {agent_name} is not yet implemented[/bold yellow]")


@agents.command()
@click.argument('agent_name')
def stop(agent_name: str):
    """Stop a specific agent."""
    console.print(f"[bold blue]Stopping {agent_name} agent...[/bold blue]")
    console.print(f"[bold yellow]Agent {agent_name} is not yet implemented[/bold yellow]")


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
def show():
    """Show current configuration."""
    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Environment", settings.environment)
    table.add_row("Debug Mode", str(settings.debug))
    table.add_row("Log Level", settings.logging.log_level)
    table.add_row("Log Format", settings.logging.log_format)
    
    console.print(table)


@config.command()
def validate():
    """Validate configuration settings."""
    console.print("[bold blue]Validating configuration...[/bold blue]")
    
    try:
        # Test configuration loading
        test_settings = settings
        console.print("[bold green]✓ Configuration is valid![/bold green]")
        
        # Show any warnings
        if not test_settings.aws.agentcore_endpoint:
            console.print("[bold yellow]⚠ AgentCore endpoint not configured[/bold yellow]")
        
        if not test_settings.observability.langfuse_public_key:
            console.print("[bold yellow]⚠ Langfuse observability not configured[/bold yellow]")
            
    except Exception as e:
        console.print(f"[bold red]✗ Configuration validation failed: {e}[/bold red]")
        sys.exit(1)


@cli.command()
def version():
    """Show version information."""
    from src import __version__
    console.print(f"[bold blue]Agentic Pharmaceutical Pipeline v{__version__}[/bold blue]")


@cli.command()
def dev():
    """Start development environment."""
    console.print("[bold blue]Starting development environment...[/bold blue]")
    console.print("[bold yellow]Use 'docker-compose up -d' to start infrastructure services[/bold yellow]")
    console.print("[bold yellow]Then run 'pharma-pipeline db init' to initialize databases[/bold yellow]")


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()