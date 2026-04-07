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

def _unwrap(res):
    """Unwrap the {success, data} envelope if present."""
    body = res.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body

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

    res = _request("POST", f"/api/v1/workflows/{workflow_id}/trigger", json={"input_data": data})

    if res.is_success:
        run_data = _unwrap(res)
        run_id = run_data.get("run_id") or run_data.get("id")
        console.print(f"[green]QUEUED run: [bold]{run_id}[/bold][/green]")
        sys.exit(0)
    else:
        console.print(f"[red]Error triggering run: {res.text}[/red]")
        sys.exit(1)

@run.command()
@click.argument("run_id")
def status(run_id):
    """Get status of an execution run"""
    res = _request("GET", f"/api/v1/executions/{run_id}")
    if res.is_success:
        console.print(_unwrap(res))
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

@run.command()
@click.argument("run_id")
def cancel(run_id):
    """Cancel an execution run"""
    res = _request("POST", f"/api/v1/executions/{run_id}/cancel")
    if res.is_success:
        console.print(f"[green]Started cancellation of {run_id}[/green]")
    else:
        console.print(f"[red]Failed: {res.text}[/red]")

async def stream_logs(run_id, token, max_reconnects=3):
    http_url = get_base_url()
    ws_url = http_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_endpoint = f"{ws_url}/api/v1/ws/executions/{run_id}?token={token}"

    for attempt in range(max_reconnects):
        try:
            async with websockets.connect(ws_endpoint) as wsock:
                while True:
                    message = await wsock.recv()
                    data = json.loads(message)
                    msg_type = data.get("type")
                    if msg_type in ("node_state", "node_update"):
                        node = data.get("node_id")
                        node_status = data.get("status")
                        console.print(f"[blue][{node}][/blue]: {node_status}")
                    elif msg_type in ("run_complete", "terminal"):
                        run_status = data.get("status")
                        console.print(f"[yellow]Execution terminated: {run_status}[/yellow]")
                        return
                    elif msg_type == "error":
                        console.print(f"[red]Error: {data.get('detail')}[/red]")
                        return
                    else:
                        console.print(str(data))
        except websockets.exceptions.ConnectionClosed as exc:
            if attempt < max_reconnects - 1:
                wait = 2 ** attempt
                console.print(f"[yellow]Stream disconnected (attempt {attempt + 1}/{max_reconnects}), retrying in {wait}s...[/yellow]")
                await asyncio.sleep(wait)
            else:
                console.print("[yellow]Stream closed — max reconnects reached.[/yellow]")

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
        try:
            asyncio.run(stream_logs(run_id, token))
        except Exception as e:
            console.print(f"[red]Stream connection failed: {e}[/red]")
    else:
        res = _request("GET", f"/api/v1/executions/{run_id}/logs")
        if res.is_success:
            console.print(_unwrap(res))
        else:
            console.print(f"[red]Failed: {res.text}[/red]")
