#!/usr/bin/env python3
"""
GPTInfernse Client Example

This script demonstrates how to interact with the GPTInfernse API.
It provides examples for both synchronous and asynchronous chat requests.
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any

import aiohttp
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel

console = Console()


class GPTInfernseClient:
    """Client for GPTInfernse API."""
    
    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.init_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def init_session(self):
        """Initialize aiohttp session."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=300)
        )
        
    async def close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            
    async def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        async with self.session.get(f"{self.base_url}/health/detailed") as response:
            return await response.json()
            
    async def list_models(self) -> Dict[str, Any]:
        """List available models."""
        async with self.session.get(f"{self.base_url}/models/") as response:
            return await response.json()
            
    async def chat_sync(
        self,
        prompt: str,
        model: str = "llama3",
        **kwargs
    ) -> Dict[str, Any]:
        """Synchronous chat request."""
        payload = {
            "prompt": prompt,
            "model": model,
            **kwargs
        }
        
        async with self.session.post(f"{self.base_url}/chat/sync", json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"API Error {response.status}: {error_text}")
            return await response.json()
            
    async def chat_async(
        self,
        prompt: str,
        model: str = "llama3",
        **kwargs
    ) -> Dict[str, Any]:
        """Asynchronous chat request."""
        payload = {
            "prompt": prompt,
            "model": model,
            **kwargs
        }
        
        # Submit task
        async with self.session.post(f"{self.base_url}/chat/", json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"API Error {response.status}: {error_text}")
            task_info = await response.json()
            
        # Poll for result
        task_id = task_info["task_id"]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing...", total=None)
            
            while True:
                async with self.session.get(f"{self.base_url}/chat/task/{task_id}") as response:
                    status_info = await response.json()
                    
                if status_info["status"] == "completed":
                    progress.update(task, description="✅ Completed!")
                    return status_info["result"]
                elif status_info["status"] == "failed":
                    progress.update(task, description="❌ Failed!")
                    raise Exception(f"Task failed: {status_info.get('error', 'Unknown error')}")
                    
                await asyncio.sleep(1)
                
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status."""
        async with self.session.get(f"{self.base_url}/chat/task/{task_id}") as response:
            return await response.json()


@click.group()
@click.option("--url", default="http://localhost:8000", help="API base URL")
@click.option("--token", help="Authentication token")
@click.pass_context
def cli(ctx, url, token):
    """GPTInfernse CLI Client."""
    ctx.ensure_object(dict)
    ctx.obj["url"] = url
    ctx.obj["token"] = token


@cli.command()
@click.pass_context
async def health(ctx):
    """Check API health."""
    async with GPTInfernseClient(ctx.obj["url"], ctx.obj["token"]) as client:
        try:
            health_info = await client.health_check()
            
            # Display health status
            status = health_info.get("status", "unknown")
            color = "green" if status == "healthy" else "red" if status == "unhealthy" else "yellow"
            
            console.print(Panel(
                f"[{color}]Status: {status.upper()}[/{color}]\n"
                f"Service: {health_info.get('service', 'Unknown')}\n"
                f"Version: {health_info.get('version', 'Unknown')}\n"
                f"Timestamp: {health_info.get('timestamp', 'Unknown')}",
                title="🏥 Health Check"
            ))
            
            # Display component status
            if "components" in health_info:
                table = Table(title="Component Status")
                table.add_column("Component", style="cyan")
                table.add_column("Status", style="magenta")
                table.add_column("Details", style="green")
                
                for component, info in health_info["components"].items():
                    status = info.get("status", "unknown")
                    details = info.get("url", info.get("models_count", ""))
                    table.add_row(component, status, str(details))
                    
                console.print(table)
                
        except Exception as e:
            console.print(f"[red]❌ Health check failed: {e}[/red]")


@cli.command()
@click.pass_context
async def models(ctx):
    """List available models."""
    async with GPTInfernseClient(ctx.obj["url"], ctx.obj["token"]) as client:
        try:
            models_info = await client.list_models()
            
            table = Table(title="📚 Available Models")
            table.add_column("Name", style="cyan")
            table.add_column("Size", style="magenta")
            table.add_column("Modified", style="green")
            
            for model in models_info.get("models", []):
                table.add_row(
                    model.get("name", "Unknown"),
                    model.get("size", "Unknown"),
                    model.get("modified_at", "Unknown")[:19]  # Truncate timestamp
                )
                
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]❌ Failed to list models: {e}[/red]")


@cli.command()
@click.argument("prompt")
@click.option("--model", default="llama3", help="Model to use")
@click.option("--sync", is_flag=True, help="Use synchronous processing")
@click.option("--temperature", type=float, default=0.7, help="Sampling temperature")
@click.option("--max-tokens", type=int, default=1000, help="Maximum tokens")
@click.pass_context
async def chat(ctx, prompt, model, sync, temperature, max_tokens):
    """Send a chat message."""
    async with GPTInfernseClient(ctx.obj["url"], ctx.obj["token"]) as client:
        try:
            console.print(f"[cyan]🤖 Sending to {model}...[/cyan]")
            console.print(f"[dim]Prompt: {prompt}[/dim]\n")
            
            start_time = time.time()
            
            if sync:
                result = await client.chat_sync(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                result = await client.chat_async(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            end_time = time.time()
            
            # Display result
            console.print(Panel(
                result.get("response", "No response"),
                title=f"💬 Response from {result.get('model', model)}",
                border_style="green"
            ))
            
            # Display metadata
            console.print(f"[dim]Processing time: {end_time - start_time:.2f}s[/dim]")
            console.print(f"[dim]Tokens used: {result.get('tokens_used', 'Unknown')}[/dim]")
            console.print(f"[dim]Conversation ID: {result.get('conversation_id', 'Unknown')}[/dim]")
            
        except Exception as e:
            console.print(f"[red]❌ Chat failed: {e}[/red]")


@cli.command()
@click.argument("task_id")
@click.pass_context
async def status(ctx, task_id):
    """Check task status."""
    async with GPTInfernseClient(ctx.obj["url"], ctx.obj["token"]) as client:
        try:
            status_info = await client.get_task_status(task_id)
            
            status = status_info.get("status", "unknown")
            color = "green" if status == "completed" else "red" if status == "failed" else "yellow"
            
            console.print(Panel(
                f"[{color}]Status: {status.upper()}[/{color}]\n"
                f"Task ID: {task_id}",
                title="📋 Task Status"
            ))
            
            if "result" in status_info:
                console.print("\n[bold]Result:[/bold]")
                console.print(json.dumps(status_info["result"], indent=2))
            elif "error" in status_info:
                console.print(f"\n[red]Error: {status_info['error']}[/red]")
                
        except Exception as e:
            console.print(f"[red]❌ Failed to get status: {e}[/red]")


@cli.command()
@click.pass_context
async def interactive(ctx):
    """Interactive chat mode."""
    console.print("[bold green]🚀 GPTInfernse Interactive Mode[/bold green]")
    console.print("[dim]Type 'quit' to exit, 'help' for commands[/dim]\n")
    
    async with GPTInfernseClient(ctx.obj["url"], ctx.obj["token"]) as client:
        model = "llama3"
        
        while True:
            try:
                prompt = console.input(f"[cyan][{model}][/cyan] > ")
                
                if prompt.lower() in ["quit", "exit", "q"]:
                    console.print("[yellow]👋 Goodbye![/yellow]")
                    break
                elif prompt.lower() == "help":
                    console.print("""
[bold]Available commands:[/bold]
- /model <name>  : Change model
- /models       : List available models
- /health       : Check API health
- /clear        : Clear screen
- quit/exit/q   : Exit
                    """)
                    continue
                elif prompt.startswith("/model "):
                    model = prompt[7:].strip()
                    console.print(f"[green]✅ Switched to model: {model}[/green]")
                    continue
                elif prompt == "/models":
                    models_info = await client.list_models()
                    for m in models_info.get("models", []):
                        console.print(f"  - {m.get('name', 'Unknown')}")
                    continue
                elif prompt == "/health":
                    health_info = await client.health_check()
                    status = health_info.get("status", "unknown")
                    console.print(f"[green]✅ API Status: {status}[/green]")
                    continue
                elif prompt == "/clear":
                    console.clear()
                    continue
                elif not prompt.strip():
                    continue
                
                # Send chat message
                result = await client.chat_sync(prompt=prompt, model=model)
                
                console.print(f"\n[bold green]🤖 {model}:[/bold green]")
                console.print(result.get("response", "No response"))
                console.print(f"[dim]({result.get('processing_time', 0):.1f}s, {result.get('tokens_used', 0)} tokens)[/dim]\n")
                
            except KeyboardInterrupt:
                console.print("\n[yellow]👋 Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")


def main():
    """Main entry point."""
    # Make all commands async-compatible
    for command in cli.commands.values():
        if asyncio.iscoroutinefunction(command.callback):
            command.callback = lambda *args, **kwargs: asyncio.run(command.callback(*args, **kwargs))
    
    cli()


if __name__ == "__main__":
    main()
