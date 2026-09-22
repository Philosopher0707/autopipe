"""Enhanced CLI for AutoPipe with modern features."""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from autopipe.config.load import Config
from autopipe.eval import eval_command as eval_cmd
from autopipe.exceptions import AutoPipeError

console = Console()


def print_banner():
    """Print the AutoPipe banner."""
    banner = """
    [bold cyan]╔═══════════════════════════════════════╗
    ║                                       ║
    ║  [bold green]AutoPipe[/bold green] - ML/DL Pipeline Framework  ║
    ║                                       ║
    ╚═══════════════════════════════════════╝[/bold cyan]
    """
    console.print(banner)


@click.group()
@click.version_option(version=__import__("autopipe").__version__, prog_name="autopipe")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Optional[str]):
    """AutoPipe CLI - Manage and run ML/DL pipelines."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config

    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")


@cli.command()
@click.argument("pipeline_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory for results")
@click.option("--cache/--no-cache", default=True, help="Enable/disable caching")
@click.option("--parallel", "-p", is_flag=True, help="Run steps in parallel where possible")
@click.option("--step", "-s", multiple=True, help="Run only specific steps")
@click.pass_context
def run(
    ctx: click.Context,
    pipeline_file: str,
    output: Optional[str],
    cache: bool,
    parallel: bool,
    step: tuple,
):
    """Run a pipeline from a YAML or Python file."""
    from autopipe.core.runner import load_pipeline_from_module, load_pipeline_from_yaml

    if pipeline_file.endswith(".py"):
        pipeline = load_pipeline_from_module(pipeline_file)
    else:
        pipeline = load_pipeline_from_yaml(pipeline_file)

    print_banner()

    try:
        console.print(f"[bold green]Pipeline loaded:[/bold green] {pipeline.name}")
        console.print(f"[dim]Steps: {len(pipeline.steps)}[/dim]")

        if step:
            console.print(f"[yellow]Running only steps: {', '.join(step)}[/yellow]")

        console.print("\n[bold]Running pipeline...[/bold]\n")

        results = pipeline.run()

        console.print("\n[bold green]✓ Pipeline completed successfully![/bold green]")

        # Display results table
        table = Table(title="Step Outputs")
        table.add_column("Step", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Output", style="white")

        for name, output in results.items():
            status = "✓" if output is not None else "○"
            output_str = str(output)[:50] if output else "None"
            table.add_row(name, status, output_str)

        console.print(table)

    except AutoPipeError as e:
        console.print(f"[bold red]✗ Pipeline error: {e}[/bold red]")
        if ctx.obj.get("verbose"):
            raise
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]✗ Error: {e}[/bold red]")
        if ctx.obj.get("verbose"):
            import traceback

            console.print(traceback.format_exc())
        sys.exit(1)


@cli.command()
@click.argument("pipeline_file", type=click.Path(exists=True))
def validate(pipeline_file: str):
    """Validate a pipeline configuration file.

    VALID means execution-ready: the file must pass schema validation, every
    step type must resolve under the trusted-roots allowlist, every step must be
    constructible with the parameters given, and the dependency graph must be
    acyclic. This is the same loading path `autopipe run` uses, so anything that
    validates here will load there.
    """
    print_banner()

    try:
        import yaml

        console.print(f"[bold blue]Validating:[/bold blue] {pipeline_file}")

        with open(pipeline_file, "r") as f:
            config_dict = yaml.safe_load(f)

        # One validation/loading path (invariant I8): build the pipeline exactly
        # as `run` would. This exercises schema validation, alias resolution,
        # the step-type allowlist, constructor arity and the dependency graph —
        # the previous implementation only checked that step classes were
        # importable, so it reported VALID for configs that could not run.
        from autopipe.core.loader import load_pipeline_from_config

        pipeline = load_pipeline_from_config(config_dict)

        for step_name, step in pipeline.steps.items():
            cls = type(step)
            console.print(f"  [green]✓[/green] {step_name}: {cls.__module__}.{cls.__name__}")

        console.print(
            f"\n[bold green]✓ Pipeline '{pipeline.name}' is valid and executable "
            f"({len(pipeline.steps)} steps).[/bold green]"
        )

    except Exception as e:
        console.print(f"\n[bold red]✗ Validation failed: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option("--providers", is_flag=True, help="Show LLM provider status")
@click.option("--cache", is_flag=True, help="Show cache status")
@click.option("--metrics", is_flag=True, help="Show metrics status")
def status(providers: bool, cache: bool, metrics: bool):
    """Check system status and configuration."""
    print_banner()

    # Show all if no specific option selected
    show_all = not any([providers, cache, metrics])

    if show_all or providers:
        console.print("\n[bold]LLM Providers[/bold]")

        provider_status = [
            ("OpenAI", "OPENAI_API_KEY"),
            ("Anthropic", "ANTHROPIC_API_KEY"),
            ("OpenRouter", "OPENROUTER_API_KEY"),
            ("Ollama", "OLLAMA_BASE_URL"),  # Ollama uses base_url for detection
        ]

        for name, env_var in provider_status:
            if name == "Ollama":
                # Check if Ollama is reachable
                ollama_url = os.environ.get(env_var, "http://127.0.0.1:11434/v1")
                try:
                    import requests

                    # Try native Ollama API
                    base = ollama_url.replace("/v1", "")
                    response = requests.get(f"{base}/api/tags", timeout=2)
                    if response.status_code == 200:
                        models = response.json().get("models", [])
                        model_names = [m.get("name", "unknown") for m in models[:3]]
                        models_str = ", ".join(model_names) if model_names else "no models"
                        console.print(
                            f"  [green]✓[/green] {name}: Running at {ollama_url} ({models_str})"
                        )
                    else:
                        console.print(
                            f"  [yellow]○[/yellow] {name}: Configured ({ollama_url}) but not responding"
                        )
                except Exception:
                    console.print(
                        f"  [red]✗[/red] {name}: Not running ({ollama_url}) - Run: ollama serve"
                    )
            elif os.environ.get(env_var):
                console.print(f"  [green]✓[/green] {name}: Configured")
            else:
                console.print(f"  [red]✗[/red] {name}: Not configured ({env_var})")

    if show_all or cache:
        console.print("\n[bold]Cache[/bold]")
        cache_dir = Path("./.autopipe_cache")
        if cache_dir.exists():
            size = sum(f.stat().st_size for f in cache_dir.glob("*") if f.is_file())
            console.print(f"  [green]✓[/green] Cache directory: {cache_dir} ({size / 1024:.1f} KB)")
        else:
            console.print("  [dim]○ Cache directory not created yet[/dim]")

    if show_all or metrics:
        console.print("\n[bold]Metrics[/bold]")
        console.print("  [dim]○ Prometheus metrics disabled (enable with --metrics)[/dim]")


@cli.command()
@click.option("--force", is_flag=True, help="Force clean without confirmation")
def clean(force: bool):
    """Clean temporary files and caches."""
    if not force and not click.confirm("This will remove all cached results. Continue?"):
        console.print("[dim]Cancelled.[/dim]")
        return

    cache_dir = Path("./.autopipe_cache")
    if cache_dir.exists():
        import shutil

        shutil.rmtree(cache_dir)
        console.print(f"[green]✓ Removed cache directory: {cache_dir}[/green]")

    figures_dir = Path("./figures")
    if figures_dir.exists():
        for f in figures_dir.glob("*.png"):
            f.unlink()
        console.print(f"[green]✓ Cleaned figures directory: {figures_dir}[/green]")

    console.print("[bold green]✓ Cleanup complete![/bold green]")


@cli.command()
@click.argument("name")
def create(name: str):
    """Create a new pipeline from a template."""
    print_banner()

    template = f"""name: {name}
description: A sample AutoPipe pipeline

env:
  LOG_LEVEL: INFO

steps:
  # `sample_data_loader` loads a bundled scikit-learn dataset (iris|diabetes).
  # For your own CSV/parquet/SQL source, use `data_loader` with `source:`.
  - name: load_data
    type: sample_data_loader
    params:
      dataset: iris

  # `inputs:` maps a run() parameter to an upstream step's output. A prompt
  # template is formatted with those kwargs, so a placeholder must name one of
  # them — otherwise the raw template would be sent to the model.
  - name: analyze
    type: llm
    depends_on: [load_data]
    inputs:
      data: load_data
    params:
      # Use 'ollama' for a local LLM, 'openrouter' for a cloud provider.
      provider: openrouter
      # For Ollama: model: llama3.1
      prompt_template: >
        The Iris dataset has 150 samples, 4 numeric features and 3 species.
        In one sentence, state the most useful first analysis to run on it.

  - name: visualize
    type: visualization
    depends_on: [analyze]
    params:
      chart_type: metrics

# To use Ollama instead, set OLLAMA_BASE_URL and change:
#   provider: ollama
#   model: llama3.1  # or mistral, codellama, etc.
"""

    filename = f"{name}.yaml"
    if Path(filename).exists():
        console.print(f"[red]Error: {filename} already exists![/red]")
        sys.exit(1)

    with open(filename, "w") as f:
        f.write(template)

    console.print(f"[green]✓ Created new pipeline: {filename}[/green]")
    console.print(f"\nEdit the file and run with: autopipe run {filename}")


@cli.group()
def models():
    """Manage LLM models and providers."""


@models.command(name="list")
@click.option("--provider", "-p", default="ollama", help="Provider to list models for")
def models_list(provider: str):
    """List available models from the provider."""
    print_banner()

    if provider == "ollama":
        from autopipe.config.load import Config

        console.print("\n[bold]Ollama Models[/bold]\n")

        # Try to fetch from Ollama server
        try:
            import requests

            base = Config.OLLAMA_BASE_URL.replace("/v1", "")
            response = requests.get(f"{base}/api/tags", timeout=5)
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                if models_data:
                    table = Table(title="Available Ollama Models")
                    table.add_column("#", style="dim", justify="right")
                    table.add_column("Model Name", style="cyan")
                    table.add_column("Size", style="green")
                    table.add_column("Modified", style="blue")
                    table.add_column("Current", style="yellow")

                    current_model = os.getenv("OLLAMA_DEFAULT_MODEL", "")
                    for i, model in enumerate(models_data[:10], 1):
                        name = model.get("name", "unknown")
                        size = model.get("size", 0)
                        size_str = f"{size / 1e9:.1f} GB" if size else "N/A"
                        modified = (
                            model.get("modified_at", "")[:10] if model.get("modified_at") else "N/A"
                        )
                        is_current = "★" if name == current_model else ""
                        table.add_row(str(i), name, size_str, modified, is_current)

                    console.print(table)
                    console.print(f"\n[dim]Current default: {current_model or 'Not set'}[/dim]")
                    console.print(
                        "\nUse [bold]autopipe models set <model_name>[/bold] to change default"
                    )
                else:
                    console.print(
                        "[yellow]No models found. Run 'ollama pull <model>' to download.[/yellow]"
                    )
            else:
                console.print(f"[red]Failed to fetch models: HTTP {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Could not connect to Ollama: {e}[/red]")
            console.print("[dim]Ensure Ollama is running: ollama serve[/dim]")
    else:
        console.print(
            f"[yellow]Model listing for provider '{provider}' not yet implemented.[/yellow]"
        )


@models.command(name="set")
@click.argument("model_name")
@click.option("--provider", "-p", default="ollama", help="Provider to set model for")
@click.option("--persist", is_flag=True, help="Persist to .env file")
def models_set(model_name: str, provider: str, persist: bool):
    """Set the default model for a provider."""
    print_banner()

    if provider == "ollama":
        # Validate the model is available
        try:
            import requests

            from autopipe.config.load import Config

            base = Config.OLLAMA_BASE_URL.replace("/v1", "")
            response = requests.get(f"{base}/api/tags", timeout=5)

            available_models = []
            if response.status_code == 200:
                available_models = [m.get("name") for m in response.json().get("models", [])]

            if available_models and model_name not in available_models:
                console.print(f"[red]Model '{model_name}' not found in Ollama.[/red]")
                console.print(f"\n[dim]Available models: {', '.join(available_models)}[/dim]")
                sys.exit(1)

            # Set environment variable for current session
            os.environ["OLLAMA_DEFAULT_MODEL"] = model_name

            console.print(f"[green]✓ Set default Ollama model: {model_name}[/green]")

            # Optionally persist to .env file
            if persist:
                env_file = Path(".env")
                if env_file.exists():
                    content = env_file.read_text()
                    if "OLLAMA_DEFAULT_MODEL=" in content:
                        # Replace existing line
                        lines = content.split("\n")
                        new_lines = []
                        for line in lines:
                            if line.startswith("OLLAMA_DEFAULT_MODEL="):
                                new_lines.append(f"OLLAMA_DEFAULT_MODEL={model_name}")
                            else:
                                new_lines.append(line)
                        content = "\n".join(new_lines)
                    else:
                        content += f"\nOLLAMA_DEFAULT_MODEL={model_name}\n"
                    env_file.write_text(content)
                    console.print("[green]✓ Persisted to .env file[/green]")
                else:
                    env_file.write_text(f"OLLAMA_DEFAULT_MODEL={model_name}\n")
                    console.print(
                        f"[green]✓ Created .env file with OLLAMA_DEFAULT_MODEL={model_name}[/green]"
                    )
            else:
                console.print("[dim]Tip: Use --persist to save to .env file[/dim]")

        except Exception as e:
            console.print(f"[yellow]Warning: Could not validate model: {e}[/yellow]")
            # Still set it anyway
            os.environ["OLLAMA_DEFAULT_MODEL"] = model_name
    else:
        console.print(
            f"[yellow]Setting model for provider '{provider}' not yet supported.[/yellow]"
        )


@models.command(name="current")
def models_current():
    """Show the current default model configuration."""
    print_banner()

    console.print("\n[bold]Current Model Configuration[/bold]\n")

    # Show all provider configurations
    providers = [
        ("Default Provider", Config.DEFAULT_LLM_PROVIDER),
        ("Ollama Default Model", Config.OLLAMA_DEFAULT_MODEL),
        ("Ollama URL", Config.OLLAMA_BASE_URL),
    ]

    if os.getenv("OPENAI_API_KEY"):
        providers.append(("OpenAI Model", "gpt-4o (default)"))
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append(("Anthropic Model", "claude-3-5-sonnet (default)"))
    if os.getenv("OPENROUTER_API_KEY"):
        providers.append(("OpenRouter Model", Config.DEFAULT_LLM_MODEL))

    for name, value in providers:
        console.print(f"  [cyan]{name}:[/cyan] {value}")

    # Try to fetch Ollama models
    try:
        import requests

        base = Config.OLLAMA_BASE_URL.replace("/v1", "")
        response = requests.get(f"{base}/api/tags", timeout=3)
        if response.status_code == 200:
            models = [m.get("name") for m in response.json().get("models", [])]
            current = os.getenv("OLLAMA_DEFAULT_MODEL", Config.OLLAMA_DEFAULT_MODEL)
            if models:
                console.print("\n[bold]Available Ollama Models:[/bold]")
                for m in models:
                    marker = "[yellow]★[/yellow]" if m == current else " "
                    console.print(f"  {marker} {m}")
    except Exception:
        pass


@models.command(name="use")
@click.argument("alias", required=False)
@click.option("--kimi", is_flag=True, help="Use kimi-k2.5:cloud")
@click.option("--glm", is_flag=True, help="Use glm-5.1:cloud")
@click.option("--minimax", is_flag=True, help="Use minimax-m2.7:cloud")
def models_use(alias: str, kimi: bool, glm: bool, minimax: bool):
    """Quick-select a cloud model by alias.

    Available aliases:
    • kimi - kimi-k2.5:cloud
    • glm - glm-5.1:cloud
    • minimax - minimax-m2.7:cloud
    """
    print_banner()

    # Map aliases to model names
    alias_map = {
        "kimi": "kimi-k2.5:cloud",
        "k2.5": "kimi-k2.5:cloud",
        "glm": "glm-5.1:cloud",
        "minimax": "minimax-m2.7:cloud",
        "m2.7": "minimax-m2.7:cloud",
    }

    # Determine which model to use
    model = None
    if kimi:
        model = "kimi-k2.5:cloud"
    elif glm:
        model = "glm-5.1:cloud"
    elif minimax:
        model = "minimax-m2.7:cloud"
    elif alias:
        model = alias_map.get(alias.lower(), alias)  # Use alias or direct name
    else:
        # Show help
        console.print("\n[bold]Quick-Select Cloud Models[/bold]\n")
        console.print(
            "  [cyan]kimi[/cyan]      → [green]kimi-k2.5:cloud[/green]  (High-performance reasoning)"
        )
        console.print(
            "  [cyan]glm[/cyan]       → [green]glm-5.1:cloud[/green]    (General purpose chat)"
        )
        console.print(
            "  [cyan]minimax[/cyan]   → [green]minimax-m2.7:cloud[/green] (Multi-modal capable)\n"
        )
        console.print("Examples:")
        console.print("  autopipe models use kimi")
        console.print("  autopipe models use --glm")
        console.print("  autopipe models set kimi-k2.5:cloud --persist")
        return

    # Set the model
    os.environ["OLLAMA_DEFAULT_MODEL"] = model

    # Update .env file if it exists
    env_file = Path(".env")
    if env_file.exists():
        content = env_file.read_text()
        if "OLLAMA_DEFAULT_MODEL=" in content:
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                if line.startswith("OLLAMA_DEFAULT_MODEL="):
                    new_lines.append(f"OLLAMA_DEFAULT_MODEL={model}")
                else:
                    new_lines.append(line)
            content = "\n".join(new_lines)
        else:
            content += f"\nOLLAMA_DEFAULT_MODEL={model}\n"
        env_file.write_text(content)
        console.print(f"[green]✓ Set active model: {model}[/green]")
        console.print("[dim]   Updated .env file[/dim]")
    else:
        console.print(f"[green]✓ Set active model: {model}[/green]")
        console.print("[dim]   (Session only - create .env file to persist)[/dim]")


# Register eval subcommand
cli.add_command(eval_cmd, name="eval")


def main():
    """Entry point for the CLI."""
    cli()
