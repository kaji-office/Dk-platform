"""
Main CLI Group definition handling initialization of commands.
"""
import click
from rich.console import Console
from .commands import auth, workflow, run, schedule, config

console = Console()

@click.group()
@click.option("--api-url", envvar="WF_API_URL", default=None, help="Override the API base URL for this invocation.")
@click.pass_context
def cli(ctx: click.Context, api_url: str | None):
    """DK Workflow CLI — The thin command line interface to interact with your pipelines."""
    ctx.ensure_object(dict)
    if api_url:
        # Runtime override — does not persist to config file
        import workflow_cli.config as _cfg
        _cfg._RUNTIME_API_URL = api_url

cli.add_command(auth.auth)
cli.add_command(workflow.workflow)
cli.add_command(run.run)
cli.add_command(schedule.schedule)
cli.add_command(config.config_group)

if __name__ == "__main__":
    cli()
