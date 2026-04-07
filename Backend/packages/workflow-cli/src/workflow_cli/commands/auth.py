"""
CLI Authentication commands
wf auth login / logout / whoami
"""
import click
import httpx
from rich.console import Console
from workflow_cli.config import set_profile, get_base_url, get_token

console = Console()

@click.group(name="auth")
def auth():
    """Authentication and session management"""
    pass

@auth.command()
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
def login(email, password):
    """Authenticate and store JWT token locally"""
    url = f"{get_base_url()}/api/v1/auth/login"
    try:
        res = httpx.post(url, json={"email": email, "password": password})
        if res.is_success:
            data = res.json().get("data", res.json())
            token = data.get("access_token")
            tenant_id = data.get("tenant_id")
            set_profile(token=token, tenant_id=tenant_id)
            console.print("[green]Successfully logged in![/green]")
        elif res.status_code == 401:
            console.print("[red]Login failed: Invalid credentials[/red]")
        elif res.status_code == 422:
            detail = res.json().get("detail", res.text)
            console.print(f"[red]Login failed: {detail}[/red]")
        else:
            console.print(f"[red]Login failed: {res.text}[/red]")
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")

@auth.command()
def logout():
    """Remove local JWT token"""
    set_profile(token=None, tenant_id=None)
    console.print("[yellow]Logged out successfully.[/yellow]")

@auth.command()
def whoami():
    """Print current user properties via API"""
    token = get_token()
    if not token:
        console.print("[red]Not logged in.[/red]")
        return

    url = f"{get_base_url()}/api/v1/users/me"
    try:
        res = httpx.get(url, headers={"Authorization": f"Bearer {token}"})
        if res.is_success:
            console.print(res.json().get("data", res.json()))
        else:
            console.print(f"[red]Failed to verify session: {res.text}[/red]")
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")
