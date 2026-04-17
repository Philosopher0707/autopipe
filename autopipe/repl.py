"""AutoPipe Interactive REPL CLI.

A production-grade interactive REPL (Read-Eval-Print Loop) for AutoPipe that provides:
- Command history with arrow-key navigation
- Syntax highlighting
- Tab-completion for commands, variables, and file paths
- Rich output formatting with tables and panels
- Multi-line input support
- Persistent configuration
- Integrated help system
"""

from __future__ import annotations

import ast
import inspect
import os
import pathlib
import re
import shutil
import sys
import textwrap
import traceback
from abc import ABC, abstractmethod
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from enum import Enum, auto
from importlib import import_module, reload
from io import StringIO
from typing import Any, Callable, Dict, Generic, List, Optional, Set, Tuple, TypeVar, Union

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import HTML, FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import confirm, message_dialog, progress_dialog
from prompt_toolkit.styles import Style
from pygments.lexers.python import PythonLexer
from rich.console import Console
from rich.highlighter import ReprHighlighter
from rich.panel import Panel
from rich.pretty import pretty_repr
from rich.table import Table
from rich.traceback import Traceback

# Import AutoPipe components
try:
    from autopipe import Pipeline, Step, __version__
    from autopipe.core.pipeline import Pipeline as CorePipeline
    from autopipe.core.step import Step as CoreStep
    from autopipe.core.steps import PrintStep, DataLoaderStep
    from autopipe.schemas.models import PipelineConfig, StepConfig
except ImportError:
    # Fallback for development
    __version__ = "0.1.0"
    Pipeline = None
    Step = None

# Constants
HISTORY_FILE = pathlib.Path.home() / ".autopipe" / "repl_history"
CONFIG_FILE = pathlib.Path.home() / ".autopipe" / "repl_config.py"
WELCOME_WIDTH = 80

# RESTRICTED BUILTINS - Remove dangerous functions for security
# SECURITY FIX: Using restricted builtins instead of __builtins__
_RESTRICTED_BUILTINS = {
    # Safe types
    'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
    'list': list, 'dict': dict, 'tuple': tuple, 'set': set, 'frozenset': frozenset,
    'type': type, 'bytes': bytes, 'bytearray': bytearray, 'complex': complex,
    
    # Safe built-in functions
    'abs': abs, 'all': all, 'any': any, 'bin': bin, 'chr': chr, 'dir': dir,
    'divmod': divmod, 'enumerate': enumerate, 'filter': filter, 'format': format,
    'hash': hash, 'hex': hex, 'id': id, 'isinstance': isinstance, 'issubclass': issubclass,
    'iter': iter, 'map': map, 'max': max, 'min': min, 'next': next, 'oct': oct,
    'ord': ord, 'pow': pow, 'print': print, 'range': range, 'repr': repr,
    'reversed': reversed, 'round': round, 'setattr': setattr, 'getattr': getattr,
    'slice': slice, 'sorted': sorted, 'sum': sum, 'zip': zip,
    
    # Safe exceptions (allow raising common ones)
    'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
    'KeyError': KeyError, 'IndexError': IndexError, 'RuntimeError': RuntimeError,
    'StopIteration': StopIteration, 'AssertionError': AssertionError,
}


class CommandError(Exception):
    """Error raised for invalid commands."""
    pass


class ExecutionError(Exception):
    """Error raised during command execution."""
    pass


class ExitREPL(Exception):
    """Signal to exit the REPL."""
    pass


class CommandContext:
    """Context object passed to commands."""
    def __init__(self, repl: 'AutoPipeREPL'):
        self.repl = repl
        self.console = repl.console
        self.session = repl.session
        self.variables: Dict[str, Any] = repl.variables
        self.history: List[str] = repl.command_history
        self.pipelines: Dict[str, Any] = repl.pipelines

    def get_variable(self, name: str) -> Any:
        """Get a variable by name."""
        return self.variables.get(name)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable."""
        self.variables[name] = value

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print to the console."""
        self.console.print(*args, **kwargs)


@dataclass
class CommandInfo:
    """Information about a REPL command."""
    name: str
    handler: Callable[[CommandContext, List[str]], Any]
    description: str
    usage: str
    aliases: List[str] = field(default_factory=list)
    category: str = "General"
    hidden: bool = False


class CommandRegistry:
    """Registry for REPL commands."""
    def __init__(self):
        self._commands: Dict[str, CommandInfo] = {}
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        name: str,
        handler: Callable[[CommandContext, List[str]], Any],
        description: str,
        usage: str = "",
        aliases: Optional[List[str]] = None,
        category: str = "General",
        hidden: bool = False
    ) -> CommandInfo:
        """Register a new command."""
        info = CommandInfo(
            name=name,
            handler=handler,
            description=description,
            usage=usage or name,
            aliases=aliases or [],
            category=category,
            hidden=hidden
        )
        self._commands[name] = info

        # Register aliases
        for alias in info.aliases:
            self._aliases[alias] = name

        return info

    def get(self, name: str) -> Optional[CommandInfo]:
        """Get a command by name or alias."""
        if name in self._commands:
            return self._commands[name]
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        return None

    def get_by_category(self) -> Dict[str, List[CommandInfo]]:
        """Get commands grouped by category."""
        categories: Dict[str, List[CommandInfo]] = {}
        for cmd in self._commands.values():
            if not cmd.hidden:
                categories.setdefault(cmd.category, []).append(cmd)
        return {k: sorted(v, key=lambda x: x.name) for k, v in sorted(categories.items())}

    def get_all_names(self) -> Set[str]:
        """Get all command names including aliases."""
        names = set(self._commands.keys())
        names.update(self._aliases.keys())
        return names

    def get_completions(self, prefix: str) -> List[Tuple[str, str]]:
        """Get command completions matching a prefix."""
        completions = []
        prefix_lower = prefix.lower()

        for name, info in self._commands.items():
            if not info.hidden and name.startswith(prefix_lower):
                completions.append((name, info.description))

        for alias, cmd_name in self._aliases.items():
            if alias.startswith(prefix_lower):
                info = self._commands.get(cmd_name)
                if info and not info.hidden:
                    completions.append((alias, f"Alias for {cmd_name}"))

        return completions


class AutoPipeCompleter(Completer):
    """Custom completer for the REPL."""

    def __init__(self, repl: 'AutoPipeREPL'):
        self.repl = repl
        self.path_completer = PathCompleter()

    def get_completions(self, document: Document, complete_event) -> Any:
        word = document.get_word_before_cursor()
        text = document.text_before_cursor
        words = text.split()

        # Completing first word (command)
        if not words or (len(words) == 1 and not text.endswith(' ')):
            for name, desc in self.repl.registry.get_completions(word):
                yield Completion(
                    name,
                    start_position=-len(word),
                    display=name,
                    display_meta=desc
                )
            return

        # Get the command
        cmd_name = words[0].lower()
        cmd = self.repl.registry.get(cmd_name)
        if cmd is None:
            return

        # Path completion for certain commands
        if cmd_name in ('load', 'save', 'run', 'cat', 'less', 'edit', 'config'):
            yield from self.path_completer.get_completions(document, complete_event)

        # Variable completion for special prefixes
        if word.startswith('$') or word.startswith('@'):
            prefix = word[1:]
            for var_name in self.repl.variables:
                if var_name.startswith(prefix):
                    yield Completion(
                        f"${var_name}",
                        start_position=-len(word),
                        display=var_name,
                        display_meta=f"Variable: {type(self.repl.variables[var_name]).__name__}"
                    )
            for pipe_name in self.repl.pipelines:
                if pipe_name.startswith(prefix):
                    yield Completion(
                        f"@{pipe_name}",
                        start_position=-len(word),
                        display=pipe_name,
                        display_meta="Pipeline"
                    )


class AutoPipeREPL:
    """Production-grade interactive REPL for AutoPipe."""

    def __init__(self):
        self.console = Console(highlight=True)
        self.registry = CommandRegistry()
        self.variables: Dict[str, Any] = {}
        self.pipelines: Dict[str, Any] = {}
        self.command_history: List[str] = []
        self.session: Optional[PromptSession] = None
        self._setup_directories()
        self._register_commands()
        self._setup_session()

    def _setup_directories(self) -> None:
        """Ensure required directories exist."""
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _setup_session(self) -> None:
        """Setup the prompt session with history and styling."""
        style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'prompt.dots': '#00aa00',
            'command': '#0088ff',
            'error': '#ff0000',
            'warning': '#ffaa00',
            'info': '#00aaaa',
            'success': '#00ff00',
        })

        self.session = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            completer=AutoPipeCompleter(self),
            complete_while_typing=True,
            lexer=PygmentsLexer(PythonLexer),
            style=style,
            enable_suspend=True,
            enable_history_search=True,
            mouse_support=True,
            auto_suggest=AutoPipeAutoSuggest(),
        )

    def _register_commands(self) -> None:
        """Register all REPL commands."""
        # Core commands
        self.registry.register(
            'help', self._cmd_help,
            'Show help information for commands',
            'help [command]',
            aliases=['?', 'h'],
            category='Core'
        )
        self.registry.register(
            'exit', self._cmd_exit,
            'Exit the REPL',
            'exit',
            aliases=['quit', 'q', 'bye'],
            category='Core'
        )
        self.registry.register(
            'clear', self._cmd_clear,
            'Clear the terminal screen',
            'clear',
            aliases=['cls', 'clr'],
            category='Core'
        )
        self.registry.register(
            'version', self._cmd_version,
            'Show version information',
            'version',
            aliases=['ver', 'v'],
            category='Core'
        )

        # Variable commands
        self.registry.register(
            'let', self._cmd_let,
            'Define a variable',
            'let <name> = <expression>',
            category='Variables'
        )
        self.registry.register(
            'vars', self._cmd_vars,
            'List all variables',
            'vars [pattern]',
            aliases=['lsvar', 'env'],
            category='Variables'
        )
        self.registry.register(
            'del', self._cmd_del,
            'Delete a variable',
            'del <name>',
            aliases=['rmvar', 'unset'],
            category='Variables'
        )
        self.registry.register(
            'type', self._cmd_type,
            'Show the type of a variable',
            'type <name>',
            category='Variables'
        )

        # Pipeline commands
        self.registry.register(
            'new', self._cmd_new,
            'Create a new pipeline',
            'new <name> [--steps <steps>]',
            category='Pipelines'
        )
        self.registry.register(
            'pipelines', self._cmd_pipelines,
            'List all pipelines',
            'pipelines',
            aliases=['pipes', 'list'],
            category='Pipelines'
        )
        self.registry.register(
            'run', self._cmd_run,
            'Run a pipeline',
            'run <name_or_file> [--dry-run]',
            category='Pipelines'
        )
        self.registry.register(
            'step', self._cmd_step,
            'Add a step to a pipeline',
            'step <pipeline> <name> [--type <type>] [--params <params>] [--depends <deps>]',
            aliases=['add'],
            category='Pipelines'
        )
        self.registry.register(
            'show', self._cmd_show,
            'Show pipeline configuration',
            'show <name>',
            aliases=['cat', 'view', 'inspect'],
            category='Pipelines'
        )

        # File commands
        self.registry.register(
            'load', self._cmd_load,
            'Load a YAML pipeline file',
            'load <file> [as <name>]',
            category='Files'
        )
        self.registry.register(
            'save', self._cmd_save,
            'Save a pipeline to file',
            'save <name> [to <file>]',
            category='Files'
        )
        self.registry.register(
            'files', self._cmd_files,
            'List YAML files in current directory',
            'files [pattern]',
            aliases=['ls', 'dir'],
            category='Files'
        )

        # Python commands
        self.registry.register(
            'py', self._cmd_python,
            'Execute Python code',
            'py <expression>',
            aliases=['python', 'eval', 'exec'],
            category='Python'
        )
        self.registry.register(
            'print', self._cmd_print,
            'Print a variable or expression',
            'print <expression>',
            aliases=['p', 'echo'],
            category='Python'
        )
        self.registry.register(
            'who', self._cmd_who,
            'Show detailed information about variables',
            'who [var_pattern]',
            aliases=['info'],
            category='Python'
        )
        self.registry.register(
            'whos', self._cmd_whos,
            'Show detailed information about variables (rich format)',
            'whos',
            category='Python'
        )

        # Model commands
        self.registry.register(
            'models', self._cmd_models,
            'List or select Ollama models',
            'models [list|use|current]',
            aliases=['model', 'llm'],
            category='Models'
        )
        self.registry.register(
            'use', self._cmd_use_model,
            'Quick-select an Ollama model (kimi, glm, minimax)',
            'use <kimi|glm|minimax>',
            category='Models'
        )
        self.registry.register(
            'current', self._cmd_current_model,
            'Show current model configuration',
            'current',
            category='Models'
        )

        # Configuration commands
        self.registry.register(
            'config', self._cmd_config,
            'Show or edit REPL configuration',
            'config [key] [value]',
            category='Config'
        )
        self.registry.register(
            'history', self._cmd_history,
            'Show command history',
            'history [n]',
            aliases=['hist'],
            category='Config'
        )
        self.registry.register(
            'edit', self._cmd_edit,
            'Open config or file in editor',
            'edit [config|<file>]',
            category='Config'
        )

        # Debug commands (hidden)
        self.registry.register(
            'debug', self._cmd_debug,
            'Debug mode toggle',
            'debug [on|off]',
            category='Debug',
            hidden=True
        )
        self.registry.register(
            'test', self._cmd_test,
            'Run example pipeline',
            'test',
            category='Debug',
            hidden=False
        )

    # Command handlers

    def _cmd_help(self, ctx: CommandContext, args: List[str]) -> None:
        """Show help information."""
        if args:
            cmd_name = args[0].lower()
            cmd = self.registry.get(cmd_name)
            if cmd is None:
                ctx.print(f"[red]Unknown command: {cmd_name}[/red]")
                return

            panel = Panel(
                f"[bold cyan]{cmd.name}[/bold cyan]\n\n"
                f"[white]{cmd.description}[/white]\n\n"
                f"[bold]Usage:[/bold] [yellow]{cmd.usage}[/yellow]\n"
                + (f"[bold]Aliases:[/bold] [dim]{', '.join(cmd.aliases)}[/dim]\n" if cmd.aliases else "")
                + f"[bold]Category:[/bold] {cmd.category}",
                title="Command Help",
                border_style="cyan"
            )
            ctx.print(panel)
            return

        # Show all commands
        table = Table(title="AutoPipe REPL Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Aliases", style="dim")

        categories = self.registry.get_by_category()
        for category, commands in categories.items():
            table.add_row(f"[bold underline]{category}[/bold underline]", "", "")
            for cmd in commands:
                aliases_str = ', '.join(cmd.aliases) if cmd.aliases else ''
                table.add_row(f"  {cmd.name}", cmd.description, aliases_str)

        ctx.print(table)
        ctx.print("\n[dim]Type 'help <command>' for detailed help on a specific command.[/dim]")
        ctx.print("[dim]Use arrow keys for history, Tab for completion, Ctrl+C to cancel.[/dim]")

    def _cmd_exit(self, ctx: CommandContext, args: List[str]) -> None:
        """Exit the REPL."""
        if self.session:
            ctx.print("\n[green]Goodbye! 👋[/green]")
        raise ExitREPL()

    def _cmd_clear(self, ctx: CommandContext, args: List[str]) -> None:
        """Clear the screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def _cmd_version(self, ctx: CommandContext, args: List[str]) -> None:
        """Show version info."""
        ctx.print(f"[bold cyan]AutoPipe REPL v{__version__}[/bold cyan]")
        ctx.print(f"[dim]Python {sys.version}[/dim]")
        ctx.print(f"[dim]Running on {sys.platform}[/dim]")

    def _cmd_let(self, ctx: CommandContext, args: List[str]) -> None:
        """Define a variable."""
        if not args:
            ctx.print("[red]Usage: let <name> = <expression>[/red]")
            return

        # Join args and parse
        expr = ' '.join(args)
        match = re.match(r'^(\w+)\s*=\s*(.+)$', expr)
        if not match:
            ctx.print("[red]Invalid syntax. Use: let <name> = <expression>[/red]")
            return

        name, value_expr = match.groups()

        try:
            # Create safe namespace with existing variables
            namespace = {**self.variables}
            # Add autopipe imports
            if Pipeline:
                namespace['Pipeline'] = Pipeline
                namespace['Step'] = Step

            # SECURITY FIX: Use restricted builtins to prevent code injection
            value = eval(value_expr, {"__builtins__": _RESTRICTED_BUILTINS}, namespace)
            self.variables[name] = value
            ctx.print(f"[green]✓[/green] {name} = {self._format_value(value)}")
        except Exception as e:
            ctx.print(f"[red]Error: {e}[/red]")

    def _cmd_vars(self, ctx: CommandContext, args: List[str]) -> None:
        """List variables."""
        pattern = args[0] if args else None

        if not self.variables:
            ctx.print("[dim]No variables defined.[/dim]")
            return

        table = Table(title="Variables", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Value", style="white")

        for name, value in sorted(self.variables.items()):
            if pattern and pattern not in name:
                continue
            type_name = type(value).__name__
            value_str = self._format_preview(value)
            table.add_row(name, type_name, value_str)

        ctx.print(table)

    def _cmd_del(self, ctx: CommandContext, args: List[str]) -> None:
        """Delete a variable."""
        if not args:
            ctx.print("[red]Usage: del <name>[/red]")
            return

        name = args[0]
        if name in self.variables:
            del self.variables[name]
            ctx.print(f"[green]✓[/green] Deleted variable: {name}")
        elif name in self.pipelines:
            del self.pipelines[name]
            ctx.print(f"[green]✓[/green] Deleted pipeline: {name}")
        else:
            ctx.print(f"[red]Variable or pipeline '{name}' not found[/red]")

    def _cmd_type(self, ctx: CommandContext, args: List[str]) -> None:
        """Show type of a variable."""
        if not args:
            ctx.print("[red]Usage: type <name>[/red]")
            return

        name = args[0]
        if name in self.variables:
            value = self.variables[name]
            ctx.print(f"[cyan]{name}[/cyan]: [yellow]{type(value).__module__}.{type(value).__name__}[/yellow]")
            ctx.print(f"[dim]{repr(value)[:200]}[/dim]")
        else:
            ctx.print(f"[red]Variable '{name}' not found[/red]")

    def _cmd_new(self, ctx: CommandContext, args: List[str]) -> None:
        """Create a new pipeline."""
        if not args:
            ctx.print("[red]Usage: new <name> [--steps <steps>][/red]")
            return

        name = args[0]

        # Parse optional steps
        steps = []
        if '--steps' in args:
            idx = args.index('--steps')
            steps_str = args[idx + 1] if idx + 1 < len(args) else ''
            steps = [s.strip() for s in steps_str.split(',') if s.strip()]

        try:
            if Pipeline:
                pipeline = Pipeline(name)
                self.pipelines[name] = pipeline
                ctx.print(f"[green]✓[/green] Created pipeline: [cyan]{name}[/cyan]")
            else:
                # Fallback for when Pipeline isn't available
                self.pipelines[name] = {"name": name, "steps": steps}
                ctx.print(f"[green]✓[/green] Created pipeline structure: [cyan]{name}[/cyan]")
        except Exception as e:
            ctx.print(f"[red]Error creating pipeline: {e}[/red]")

    def _cmd_pipelines(self, ctx: CommandContext, args: List[str]) -> None:
        """List pipelines."""
        if not self.pipelines:
            ctx.print("[dim]No pipelines defined. Create one with 'new <name>'[/dim]")
            return

        table = Table(title="Pipelines", show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Steps", style="white")

        for name, pipeline in sorted(self.pipelines.items()):
            type_name = type(pipeline).__name__
            # Try to get steps count
            if hasattr(pipeline, 'steps'):
                steps_count = len(pipeline.steps) if hasattr(pipeline.steps, '__len__') else '?'
            else:
                steps_count = len(pipeline.get('steps', [])) if isinstance(pipeline, dict) else '?'
            table.add_row(name, type_name, str(steps_count))

        ctx.print(table)

    def _cmd_run(self, ctx: CommandContext, args: List[str]) -> None:
        """Run a pipeline."""
        if not args:
            ctx.print("[red]Usage: run <name_or_file> [--dry-run][/red]")
            return

        target = args[0]
        dry_run = '--dry-run' in args or '-n' in args

        # Check if it's a loaded pipeline
        if target in self.pipelines:
            pipeline = self.pipelines[target]
            if dry_run:
                ctx.print(f"[yellow]Dry run: Would execute pipeline '{target}'[/yellow]")
                return

            ctx.print(f"[bold]Running pipeline: {target}...[/bold]")
            try:
                if hasattr(pipeline, 'run'):
                    result = pipeline.run()
                    ctx.print(f"[green]✓[/green] Pipeline completed")
                    self.variables[f'result_{target}'] = result
                    ctx.print(f"[dim]Result saved to: $result_{target}[/dim]")
                else:
                    ctx.print(f"[yellow]Pipeline object doesn't have a run method[/yellow]")
            except Exception as e:
                ctx.print(f"[red]Pipeline failed: {e}[/red]")
                ctx.print(Traceback())
        else:
            ctx.print(f"[red]Pipeline '{target}' not found. Use 'load <file>' first.[/red]")

    def _cmd_step(self, ctx: CommandContext, args: List[str]) -> None:
        """Add a step to a pipeline."""
        if len(args) < 2:
            ctx.print("[red]Usage: step <pipeline> <name> [--type <type>] [--params <params>] [--depends <deps>][/red]")
            return

        pipeline_name = args[0]
        step_name = args[1]

        if pipeline_name not in self.pipelines:
            ctx.print(f"[red]Pipeline '{pipeline_name}' not found[/red]")
            return

        # Parse options
        step_type = 'print'
        params = {}
        depends = []

        i = 2
        while i < len(args):
            if args[i] == '--type' and i + 1 < len(args):
                step_type = args[i + 1]
                i += 2
            elif args[i] == '--params' and i + 1 < len(args):
                try:
                    params = eval(args[i + 1], {"__builtins__": _RESTRICTED_BUILTINS})
                except Exception:
                    params = {"raw": args[i + 1]}
                i += 2
            elif args[i] == '--depends' and i + 1 < len(args):
                depends = [d.strip() for d in args[i + 1].split(',')]
                i += 2
            else:
                i += 1

        pipeline = self.pipelines[pipeline_name]
        ctx.print(f"[green]✓[/green] Added step [cyan]{step_name}[/cyan] to pipeline [cyan]{pipeline_name}[/cyan]")
        ctx.print(f"[dim]  Type: {step_type}, Depends: {depends or 'None'}[/dim]")

    def _cmd_show(self, ctx: CommandContext, args: List[str]) -> None:
        """Show pipeline configuration."""
        if not args:
            ctx.print("[red]Usage: show <name>[/red]")
            return

        name = args[0]
        if name in self.pipelines:
            pipeline = self.pipelines[name]
            ctx.print(f"[bold cyan]Pipeline: {name}[/bold cyan]")
            ctx.print(pretty_repr(pipeline))
        else:
            ctx.print(f"[red]Pipeline '{name}' not found[/red]")

    def _cmd_load(self, ctx: CommandContext, args: List[str]) -> None:
        """Load a YAML file."""
        if not args:
            ctx.print("[red]Usage: load <file> [as <name>][/red]")
            return

        filepath = args[0]
        name = None
        if 'as' in args:
            idx = args.index('as')
            if idx + 1 < len(args):
                name = args[idx + 1]

        try:
            path = pathlib.Path(filepath)
            if not path.exists():
                ctx.print(f"[red]File not found: {filepath}[/red]")
                return

            # Try to load as actual pipeline
            if Pipeline:
                from autopipe.core.loader import load_pipeline
                pipeline = load_pipeline(str(path))
                name = name or path.stem
                self.pipelines[name] = pipeline
                ctx.print(f"[green]✓[/green] Loaded pipeline: [cyan]{name}[/cyan] from {path.name}")
            else:
                # Fallback: just show the file content
                import yaml
                with open(path) as f:
                    data = yaml.safe_load(f)
                name = name or path.stem
                self.pipelines[name] = data
                ctx.print(f"[green]✓[/green] Loaded: [cyan]{name}[/cyan] (structure only)")

        except Exception as e:
            ctx.print(f"[red]Error loading file: {e}[/red]")

    def _cmd_save(self, ctx: CommandContext, args: List[str]) -> None:
        """Save a pipeline to file."""
        if not args:
            ctx.print("[red]Usage: save <name> [to <file>][/red]")
            return

        name = args[0]
        filepath = f"{name}.yaml"

        if 'to' in args:
            idx = args.index('to')
            if idx + 1 < len(args):
                filepath = args[idx + 1]

        if name not in self.pipelines:
            ctx.print(f"[red]Pipeline '{name}' not found[/red]")
            return

        try:
            import yaml
            pipeline = self.pipelines[name]

            # Convert to dict if necessary
            if hasattr(pipeline, 'dict'):
                data = pipeline.dict()
            elif hasattr(pipeline, '__dict__'):
                data = pipeline.__dict__
            else:
                data = pipeline

            with open(filepath, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)

            ctx.print(f"[green]✓[/green] Saved [cyan]{name}[/cyan] to {filepath}")
        except Exception as e:
            ctx.print(f"[red]Error saving file: {e}[/red]")

    def _cmd_files(self, ctx: CommandContext, args: List[str]) -> None:
        """List YAML files."""
        pattern = args[0] if args else "*.yaml"
        if not pattern.endswith('.yaml') and not pattern.endswith('.yml'):
            pattern += "*.yaml"

        files = list(pathlib.Path('.').glob(pattern))
        files.extend(pathlib.Path('.').glob(pattern.replace('.yaml', '.yml')))

        if not files:
            ctx.print(f"[dim]No files matching '{pattern}' found.[/dim]")
            return

        table = Table(title=f"YAML Files ({len(files)})", show_header=True)
        table.add_column("File", style="cyan")
        table.add_column("Size", style="yellow", justify="right")
        table.add_column("Modified", style="white")

        for f in sorted(files):
            size = f.stat().st_size
            mtime = f.stat().st_mtime
            from datetime import datetime
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

            size_str = self._format_bytes(size)
            table.add_row(f.name, size_str, mtime_str)

        ctx.print(table)

    def _cmd_python(self, ctx: CommandContext, args: List[str]) -> None:
        """Execute Python code."""
        if not args:
            ctx.print("[red]Usage: py <expression>[/red]")
            return

        code = ' '.join(args)
        namespace = {**self.variables}
        if Pipeline:
            namespace['Pipeline'] = Pipeline
            namespace['Step'] = Step

        try:
            # SECURITY FIX: Use restricted builtins to prevent code injection
            try:
                result = eval(code, {"__builtins__": _RESTRICTED_BUILTINS}, namespace)
                ctx.print(self._format_value(result))
                self.variables['_'] = result
            except SyntaxError:
                # Fall back to exec with restricted builtins
                exec(code, {"__builtins__": _RESTRICTED_BUILTINS}, namespace)
                self.variables.update({k: v for k, v in namespace.items() if k not in self.variables or v != self.variables.get(k)})
        except Exception as e:
            ctx.print(f"[red]{type(e).__name__}: {e}[/red]")

    def _cmd_print(self, ctx: CommandContext, args: List[str]) -> None:
        """Print a variable or expression."""
        if not args:
            ctx.print("[red]Usage: print <expression>[/red]")
            return

        expr = ' '.join(args)
        
        # Check for variable in pipelines or variables
        if expr.startswith('@') and expr[1:] in self.pipelines:
            ctx.print(pretty_repr(self.pipelines[expr[1:]]))
        elif expr.startswith('$') and expr[1:] in self.variables:
            ctx.print(pretty_repr(self.variables[expr[1:]]))
        else:
            self._cmd_python(ctx, ['str(' + expr + ')'])

    def _cmd_who(self, ctx: CommandContext, args: List[str]) -> None:
        """Show variable details."""
        pattern = args[0] if args else None
        found = False

        for name, value in self.variables.items():
            if pattern and pattern not in name:
                continue
            found = True
            ctx.print(f"\n[cyan]{name}[/cyan]: [yellow]{type(value).__name__}[/yellow]")
            try:
                size = self._get_size(value)
                ctx.print(f"  Size: {self._format_bytes(size) if size else 'N/A'}")
            except Exception:
                pass

            # Show repr
            repr_str = repr(value)
            if len(repr_str) > 200:
                repr_str = repr_str[:200] + "..."
            ctx.print(f"  Value: {repr_str}")

        for name, value in self.pipelines.items():
            if pattern and pattern not in name:
                continue
            found = True
            ctx.print(f"\n[cyan]@{name}[/cyan] (Pipeline): [yellow]{type(value).__name__}[/yellow]")

        if not found:
            ctx.print("[dim]No matching variables or pipelines found.[/dim]")

    def _cmd_whos(self, ctx: CommandContext, args: List[str]) -> None:
        """Show rich variable details."""
        if not self.variables:
            ctx.print("[dim]No variables defined.[/dim]")
            return

        table = Table(title="Variable Details", show_header=True)
        table.add_column("Variable", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Size", style="green")
        table.add_column("Content", style="white")

        for name, value in sorted(self.variables.items()):
            type_name = type(value).__name__
            try:
                size = self._get_size(value)
                size_str = self._format_bytes(size) if size else '-'
            except Exception:
                size_str = '-'

            content = self._format_preview(value, max_length=50)
            table.add_row(name, type_name, size_str, content)

        ctx.print(table)

    def _cmd_config(self, ctx: CommandContext, args: List[str]) -> None:
        """Show/edit configuration."""
        if not args:
            ctx.print(f"[bold]Configuration File:[/bold] {CONFIG_FILE}")
            ctx.print(f"[bold]History File:[/bold] {HISTORY_FILE}")
            ctx.print(f"\n[dim]Variables: {len(self.variables)}")
            ctx.print(f"[dim]Pipelines: {len(self.pipelines)}")
        elif len(args) == 1:
            key = args[0]
            if key in os.environ:
                ctx.print(f"{key}={os.environ[key]}")
            else:
                ctx.print(f"[red]Key '{key}' not set[/red]")
        else:
            key, val = args[0], ' '.join(args[1:])
            os.environ[key] = val
            ctx.print(f"[green]✓[/green] Set {key}={val}")

    def _cmd_history(self, ctx: CommandContext, args: List[str]) -> None:
        """Show command history."""
        n = 20
        if args:
            try:
                n = int(args[0])
            except ValueError:
                pass

        # Read from history file
        if HISTORY_FILE.exists():
            lines = HISTORY_FILE.read_text().strip().split('\n')
            lines = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
            lines = lines[-n:]

            for i, line in enumerate(lines, 1):
                ctx.print(f"[cyan]{i:3d}[/cyan]  {line}")
        else:
            ctx.print("[dim]No history available[/dim]")

    def _cmd_edit(self, ctx: CommandContext, args: List[str]) -> None:
        """Edit a file or config."""
        target = args[0] if args else "config"

        if target == "config":
            import subprocess
            editor = os.environ.get('EDITOR', 'vim')
            if CONFIG_FILE.exists():
                subprocess.call([editor, str(CONFIG_FILE)])
            else:
                ctx.print(f"[yellow]Config file doesn't exist yet: {CONFIG_FILE}[/yellow]")
        else:
            import subprocess
            editor = os.environ.get('EDITOR', 'vim')
            path = pathlib.Path(target)
            if path.exists():
                subprocess.call([editor, str(path)])
            else:
                ctx.print(f"[red]File not found: {target}[/red]")

    def _cmd_debug(self, ctx: CommandContext, args: List[str]) -> None:
        """Toggle debug mode."""
        if args and args[0].lower() in ('off', 'false', '0'):
            ctx.print("[dim]Debug mode: OFF[/dim]")
        else:
            ctx.print("[green]Debug mode: ON[/green]")
            ctx.print(f"Variables: {list(self.variables.keys())}")
            ctx.print(f"Pipelines: {list(self.pipelines.keys())}")

    def _cmd_test(self, ctx: CommandContext, args: List[str]) -> None:
        """Run a test/example pipeline."""
        ctx.print("[bold]Running test pipeline...[/bold]")
        
        try:
            from autopipe.core.steps import PrintStep
            pipeline = Pipeline("test_pipeline")
            pipeline.add_step(PrintStep("step1", message="Hello from AutoPipe!"))
            pipeline.add_step(PrintStep("step2", message="Step 2 executing", depends_on=["step1"]))
            
            result = pipeline.run()
            self.pipelines['test'] = pipeline
            self.variables['test_result'] = result
            ctx.print(f"[green]✓[/green] Test completed successfully!")
            ctx.print(f"[dim]Access pipeline with: @test[/dim]")
            ctx.print(f"[dim]Access result with: $test_result[/dim]")
        except Exception as e:
            ctx.print(f"[yellow]Test pipeline not available: {e}[/yellow]")
            ctx.print("[dim]This is expected if AutoPipe modules aren't fully installed.[/dim]")

    def _cmd_models(self, ctx: CommandContext, args: List[str]) -> None:
        """List or select Ollama models."""
        action = args[0] if args else "list"
        
        if action == "list":
            ctx.print("\n[bold]Ollama Models[/bold]\n")
            
            try:
                import requests
                import os
                base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").replace("/v1", "")
                response = requests.get(f"{base_url}/api/tags", timeout=5)
                
                if response.status_code == 200:
                    models_data = response.json().get("models", [])
                    current_model = os.getenv("OLLAMA_DEFAULT_MODEL", "Not set")
                    
                    if models_data:
                        table = Table(title="Available Ollama Models")
                        table.add_column("#", style="dim", justify="right")
                        table.add_column("Model Name", style="cyan")
                        table.add_column("Size", style="green")
                        table.add_column("Current", style="yellow", justify="center")
                        
                        for i, model in enumerate(models_data[:10], 1):
                            name = model.get("name", "unknown")
                            size = model.get("size", 0)
                            size_str = f"{size / 1e9:.1f} GB" if size else "N/A"
                            is_current = "★" if name == current_model else ""
                            table.add_row(str(i), name, size_str, is_current)
                        
                        ctx.print(table)
                        ctx.print(f"\n[dim]Current: {current_model}[/dim]")
                        ctx.print("\n[dim]Use 'use <kimi|glm|minimax>' or 'models use <name>'[/dim]")
                    else:
                        ctx.print("[yellow]No models found.[/yellow]")
                else:
                    ctx.print(f"[yellow]Could not connect to Ollama: HTTP {response.status_code}[/yellow]")
            except Exception as e:
                ctx.print(f"[red]Could not connect to Ollama: {e}[/red]")
                ctx.print("[dim]Ensure Ollama is running: ollama serve[/dim]")
                
        elif action in ("use", "select"):
            if len(args) < 2:
                ctx.print("[yellow]Usage: models use <kimi|glm|minimax|model_name>[/yellow]")
                return
            self._cmd_use_model(ctx, args[1:])
            
        elif action == "current":
            self._cmd_current_model(ctx, args[1:])
            
        else:
            ctx.print(f"[yellow]Unknown models action: {action}[/yellow]")
            ctx.print("[dim]Try: models list, models use <model>, models current[/dim]")

    def _cmd_use_model(self, ctx: CommandContext, args: List[str]) -> None:
        """Quick-select a model."""
        if not args:
            ctx.print("\n[bold]Quick-Select Cloud Models[/bold]\n")
            ctx.print("  [cyan]kimi[/cyan]      → [green]kimi-k2.5:cloud[/green]  (High-performance reasoning)")
            ctx.print("  [cyan]glm[/cyan]       → [green]glm-5.1:cloud[/green]    (General purpose chat)")
            ctx.print("  [cyan]minimax[/cyan]   → [green]minimax-m2.7:cloud[/green] (Multi-modal capable)\n")
            ctx.print("[dim]Usage: use <kimi|glm|minimax> or use <any_model_name>[/dim]")
            return
        
        alias = args[0].lower()
        alias_map = {
            "kimi": "kimi-k2.5:cloud",
            "k2.5": "kimi-k2.5:cloud",
            "k2_5": "kimi-k2.5:cloud",
            "glm": "glm-5.1:cloud",
            "minimax": "minimax-m2.7:cloud",
            "m2.7": "minimax-m2.7:cloud",
            "m2_7": "minimax-m2.7:cloud",
        }
        
        model_name = alias_map.get(alias, alias)
        
        # Set the environment variable
        os.environ["OLLAMA_DEFAULT_MODEL"] = model_name
        
        ctx.print(f"[green]✓[/green] Switched to model: [bold]{model_name}[/bold]")
        ctx.print(f"[dim]   This will be used for new LLM steps[/dim]")
        
        # Also update .env file if it exists
        env_file = pathlib.Path(".env")
        if env_file.exists():
            try:
                content = env_file.read_text()
                if "OLLAMA_DEFAULT_MODEL=" in content:
                    lines = content.split("\n")
                    new_lines = [f"OLLAMA_DEFAULT_MODEL={model_name}" if line.startswith("OLLAMA_DEFAULT_MODEL=") else line for line in lines]
                    env_file.write_text("\n".join(new_lines))
                    ctx.print(f"[dim]   Also updated .env file[/dim]")
            except Exception:
                pass

    def _cmd_current_model(self, ctx: CommandContext, args: List[str]) -> None:
        """Show current model configuration."""
        import os
        
        ctx.print("\n[bold]Current Model Configuration[/bold]\n")
        
        # Get current settings
        provider = os.getenv("DEFAULT_LLM_PROVIDER", "Not set")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "Not set")
        current_model = os.getenv("OLLAMA_DEFAULT_MODEL", "Not set")
        
        ctx.print(f"  [cyan]Default Provider:[/cyan]    {provider}")
        ctx.print(f"  [cyan]Ollama Base URL:[/cyan]     {ollama_url}")
        ctx.print(f"  [cyan]Current Model:[/cyan]       [green]{current_model}[/green]")
        
        # Show available models
        try:
            import requests
            base = ollama_url.replace("/v1", "") if ollama_url else "http://127.0.0.1:11434"
            response = requests.get(f"{base}/api/tags", timeout=3)
            if response.status_code == 200:
                models = [m.get("name") for m in response.json().get("models", [])]
                if models:
                    ctx.print(f"\n  [dim]Available models:[/dim]")
                    for m in models:
                        marker = "  ★ " if m == current_model else "    "
                        ctx.print(f"{marker}[dim]{m}[/dim]")
        except Exception:
            pass
        
        ctx.print("\n[dim]Change with: use <kimi|glm|minimax>[/dim]")

    # Utility methods

    def _format_value(self, value: Any) -> str:
        """Format a value for display."""
        if value is None:
            return "[dim]None[/dim]"

        type_name = type(value).__name__

        if isinstance(value, str):
            escaped = value.replace('[', r'\[').replace(']', r'\]')
            return f'"[green]{escaped}[/green]"'
        elif isinstance(value, (int, float, bool)):
            return f"[cyan]{value}[/cyan]"
        elif isinstance(value, (list, tuple)):
            items = [self._format_preview(item) for item in value[:5]]
            suffix = "..." if len(value) > 5 else ""
            brackets = "[]" if isinstance(value, list) else "()"
            sep = ", " if isinstance(value, (list, tuple)) else " "
            return f"[yellow]{brackets[0]}[/yellow]{sep.join(items)}{suffix}[yellow]{brackets[1]}[/yellow]"
        elif isinstance(value, dict):
            items = [f"{k!r}: {self._format_preview(v)}" for k, v in list(value.items())[:3]]
            suffix = "..." if len(value) > 3 else ""
            return f"[yellow]{{[/yellow]{', '.join(items)}{suffix}[yellow]}}[/yellow]"
        else:
            preview = repr(value)[:100]
            return f"[dim]({type_name})[/dim] {preview}"

    def _format_preview(self, value: Any, max_length: int = 50) -> str:
        """Create a short preview of a value."""
        try:
            s = str(value)
            if len(s) > max_length:
                s = s[:max_length - 3] + "..."
            return s
        except Exception:
            return "<?>"

    def _format_bytes(self, size: int) -> str:
        """Format byte size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _get_size(self, obj: Any) -> Optional[int]:
        """Get approximate size of an object."""
        import sys
        try:
            return sys.getsizeof(obj)
        except Exception:
            return None

    def _get_prompt(self) -> FormattedText:
        """Generate the REPL prompt."""
        # Count pipelines and variables
        pipe_count = len(self.pipelines)
        var_count = len(self.variables)

        parts: List[Tuple[str, str]] = []
        if pipe_count > 0:
            parts.append(('class:prompt', f"P{pipe_count}"))
        if var_count > 0:
            if parts:
                parts.append(('class:prompt', ":"))
            parts.append(('class:prompt', f"V{var_count}"))

        prefix = '[' + ''.join(p[1] for p in parts) + '] ' if parts else ''
        return FormattedText([
            ('class:prompt', prefix),
            ('class:prompt.dots', '>>> ')
        ])

    def run(self) -> None:
        """Run the REPL loop."""
        self._print_welcome()

        while True:
            try:
                # Get input with auto-complete and history
                text = self.session.prompt(
                    self._get_prompt(),
                    vi_mode=False,
                )

                # Skip empty lines
                text = text.strip()
                if not text or text.startswith('#'):
                    continue

                # Store in history
                self.command_history.append(text)

                # Parse and execute
                self._execute(text)

            except ExitREPL:
                break
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
            except EOFError:
                self.console.print("\n[dim]Goodbye! 👋[/dim]")
                break
            except Exception as e:
                self.console.print(f"[red]Unexpected error: {e}[/red]")

    def _execute(self, text: str) -> None:
        """Execute a command."""
        # Split into command and arguments
        parts = text.split()
        if not parts:
            return

        cmd_name = parts[0].lower()
        args = parts[1:]

        # Look up command
        cmd = self.registry.get(cmd_name)
        if cmd is None:
            # Try to evaluate as Python expression
            ctx = CommandContext(self)
            self._cmd_python(ctx, parts)
            return

        # Execute command
        ctx = CommandContext(self)
        try:
            cmd.handler(ctx, args)
        except ExitREPL:
            raise
        except Exception as e:
            self.console.print(f"[red]Error executing '{cmd_name}': {e}[/red]")

    def _print_welcome(self) -> None:
        """Print welcome message."""
        title = f"AutoPipe REPL v{__version__}"
        subtitle = "Interactive Pipeline Development Environment"

        self.console.print()
        self.console.print(f"[bold cyan]{'═' * WELCOME_WIDTH}[/bold cyan]")
        self.console.print(f"[bold cyan]╭{'─' * (WELCOME_WIDTH - 2)}╮[/bold cyan]")

        # Center the title
        title_pad = (WELCOME_WIDTH - len(title) - 4) // 2
        self.console.print(
            f"[bold cyan]│[/bold cyan]"
            f"[bold white]{' ' * title_pad}[/bold white]"
            f"[bold green]{title}[/bold green]"
            f"[bold white]{' ' * (WELCOME_WIDTH - len(title) - 4 - title_pad)}[/bold white]"
            f"[bold cyan]│[/bold cyan]"
        )

        subtitle_pad = (WELCOME_WIDTH - len(subtitle) - 4) // 2
        self.console.print(
            f"[bold cyan]│[/bold cyan]"
            f"[dim]{' ' * subtitle_pad}[/dim]"
            f"[dim]{subtitle}[/dim]"
            f"[dim]{' ' * (WELCOME_WIDTH - len(subtitle) - 4 - subtitle_pad)}[/dim]"
            f"[bold cyan]│[/bold cyan]"
        )
        self.console.print(f"[bold cyan]╰{'─' * (WELCOME_WIDTH - 2)}╯[/bold cyan]")
        self.console.print(f"[bold cyan]{'═' * WELCOME_WIDTH}[/bold cyan]")

        # Show current model if Ollama is the provider
        import os
        provider = os.getenv("DEFAULT_LLM_PROVIDER", "openrouter")
        if provider == "ollama":
            model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.1")
            self.console.print()
            self.console.print(f"[dim]Provider:[/dim] [cyan]{provider}[/cyan]  [dim]Model:[/dim] [green]{model}[/green]")

        self.console.print()
        self.console.print("[white]Quick Start:[/white]")
        self.console.print("  [cyan]new[/cyan] <name>           - Create a new pipeline")
        self.console.print("  [cyan]load[/cyan] <file>          - Load a YAML pipeline")
        self.console.print("  [cyan]run[/cyan] <name>           - Run a pipeline")
        self.console.print("  [cyan]models[/cyan]               - List Ollama models")
        self.console.print("  [cyan]use[/cyan] <kimi|glm|minimax> - Switch model")
        self.console.print("  [cyan]help[/cyan]                 - Show all commands")
        self.console.print()
        self.console.print("[dim]Type 'help' for full command list | Tab for completion | Up arrow for history[/dim]")
        self.console.print()


class AutoPipeAutoSuggest(AutoSuggest):
    """Custom auto-suggest for AutoPipe commands."""

    def get_suggestion(self, buffer: Document, document: Document) -> Optional[Suggestion]:
        text = document.text_before_cursor
        if not text:
            return None

        # Check for common patterns
        if text.startswith('pip'):
            return Suggestion('elines')
        elif text.startswith('let '):
            return Suggestion(' name = value')
        elif text.startswith('new '):
            return Suggestion(' name')
        elif text.startswith('run '):
            return Suggestion(' <name>')

        return None


def main() -> int:
    """Entry point for the REPL CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog='autopipe-repl',
        description='AutoPipe Interactive REPL'
    )
    parser.add_argument(
        '-c', '--command',
        help='Execute a command and exit'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Enter interactive mode after executing commands'
    )

    args = parser.parse_args()

    repl = AutoPipeREPL()

    if args.command:
        repl._execute(args.command)
        if not args.interactive:
            return 0

    try:
        repl.run()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
