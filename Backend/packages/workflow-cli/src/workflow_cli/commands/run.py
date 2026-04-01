"""
CLI Run commands
wf run trigger / status / cancel / logs
"""
import click
import httpx
import websockets
import asyncio
import json
import sys
from rich.console import Console
from workflow_cli.config import get_base_url, get_token

console = Console()

def _request(method, path, **kwargs):
    url = f"{get_base_url()}{path}"
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.request(method, url, headers=headers, **kwargs)

@click.group(name="run")
def run():
    """Manage Execution runs"""
    pass

@run.command()
@click.argument("workflow_id")
@click.option("--input-data", default="{}", help="JSON input data string")
def trigger(workflow_id, input_data):
    """Trigger a workflow. Exits 0 on QUEUED, 1 on error."""
    try:
        data = json.loads(input_data)
    except json.JSONDecodeError:
        console.print("[red]Invalid JSON input[/red]")
        sys.exit(1)
        
    res = _request("POST", f"/workflows/{workflow_id}/trigger", json=data)
    
    if res.is_success:
        run_data = res.json().get("data", {})
        console.print(f"[green]QUEUED run: [bold]{run_data.get('id')}[/bold][/green]")
        sys.exit(0)
    else:
        console.print(f"[red]Error triggering run: {res.text}[/red]")
        sys.exit(1)

@run.command()
@click.argument("run_id")
def status(run_id):
    """Get status of an execution run"""
    res = _request("GET", f"/executions/{run_id}")
    if res.is_success:
        console.print(res.json())
    else:
        console.print(f"[red]Failed: {res.text}[/red]")
        
@run.command()
@click.argument("run_id")
def cancel(run_id):
    """Cancel an execution run"""
    res = _request("POST", f"/executions/{run_id}/cancel")
    if res.is_success:
        console.print(f"[green]Started cancellation of {run_id}[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

async def stream_logs(run_id, token):
    # Convert active base HTTP URL to WS URL
    http_url = get_base_url()
    ws_url = http_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_endpoint = f"{ws_url}/ws/executions/{run_id}?token={token}"
    
    try:
        # Note: server enforces 200ms polling latency to streams NodeExecutionState
        async with websockets.connect(ws_endpoint) as wsock:
            while True:
                message = await wsock.recv()
                data = json.loads(message)
                # Stream logs cleanly
                if data.get("type") == "node_update":
                    node = data.get("node_id")
                    status = data.get("status")
                    console.print(f"[blue][{node}][/blue]: {status}")
                elif data.get("type") in ("terminal", "error"):
                    console.print(f"[yellow]Execution terminated: {data.get('status')}[/yellow]")
                    break
                else:
                    console.print(str(data))
    except websockets.exceptions.ConnectionClosed:
        console.print("[yellow]Websocket stream closed by server.[/yellow]")

@run.command()
@click.argument("run_id")
@click.option("--follow", is_flag=True, help="Stream logs via WebSocket to stdout")
def logs(run_id, follow):
    """Fetch or stream execution logs"""
    if follow:
        token = get_token()
        if not token:
            console.print("[red]Authentication required for WebSocket streaming[/red]")
            sys.exit(1)
        # AC: wf run logs <run_id> --follow streams logs to stdout
        try:
            asyncio.run(stream_logs(run_id, token))
        except Exception as e:
            console.print(f"[red]Stream connection failed: {e}[/red]")
    else:
        res = _request("GET", f"/executions/{run_id}/logs")
        if res.is_success:
            console.print(res.json())
        else:
            console.print(f"[red]Failed: {res.text}[/red]")
