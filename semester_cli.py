#!/usr/bin/env python
"""Command-line interface for semester configuration management.

Usage:
    python semester_cli.py init config/semester_configs/2024_spring.yaml
    python semester_cli.py validate config/semester_configs/2024_spring.yaml
    python semester_cli.py list
    python semester_cli.py toggle-feature plugin.MarketEventsPlugin --enabled
    python semester_cli.py archive --output archives/
    python semester_cli.py reset config/semester_configs/2024_fall.yaml --archive
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional
import logging
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
import yaml

from core.config_loader import config_loader, ConfigValidationError
from core.semester_lifecycle import lifecycle_manager
from core.database import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich console for pretty output
console = Console()


def print_config_summary(config):
    """Print a summary of the semester configuration."""
    # Create summary table
    table = Table(title=f"Semester Configuration: {config.semester.code}")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    # Basic info
    table.add_row("Name", config.semester.name)
    table.add_row("Start Date", str(config.semester.start_date))
    table.add_row("End Date", str(config.semester.end_date))
    
    # Base configuration
    if config.base_configuration:
        table.add_row(
            "Base Config", 
            f"{config.base_configuration.name} v{config.base_configuration.version}"
        )
    
    # Plugin summary
    enabled_plugins = [
        name for name, cfg in config.plugins.items() if cfg.enabled
    ]
    table.add_row("Enabled Plugins", ", ".join(enabled_plugins) or "None")
    
    # Feature flags
    enabled_flags = [
        flag.name for flag in config.feature_flags if flag.enabled
    ]
    table.add_row("Feature Flags", f"{len(enabled_flags)} enabled")
    
    # Custom rules
    table.add_row(
        "Scheduled Events", 
        str(len(config.custom_rules.scheduled_events))
    )
    
    console.print(table)


async def cmd_init(args):
    """Initialize a semester from configuration file."""
    config_path = Path(args.config)
    
    if not config_path.exists():
        console.print(f"[red]Error: Configuration file not found: {config_path}[/red]")
        return 1
    
    try:
        # Load and validate configuration first
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Validating configuration...", total=None)
            config = config_loader.load_config(config_path)
        
        print_config_summary(config)
        
        # Confirm initialization
        if not args.yes:
            confirm = console.input(
                f"\n[yellow]Initialize semester {config.semester.code}? [y/N]:[/yellow] "
            )
            if confirm.lower() != 'y':
                console.print("[red]Initialization cancelled[/red]")
                return 0
        
        # Initialize database
        await init_db()
        
        # Initialize semester
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Initializing semester...", total=None)
            
            async with get_session() as session:
                semester = await lifecycle_manager.initialize_from_config(
                    config_path, session
                )
        
        console.print(
            Panel(
                f"Successfully initialized semester [green]{semester.code}[/green]\n"
                f"ID: {semester.id}\n"
                f"Duration: {semester.start_date} to {semester.end_date}",
                title="✅ Semester Initialized",
                border_style="green"
            )
        )
        
        # Start config watching if requested
        if args.watch:
            console.print(
                f"\n[yellow]Watching {config_path} for changes "
                f"(press Ctrl+C to stop)...[/yellow]"
            )
            try:
                await lifecycle_manager.watch_config_changes(config_path)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped watching configuration[/yellow]")
        
        return 0
        
    except ConfigValidationError as e:
        console.print(f"[red]Configuration validation failed:[/red] {e}")
        return 1
    except Exception as e:
        console.print(f"[red]Error initializing semester:[/red] {e}")
        logger.exception("Failed to initialize semester")
        return 1


async def cmd_validate(args):
    """Validate a semester configuration file."""
    config_path = Path(args.config)
    
    if not config_path.exists():
        console.print(f"[red]Error: Configuration file not found: {config_path}[/red]")
        return 1
    
    try:
        config = config_loader.load_config(config_path)
        print_config_summary(config)
        
        console.print(
            Panel(
                "[green]✓[/green] Configuration is valid",
                title="Validation Result",
                border_style="green"
            )
        )
        
        # Show raw YAML if requested
        if args.show_yaml:
            with open(config_path, 'r') as f:
                yaml_content = f.read()
            
            syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
            console.print("\n[bold]Raw Configuration:[/bold]")
            console.print(syntax)
        
        return 0
        
    except ConfigValidationError as e:
        console.print(
            Panel(
                f"[red]✗[/red] Configuration validation failed:\n{e}",
                title="Validation Result",
                border_style="red"
            )
        )
        return 1


async def cmd_list(args):
    """List available semester configurations."""
    configs = config_loader.list_configs()
    
    if not configs:
        console.print("[yellow]No semester configurations found[/yellow]")
        return 0
    
    table = Table(title="Available Semester Configurations")
    table.add_column("Code", style="cyan")
    table.add_column("File", style="green")
    table.add_column("Status", style="yellow")
    
    # Check active semester
    active_semester = lifecycle_manager.get_active_semester()
    active_code = active_semester.code if active_semester else None
    
    for code, path in configs:
        status = "Active" if code == active_code else ""
        table.add_row(code, path.name, status)
    
    console.print(table)
    return 0


async def cmd_toggle_feature(args):
    """Toggle a feature flag for the active semester."""
    if not lifecycle_manager.get_active_semester():
        console.print("[red]Error: No active semester[/red]")
        return 1
    
    try:
        async with get_session() as session:
            await lifecycle_manager.update_feature_toggle(
                args.flag_name,
                args.enabled,
                session
            )
        
        status = "enabled" if args.enabled else "disabled"
        console.print(
            f"[green]Successfully {status} feature:[/green] {args.flag_name}"
        )
        return 0
        
    except Exception as e:
        console.print(f"[red]Error toggling feature:[/red] {e}")
        return 1


async def cmd_reload(args):
    """Reload configuration for active semester."""
    if not lifecycle_manager.get_active_semester():
        console.print("[red]Error: No active semester[/red]")
        return 1
    
    active_config = lifecycle_manager.get_active_config()
    if not active_config or not active_config.development.debug_mode:
        console.print(
            "[red]Error: Configuration reload only available in development mode[/red]"
        )
        return 1
    
    # Find config file for active semester
    semester_code = lifecycle_manager.get_active_semester().code
    configs = config_loader.list_configs()
    
    config_path = None
    for code, path in configs:
        if code == semester_code:
            config_path = path
            break
    
    if not config_path:
        console.print(f"[red]Error: No configuration file found for {semester_code}[/red]")
        return 1
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Reloading configuration...", total=None)
            
            async with get_session() as session:
                await lifecycle_manager.reload_configuration(config_path, session)
        
        console.print("[green]Configuration reloaded successfully[/green]")
        return 0
        
    except Exception as e:
        console.print(f"[red]Error reloading configuration:[/red] {e}")
        return 1


async def cmd_archive(args):
    """Archive the active semester."""
    if not lifecycle_manager.get_active_semester():
        console.print("[red]Error: No active semester[/red]")
        return 1
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task("Archiving semester data...", total=None)
            
            async with get_session() as session:
                archive_path = await lifecycle_manager.archive_semester(
                    output_dir, session
                )
        
        console.print(
            Panel(
                f"Semester archived to:\n[green]{archive_path}[/green]",
                title="✅ Archive Complete",
                border_style="green"
            )
        )
        return 0
        
    except Exception as e:
        console.print(f"[red]Error archiving semester:[/red] {e}")
        return 1


async def cmd_reset(args):
    """Reset and prepare for a new semester."""
    new_config_path = Path(args.config)
    
    if not new_config_path.exists():
        console.print(
            f"[red]Error: Configuration file not found: {new_config_path}[/red]"
        )
        return 1
    
    # Validate new configuration
    try:
        new_config = config_loader.load_config(new_config_path)
    except ConfigValidationError as e:
        console.print(f"[red]Configuration validation failed:[/red] {e}")
        return 1
    
    # Show current and new semester info
    current_semester = lifecycle_manager.get_active_semester()
    if current_semester:
        console.print(f"Current semester: [yellow]{current_semester.code}[/yellow]")
    console.print(f"New semester: [green]{new_config.semester.code}[/green]")
    
    # Confirm reset
    if not args.yes:
        confirm = console.input(
            "\n[yellow]This will reset the system for a new semester. Continue? [y/N]:[/yellow] "
        )
        if confirm.lower() != 'y':
            console.print("[red]Reset cancelled[/red]")
            return 0
    
    try:
        async with get_session() as session:
            semester = await lifecycle_manager.reset_for_new_semester(
                new_config_path,
                archive=args.archive,
                session=session
            )
        
        console.print(
            Panel(
                f"System reset for new semester:\n"
                f"[green]{semester.code}[/green]\n"
                f"ID: {semester.id}",
                title="✅ Reset Complete",
                border_style="green"
            )
        )
        return 0
        
    except Exception as e:
        console.print(f"[red]Error resetting semester:[/red] {e}")
        return 1


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Semester configuration management for Insurance Manager"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize semester from config')
    init_parser.add_argument('config', help='Path to configuration YAML file')
    init_parser.add_argument(
        '--watch', '-w', 
        action='store_true',
        help='Watch configuration file for changes (dev mode)'
    )
    init_parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration file')
    validate_parser.add_argument('config', help='Path to configuration YAML file')
    validate_parser.add_argument(
        '--show-yaml',
        action='store_true',
        help='Show raw YAML content'
    )
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available configurations')
    
    # Toggle feature command
    toggle_parser = subparsers.add_parser(
        'toggle-feature',
        help='Toggle a feature flag'
    )
    toggle_parser.add_argument('flag_name', help='Name of the feature flag')
    toggle_parser.add_argument(
        '--enabled',
        action='store_true',
        help='Enable the feature (default: disable)'
    )
    
    # Reload command
    reload_parser = subparsers.add_parser(
        'reload',
        help='Reload configuration (dev mode only)'
    )
    
    # Archive command
    archive_parser = subparsers.add_parser('archive', help='Archive active semester')
    archive_parser.add_argument(
        '--output', '-o',
        default='archives',
        help='Output directory for archive (default: archives)'
    )
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset for new semester')
    reset_parser.add_argument('config', help='Configuration for new semester')
    reset_parser.add_argument(
        '--archive',
        action='store_true',
        help='Archive current semester before reset'
    )
    reset_parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Map commands to async functions
    commands = {
        'init': cmd_init,
        'validate': cmd_validate,
        'list': cmd_list,
        'toggle-feature': cmd_toggle_feature,
        'reload': cmd_reload,
        'archive': cmd_archive,
        'reset': cmd_reset
    }
    
    # Run the command
    try:
        return asyncio.run(commands[args.command](args))
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled[/yellow]")
        return 0
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        logger.exception("Command failed")
        return 1


if __name__ == '__main__':
    sys.exit(main()) 