"""
CLI Schedule commands
wf schedule list / create / delete
"""
import click
import httpx
from rich.console import Console
from workflow_cli.config import get_base_url, get_token

console = Console()

def _request(method, path, **kwargs):
    url = f"{get_base_url()}{path}"
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.request(method, url, headers=headers, **kwargs)

@click.group(name="schedule")
def schedule():
    """Manage cron triggered execution schedules"""
    pass

@schedule.command()
@click.argument("workflow_id")
def list(workflow_id):
    """List schedules for a given workflow"""
    res = _request("GET", f"/schedules/?workflow_id={workflow_id}")
    if res.is_success:
        console.print(res.json())
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@schedule.command()
@click.argument("workflow_id")
@click.option("--cron", prompt=True, help="Cron expression e.g. '0 12 * * *'")
@click.option("--input-data", default="{}", help="JSON input data string")
def create(workflow_id, cron, input_data):
    """Create a new schedule"""
    import json
    data = {
        "workflow_id": workflow_id,
        "cron_expression": cron,
        "input_data": json.loads(input_data),
        "enabled": True
    }
    res = _request("POST", "/schedules/", json=data)
    if res.is_success:
        console.print("[green]Created schedule![/green]")
    else:
        console.print(f"[red]Failed to create: {res.text}[/red]")

@schedule.command()
@click.argument("schedule_id")
def delete(schedule_id):
    """Delete schedule"""
    res = _request("DELETE", f"/schedules/{schedule_id}")
    if res.is_success:
        console.print("[green]Deleted.[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")
