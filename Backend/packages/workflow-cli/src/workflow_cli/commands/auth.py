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
    url = f"{get_base_url()}/auth/token"
    try:
        res = httpx.post(url, data={"username": email, "password": password})
        if res.is_success:
            data = res.json()
            token = data.get("access_token")
            set_profile(token=token)
            console.print("[green]Successfully logged in![/green]")
        else:
            console.print(f"[red]Login failed: {res.text}[/red]")
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")

@auth.command()
def logout():
    """Remove local JWT token"""
    set_profile(token=None)
    console.print("[yellow]Logged out successfully.[/yellow]")

@auth.command()
def whoami():
    """Print current user properties via API"""
    token = get_token()
    if not token:
        console.print("[red]Not logged in.[/red]")
        return
        
    url = f"{get_base_url()}/users/me"
    try:
        res = httpx.get(url, headers={"Authorization": f"Bearer {token}"})
        if res.is_success:
            console.print(res.json())
        else:
            console.print(f"[red]Failed to verify session: {res.text}[/red]")
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")
