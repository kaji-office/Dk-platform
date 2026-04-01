"""
CLI Workflow Management commands
wf workflow list / get / create / update / delete / activate / deactivate
"""
import click
import httpx
from rich.console import Console
from rich.table import Table
from workflow_cli.config import get_base_url, get_token

console = Console()

def _request(method, path, **kwargs):
    url = f"{get_base_url()}{path}"
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.request(method, url, headers=headers, **kwargs)

@click.group(name="workflow")
def workflow():
    """Manage Workflow definitions"""
    pass

@workflow.command()
def list():
    """List all workflow definitions in tenant"""
    res = _request("GET", "/workflows/")
    if res.is_success:
        data = res.json().get("data", [])
        table = Table(title="Workflows")
        table.add_column("ID", justify="left")
        table.add_column("Name", justify="left")
        table.add_column("Version", justify="right")
        table.add_column("Active", justify="center")
        
        for wf in data:
            table.add_row(wf["id"], wf["name"], str(wf.get("version", 1)), str(wf.get("is_active", False)))
        console.print(table)
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def get(workflow_id):
    res = _request("GET", f"/workflows/{workflow_id}")
    if res.is_success:
        console.print(res.json())
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("name")
def create(name):
    """Create a new empty workflow"""
    payload = {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "nodes": {},
        "edges": []
    }
    res = _request("POST", "/workflows/", json=payload)
    if res.is_success:
        console.print(f"[green]Workflow {name} created.[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
@click.argument("file", type=click.File("rb"))
def update(workflow_id, file):
    """Update workflow from JSON file definition"""
    import json
    data = json.load(file)
    res = _request("PUT", f"/workflows/{workflow_id}", json=data)
    if res.is_success:
        console.print("[green]Workflow updated successfully.[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def delete(workflow_id):
    res = _request("DELETE", f"/workflows/{workflow_id}")
    if res.is_success:
        console.print(f"[yellow]Deleted {workflow_id}[/yellow]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def activate(workflow_id):
    res = _request("POST", f"/workflows/{workflow_id}/activate")
    if res.is_success:
        console.print(f"[green]Activated {workflow_id}[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def deactivate(workflow_id):
    res = _request("DELETE", f"/workflows/{workflow_id}/activate")
    if res.is_success:
        console.print(f"[yellow]Deactivated {workflow_id}[/yellow]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")
