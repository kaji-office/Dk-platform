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

def _unwrap(res):
    body = res.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body

@click.group(name="schedule")
def schedule():
    """Manage cron triggered execution schedules"""
    pass

@schedule.command()
@click.argument("workflow_id")
def list(workflow_id):
    """List schedules for a given workflow"""
    res = _request("GET", f"/api/v1/workflows/{workflow_id}/schedules")
    if res.is_success:
        data = _unwrap(res)
        schedules = data.get("schedules", []) if isinstance(data, dict) else data
        if not schedules:
            console.print("[yellow]No schedules found.[/yellow]")
        else:
            for s in schedules:
                console.print(s)
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@schedule.command()
@click.argument("workflow_id")
@click.option("--cron", prompt=True, help="Cron expression e.g. '0 12 * * *'")
@click.option("--timezone", default="UTC", help="Timezone (default: UTC)")
@click.option("--input-data", default="{}", help="JSON input data string")
def create(workflow_id, cron, timezone, input_data):
    """Create a new schedule for a workflow"""
    import json
    try:
        parsed_input = json.loads(input_data)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON for --input-data[/red]")
        return
    data = {
        "cron_expression": cron,
        "timezone": timezone,
        "input_data": parsed_input,
    }
    res = _request("POST", f"/api/v1/workflows/{workflow_id}/schedules", json=data)
    if res.is_success:
        result = _unwrap(res)
        schedule_id = result.get("schedule_id", "")
        console.print(f"[green]Created schedule: {schedule_id}[/green]")
    else:
        console.print(f"[red]Failed to create: {res.text}[/red]")

@schedule.command()
@click.argument("schedule_id")
def delete(schedule_id):
    """Delete a schedule by ID"""
    res = _request("DELETE", f"/api/v1/schedules/{schedule_id}")
    if res.is_success:
        console.print("[green]Deleted.[/green]")
    elif res.status_code == 404:
        console.print(f"[red]Schedule {schedule_id} not found.[/red]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")
