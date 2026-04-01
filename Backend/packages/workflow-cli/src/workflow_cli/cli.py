"""
Main CLI Group definition handling initialization of commands.
"""
import click
from rich.console import Console
from .commands import auth, workflow, run, schedule, config

console = Console()

@click.group()
def cli():
    """DK Workflow CLI — The thin command line interface to interact with your pipelines."""
    pass

cli.add_command(auth.auth)
cli.add_command(workflow.workflow)
cli.add_command(run.run)
cli.add_command(schedule.schedule)
cli.add_command(config.config_group)

if __name__ == "__main__":
    cli()
