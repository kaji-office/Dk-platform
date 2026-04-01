"""
CLI commands
wf config set / get
"""
import click
from rich.console import Console
from workflow_cli.config import set_profile, get_profile

console = Console()

@click.group(name="config")
def config_group():
    """Environment config management"""
    pass

@config_group.command()
@click.argument("key")
@click.argument("value")
def set(key, value):
    """Set config key value dynamically"""
    kwargs = {key: value}
    set_profile(**kwargs)
    console.print(f"[green]Set {key} = {value}[/green]")

@config_group.command()
@click.argument("key", required=False)
def get(key):
    """Get active config"""
    cfg = get_profile()
    if key:
        val = cfg.get(key)
        console.print(f"{key} = {val}")
    else:
        for k, v in cfg.items():
            if k == "token":
                console.print("token = *******")
            else:
                console.print(f"{k} = {v}")
