"""LLM evaluation pipeline using promptfoo.

Integrates promptfoo (npm) with AutoPipe to evaluate and compare
your configured Ollama models on pipeline-specific tasks.

Usage:
    autopipe eval --config promptfoo/promptfooconfig.yaml
    autopipe eval --task pipeline-generation --model kimi-k2.5:cloud
    autopipe eval --compare --output eval-results.json

Requires Node.js and a pinned promptfoo version (currently 0.105).
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _check_promptfoo() -> bool:
    """Verify that promptfoo (via npx) is available."""
    try:
        result = subprocess.run(
            ["npx", "promptfoo@0.105", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _ensure_promptfoo() -> None:
    """Exit with helpful message if promptfoo is not available."""
    if not _check_promptfoo():
        console.print(
            Panel.fit(
                "[bold red]promptfoo not found![/bold red]\n\n"
                "promptfoo is required to run LLM evaluations.\n"
                "Install Node.js (v18+) and run:\n\n"
                "  [bold]npm install -g promptfoo[/bold]\n\n"
                "Or use npx (no install):\n\n"
                "  [bold]npx promptfoo@0.105 eval -c promptfoo/promptfooconfig.yaml[/bold]",
                title="Missing Dependency",
                border_style="red",
            )
        )
        raise click.ClickException("promptfoo not available")


def _get_default_config_path() -> Path:
    """Return the default promptfoo config path relative to repo root."""
    # Assume we're running from repo root or autopipe package dir
    candidates = [
        Path.cwd() / "promptfoo" / "promptfooconfig.yaml",
        Path(__file__).parent.parent / "promptfoo" / "promptfooconfig.yaml",
        Path(__file__).parent.parent.parent / "promptfoo" / "promptfooconfig.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p.resolve()
    return candidates[0]


def run_eval(
    config_path: Path,
    provider: Optional[str] = None,
    task: Optional[str] = None,
    output_path: Optional[Path] = None,
    verbose: bool = False,
) -> dict:
    """Run promptfoo eval and return parsed results.

    Args:
        config_path: Path to promptfooconfig.yaml.
        provider: Optional provider filter (e.g. "ollama-kimi").
        task: Optional task/prompt filter (e.g. "pipeline-generation").
        output_path: Where to write the JSON results.
        verbose: Print raw promptfoo output.

    Returns:
        Parsed eval results dict.
    """
    if not config_path.exists():
        raise click.ClickException(f"Config not found: {config_path}")

    cmd = [
        "npx",
        "promptfoo@latest",
        "eval",
        "-c",
        str(config_path),
        "--no-progress-bar",
    ]

    if provider:
        cmd.extend(["--providers", provider])
    if task:
        cmd.extend(["--prompts", task])

    # Output: JSON to temp file
    if output_path:
        cmd.extend(["--output", str(output_path)])
    else:
        cmd.extend(["--output", ".autopipe_eval_results.json"])

    env = os.environ.copy()
    # Inject Ollama creds from .env if present
    for key in ("OLLAMA_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_DEFAULT_MODEL"):
        if key in os.environ:
            env[key] = os.environ[key]

    if verbose:
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise click.ClickException("promptfoo eval timed out after 5 minutes")

    if verbose:
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")

    if result.returncode != 0:
        # Even on eval failures, promptfoo may have output partial results
        console.print(f"[yellow]promptfoo exited with code {result.returncode}[/yellow]")

    # Try to read results from temp / specified output
    results_file = output_path or Path(".autopipe_eval_results.json")
    if results_file.exists():
        with open(results_file) as f:
            return json.load(f)
    return {"results": []}


def _render_results_table(results: dict) -> None:
    """Display a rich table of eval results."""
    if not results.get("results"):
        console.print("[yellow]No eval results to display.[/yellow]")
        return

    table = Table(title="AutoPipe LLM Eval Results", show_lines=True)
    table.add_column("Prompt", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Test", style="blue")
    table.add_column("Pass", style="bold")
    table.add_column("Latency", justify="right")
    table.add_column("Tokens", justify="right")

    for r in results.get("results", []):
        provider = r.get("provider", "?")
        prompt_label = r.get("prompt", {}).get("label", "?")
        vars_desc = r.get("vars", {}).get("task_description", "")[:40]
        passed = "[green]✔[/green]" if r.get("success") else "[red]✘[/red]"
        latency = f"{r.get('latencyMs', 0)}ms"
        tokens = str(r.get("tokenUsage", {}).get("total", "-"))

        table.add_row(
            f"{prompt_label}\n[dim]{vars_desc}...[/dim]",
            provider,
            r.get("description", "?"),
            passed,
            latency,
            tokens,
        )

    console.print(table)

    # Summary
    total = len(results["results"])
    passed = sum(1 for r in results["results"] if r.get("success"))
    console.print(f"\n[bold]{passed}/{total}[/bold] tests passed ({passed / total * 100:.1f}%)")


@click.command("eval")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to promptfoo config YAML.",
)
@click.option(
    "--provider",
    "-p",
    type=str,
    help="Filter by provider ID (e.g. ollama-kimi, ollama-glm, ollama-minimax).",
)
@click.option(
    "--task",
    "-t",
    type=str,
    help="Filter by task/prompt ID (e.g. pipeline-generation, step-explanation).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Path to write JSON results.",
)
@click.option(
    "--compare/--no-compare",
    default=False,
    help="Run full comparison across all configured providers.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show raw promptfoo output.",
)
@click.pass_context
def eval_command(
    ctx: click.Context,
    config: Optional[str],
    provider: Optional[str],
    task: Optional[str],
    output: Optional[str],
    compare: bool,
    verbose: bool,
) -> None:
    """Run LLM evaluations against your configured models.

    Compare outputs from your Ollama models (kimi, glm, minimax)
    on AutoPipe-specific tasks like pipeline generation and error diagnosis.
    """
    console.print(
        Panel.fit(
            "[bold]AutoPipe LLM Evaluation Pipeline[/bold]",
            border_style="cyan",
        )
    )

    _ensure_promptfoo()

    config_path = Path(config) if config else _get_default_config_path()
    if not config_path.exists():
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise click.ClickException("Create promptfoo/promptfooconfig.yaml first.")

    console.print(f"[dim]Using config: {config_path}[/dim]")

    output_path = Path(output) if output else None

    # If compare mode, ensure we don't filter providers
    if compare:
        provider = None
        console.print("[bold]Running comparison across ALL providers...[/bold]")

    # If specific provider requested, map to promptfoo provider ID
    provider_id_map = {
        "kimi-k2.5:cloud": "ollama-kimi",
        "glm-5.1:cloud": "ollama-glm",
        "minimax-m2.7:cloud": "ollama-minimax",
        "kimi": "ollama-kimi",
        "glm": "ollama-glm",
        "minimax": "ollama-minimax",
    }
    if provider and provider in provider_id_map:
        provider = provider_id_map[provider]

    results = run_eval(
        config_path=config_path,
        provider=provider,
        task=task,
        output_path=output_path,
        verbose=verbose,
    )

    _render_results_table(results)

    if output_path:
        console.print(f"\n[dim]Results saved to: {output_path}[/dim]")
