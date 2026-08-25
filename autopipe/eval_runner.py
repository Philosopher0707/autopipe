"""Lightweight Python evaluator for AutoPipe LLM tests.

Falls back to this when promptfoo is unavailable or fails.
Calls Ollama directly via HTTP and runs the same assertions.
"""

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


@dataclass
class EvalResult:
    provider: str
    prompt_label: str
    test_description: str
    success: bool = False
    output: str = ""
    latency_ms: float = 0.0
    tokens: int = 0
    failures: List[str] = field(default_factory=list)


def ollama_chat(model: str, messages: List[Dict[str, str]], timeout: int = 60) -> Dict[str, Any]:
    """Call Ollama chat API."""
    base = OLLAMA_BASE_URL.removesuffix("/v1").rstrip("/")
    url = f"{base}/v1/chat/completions"
    response = requests.post(
        url,
        json={
            "model": model,
            "messages": messages,
            "stream": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def render_prompt(prompt_template: str, vars_dict: Dict[str, str]) -> str:
    """Simple Jinja2-like template rendering."""
    result = prompt_template
    for key, value in vars_dict.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def run_assertion(output: str, assertion: Dict[str, Any]) -> Optional[str]:
    """Run a single assertion. Returns None if pass, error string if fail."""
    assertion_type = assertion.get("type", "contains")
    value = assertion.get("value", "")

    if assertion_type == "contains":
        if value.lower() not in output.lower():
            return f"Expected output to contain '{value}'"
    elif assertion_type == "not-contains":
        if value.lower() in output.lower():
            return f"Expected output NOT to contain '{value}'"
    elif assertion_type == "regex":
        if not re.search(value, output, re.MULTILINE):
            return f"Expected output to match regex '{value}'"
    else:
        return f"Unknown assertion type: {assertion_type}"

    return None


def run_eval(
    config_path: Path,
    provider_filter: Optional[str] = None,
    task_filter: Optional[str] = None,
    verbose: bool = False,
) -> List[EvalResult]:
    """Run evaluation suite from YAML config."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    prompts = {p["id"]: p for p in config.get("prompts", [])}
    providers = config.get("providers", [])
    tests = config.get("tests", [])

    # Filter providers
    if provider_filter:
        providers = [p for p in providers if provider_filter.lower() in str(p).lower()]
    if not providers:
        console.print("[red]No providers matched filter.[/red]")
        return []

    # Filter tests by prompt
    if task_filter:
        tests = [t for t in tests if t.get("prompt") == task_filter]
    if not tests:
        console.print("[red]No tests matched filter.[/red]")
        return []

    results: List[EvalResult] = []
    total = len(providers) * len(tests)
    current = 0

    console.print(
        f"[dim]Running {len(tests)} tests against {len(providers)} provider(s)...[/dim]\n"
    )

    for provider in providers:
        # Extract model name from provider string
        # Format: ollama:chat:model-name
        parts = str(provider).split(":")
        # Handle model names that contain colons (e.g. kimi-k2.5:cloud)
        model = ":".join(parts[2:]) if len(parts) > 2 else str(provider)
        provider_label = str(provider)

        for test in tests:
            current += 1
            prompt_id = test.get("prompt", "")
            prompt = prompts.get(prompt_id, {})
            prompt_label = prompt.get("label", prompt_id)
            test_desc = test.get("description", "unnamed test")
            vars_dict = test.get("vars", {})
            assertions = test.get("assert", [])

            console.print(f"[{current}/{total}] {provider_label} → {test_desc}")

            # Render prompt
            raw_prompt = prompt.get("raw", "")
            user_prompt = render_prompt(raw_prompt, vars_dict)

            # Call Ollama
            start = time.time()
            try:
                response = ollama_chat(
                    model,
                    [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                output = response["choices"][0]["message"]["content"]
                tokens = response.get("usage", {}).get("total_tokens", 0)
            except Exception as e:
                output = f"ERROR: {e}"
                tokens = 0

            latency_ms = (time.time() - start) * 1000

            # Run assertions
            failures = []
            for assertion in assertions:
                failure = run_assertion(output, assertion)
                if failure:
                    failures.append(failure)

            result = EvalResult(
                provider=provider_label,
                prompt_label=prompt_label,
                test_description=test_desc,
                success=len(failures) == 0,
                output=output[:500] + "..." if len(output) > 500 else output,
                latency_ms=latency_ms,
                tokens=tokens,
                failures=failures,
            )
            results.append(result)

            if verbose:
                console.print(f"  Output: {result.output[:200]}...")
                for f in failures:
                    console.print(f"  [red]✘ {f}[/red]")
                if not failures:
                    console.print("  [green]✔ All assertions passed[/green]")
                console.print()

    return results


def render_results(results: List[EvalResult]) -> None:
    """Display results in a rich table."""
    if not results:
        console.print("[yellow]No results.[/yellow]")
        return

    table = Table(title="AutoPipe LLM Eval Results", show_lines=True)
    table.add_column("Prompt", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Test", style="blue")
    table.add_column("Pass", style="bold")
    table.add_column("Latency", justify="right")
    table.add_column("Tokens", justify="right")

    for r in results:
        passed = "[green]✔[/green]" if r.success else "[red]✘[/red]"
        table.add_row(
            r.prompt_label,
            r.provider,
            r.test_description,
            passed,
            f"{r.latency_ms:.0f}ms",
            str(r.tokens),
        )

    console.print(table)

    total = len(results)
    passed = sum(1 for r in results if r.success)
    console.print(f"\n[bold]{passed}/{total}[/bold] tests passed ({passed / total * 100:.1f}%)")

    # Show failures
    failed = [r for r in results if not r.success]
    if failed:
        console.print("\n[bold red]Failures:[/bold red]")
        for r in failed:
            console.print(f"\n[red]• {r.provider} / {r.test_description}[/red]")
            for f in r.failures:
                console.print(f"  - {f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AutoPipe LLM Eval Runner")
    parser.add_argument("-c", "--config", type=Path, default=Path("promptfoo/promptfooconfig.yaml"))
    parser.add_argument("-p", "--provider", help="Filter by provider substring")
    parser.add_argument("-t", "--task", help="Filter by task/prompt ID")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    console.print(Panel.fit("[bold]AutoPipe LLM Eval Runner[/bold]", border_style="cyan"))
    results = run_eval(args.config, args.provider, args.task, args.verbose)
    render_results(results)
