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

def _unwrap(res):
    """Unwrap the {success, data} envelope if present."""
    body = res.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body

@click.group(name="workflow")
def workflow():
    """Manage Workflow definitions"""
    pass

@workflow.command()
def list():
    """List all workflow definitions in tenant"""
    res = _request("GET", "/api/v1/workflows")
    if res.is_success:
        data = _unwrap(res)
        workflows = data.get("workflows", []) if isinstance(data, dict) else data
        table = Table(title="Workflows")
        table.add_column("ID", justify="left")
        table.add_column("Name", justify="left")
        table.add_column("Active", justify="center")
        for wf in workflows:
            table.add_row(wf.get("id", ""), wf.get("name", ""), str(wf.get("is_active", False)))
        console.print(table)
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def get(workflow_id):
    """Get a workflow definition by ID"""
    res = _request("GET", f"/api/v1/workflows/{workflow_id}")
    if res.is_success:
        console.print(_unwrap(res))
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.option("--name", required=True, help="Workflow name")
def create(name):
    """Create a new empty workflow"""
    payload = {"name": name, "definition": {"nodes": {}, "edges": []}}
    res = _request("POST", "/api/v1/workflows", json=payload)
    if res.is_success:
        data = _unwrap(res)
        wf_id = data.get("id", "")
        console.print(f"[green]Workflow '{name}' created with id: {wf_id}[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
@click.option("--name", default=None, help="New workflow name")
@click.option("--file", "file_path", default=None, type=click.Path(exists=True), help="JSON file with workflow definition")
def update(workflow_id, name, file_path):
    """Update workflow (by name, or from JSON file definition)"""
    import json
    if file_path:
        with open(file_path, "rb") as f:
            data = json.load(f)
    else:
        data = {}
    if name:
        data["name"] = name
    if not data:
        console.print("[red]Provide --name or --file to update.[/red]")
        return
    res = _request("PATCH", f"/api/v1/workflows/{workflow_id}", json=data)
    if res.is_success:
        console.print("[green]Workflow updated successfully.[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def delete(workflow_id):
    """Delete a workflow"""
    res = _request("DELETE", f"/api/v1/workflows/{workflow_id}")
    if res.is_success:
        console.print(f"[yellow]Deleted {workflow_id}[/yellow]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def activate(workflow_id):
    """Activate a workflow (enable execution)"""
    res = _request("POST", f"/api/v1/workflows/{workflow_id}/activate")
    if res.is_success:
        console.print(f"[green]Activated {workflow_id}[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@workflow.command()
@click.argument("workflow_id")
def deactivate(workflow_id):
    """Deactivate a workflow (disable execution)"""
    res = _request("POST", f"/api/v1/workflows/{workflow_id}/deactivate")
    if res.is_success:
        console.print(f"[yellow]Deactivated {workflow_id}[/yellow]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")
