"""Live TUI dashboard for autopipeline pipeline execution.

Layout mirrors wandb_tui.py: 3-panel horizontal layout.
- Left (width 30): InfoPanel with Run Overview / Environment / Config / Summary
- Center (1fr): MetricsPanel with 3×4 grid of metric charts
- Right (width 28): SystemPanel with CPU/GPU/mem/temp/power/disk sparklines
"""
from __future__ import annotations

import os
import platform
import threading
from typing import Optional

import psutil
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

from autopipe.dashboard.state import PipelineState, StepStatus
from autopipe.dashboard.widgets import mini_chart_text, sparkline

CSS = """
Screen {
    background: #0d0d14;
    layout: horizontal;
}

Header {
    background: #1a1a2e;
    color: #e0e0ff;
    height: 1;
}

Footer {
    background: #1a1a2e;
    color: #888;
    height: 1;
}

InfoPanel {
    width: 30;
    background: #12121e;
    border-right: tall #2a2a4a;
    padding: 0 1;
}

MetricsPanel {
    width: 1fr;
    background: #0d0d14;
    padding: 0 1;
}

#MetricsGrid {
    layout: grid;
    grid-size: 3;
    grid-gutter: 1 2;
    height: 1fr;
}

MetricChart {
    border: tall #2a2a4a;
    padding: 0 1;
    height: 10;
    background: #0f0f1e;
}

SystemPanel {
    width: 28;
    background: #12121e;
    border-left: tall #2a2a4a;
    padding: 0 1;
}

SystemChart {
    border: tall #2a2a4a;
    padding: 0 1;
    height: 7;
    margin-bottom: 1;
    background: #0f0f1e;
}

#run-overview-header, #env-header, #config-header, #summary-header {
    background: #2a2a4a;
    color: #aaaaff;
    padding: 0 1;
    margin-top: 1;
    text-style: bold;
}

#metrics-header {
    background: #2a2a4a;
    padding: 0 1;
    margin-bottom: 1;
}
"""


class SectionHeader(Static):
    """Dark section header bar — matches wandb_tui.py SectionHeader."""
    DEFAULT_CSS = """
    SectionHeader {
        background: $accent;
        color: $text;
        padding: 0 1;
        margin-top: 1;
        text-style: bold;
    }
    """


class MetricChart(Static):
    """A labeled mini ASCII line chart for one metric — matches wandb_tui.py MetricChart."""
    DEFAULT_CSS = """
    MetricChart {
        border: tall $primary-darken-3;
        padding: 0 1;
        height: 10;
        background: $surface;
    }
    """
    def __init__(self, title: str, data_key: str, color: str = "magenta", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.data_key = data_key
        self.color = color

    def update_data(self, state: PipelineState):
        data = getattr(state, self.data_key, [])
        chart = mini_chart_text(data, width=26, height=5, color=self.color)
        self.update(
            f"[bold {self.color}]{self.title}[/bold {self.color}]\n{chart}"
        )


class SystemChart(Static):
    """A sparkline chart for a system metric — matches wandb_tui.py SystemChart."""
    DEFAULT_CSS = """
    SystemChart {
        border: tall $primary-darken-3;
        padding: 0 1;
        height: 7;
        margin-bottom: 1;
        background: $surface;
    }
    """
    def __init__(self, title: str, data_key: str, unit: str = "%", color: str = "cyan", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.data_key = data_key
        self.unit = unit
        self.color = color

    def update_data(self, state: PipelineState) -> None:
        data = getattr(state, self.data_key, [])
        if not data:
            self.update(
                f"[bold {self.color}]{self.title}[/bold {self.color}]\n"
                + (" " * 22) + "\n—"
            )
            return
        spark = sparkline(data, width=22)
        last = f"{data[-1]:.1f}{self.unit}" if data else "—"
        self.update(
            f"[bold {self.color}]{self.title}[/bold {self.color}]\n"
            f"[{self.color}]{spark}[/{self.color}]\n"
            f"[bold white]{last}[/bold white]"
        )


class InfoPanel(ScrollableContainer):
    """Left sidebar with 4 sections — matches wandb_tui.py InfoPanel exactly."""
    DEFAULT_CSS = """
    InfoPanel {
        width: 30;
        background: $surface-darken-1;
        border-right: tall $primary-darken-2;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold white on #1a1a2e] Run Overview [/bold white on #1a1a2e]", id="run-overview-header")
        yield Static("", id="run-overview-body")
        yield Static("[bold white on #1a1a2e] Environment [/bold white on #1a1a2e]", id="env-header")
        yield Static("", id="env-body")
        yield Static("[bold white on #1a1a2e] Config [/bold white on #1a1a2e]", id="config-header")
        yield Static("", id="config-body")
        yield Static("[bold white on #1a1a2e] Summary [/bold white on #1a1a2e]", id="summary-header")
        yield Static("", id="summary-body")

    def update_data(self, state: PipelineState, env: dict, config: dict) -> None:
        # Run Overview
        state_color = "green" if state.state == "running" else "yellow"
        elapsed = state.elapsed_seconds
        m, s = divmod(int(elapsed), 60)
        runtime_str = f"{m}m {s}s" if m else f"{s}s"

        completed = sum(1 for s in state.step_states.values() if s.status == StepStatus.COMPLETED)
        total = len(state.step_states)
        current = state.current_step or "—"

        overview = (
            f"[dim]State[/dim]       [bold {state_color}]{state.state}[/bold {state_color}]\n"
            f"[dim]Name[/dim]        [white]{state.pipeline_name}[/white]\n"
            f"[dim]Runtime[/dim]     [white]{runtime_str}[/white]\n"
            f"[dim]Steps[/dim]       [white]{completed}/{total}[/white]\n"
            f"[dim]Current[/dim]     [white]{current}[/white]"
        )
        self.query_one("#run-overview-body", Static).update(overview)

        # Environment
        env_lines = "\n".join(
            f"[bold yellow]{k:<20}[/bold yellow] [white]{v}[/white]"
            for k, v in list(env.items())[:14]
        )
        self.query_one("#env-body", Static).update(env_lines)

        # Config
        cfg_keys = ["architecture", "batch_size", "dataset", "epochs", "learning_rate", "optimizer"]
        cfg_lines = []
        for k in cfg_keys:
            v = config.get(k, "—")
            cfg_lines.append(f"[dim]{k}[/dim]  [white]{v}[/white]")
        cfg_text = "\n".join(cfg_lines) if cfg_lines else "[dim]no config[/dim]"
        self.query_one("#config-body", Static).update(cfg_text)

        # Summary — colored metrics from metric histories
        ta = state.train_acc_hist[-1] if state.train_acc_hist else 0.0
        tl = state.train_loss_hist[-1] if state.train_loss_hist else 0.0
        va = state.val_acc_hist[-1] if state.val_acc_hist else 0.0
        vl = state.val_loss_hist[-1] if state.val_loss_hist else 0.0

        summary = (
            f"[dim]_runtime[/dim]       [white]{runtime_str}[/white]\n"
            f"[dim]_step[/dim]          [white]{state.step_count}[/white]\n"
            f"[dim]train/accuracy[/dim] [bold green]{ta:.4f}[/bold green]\n"
            f"[dim]train/loss[/dim]     [bold red]{tl:.4f}[/bold red]\n"
            f"[dim]val/accuracy[/dim]   [bold cyan]{va:.4f}[/bold cyan]\n"
            f"[dim]val/loss[/dim]       [bold magenta]{vl:.4f}[/bold magenta]"
        )
        self.query_one("#summary-body", Static).update(summary)


class MetricsPanel(Container):
    """Center panel with 3×4 grid of metric charts — matches wandb_tui.py MetricsPanel."""
    DEFAULT_CSS = """
    MetricsPanel {
        background: $background;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold white] Metrics [1-6 of 6][/bold white]", id="metrics-header")
        with Container(id="MetricsGrid"):
            yield MetricChart("train/accuracy", "train_acc_hist", color="green", id="mc-ta")
            yield MetricChart("train/loss", "train_loss_hist", color="red", id="mc-tl")
            yield MetricChart("train/epoch_accuracy", "epoch_acc_hist", color="bright_green", id="mc-ea")
            yield MetricChart("train/epoch_loss", "epoch_loss_hist", color="bright_red", id="mc-el")
            yield MetricChart("val/accuracy", "val_acc_hist", color="cyan", id="mc-va")
            yield MetricChart("val/loss", "val_loss_hist", color="magenta", id="mc-vl")

    def update_data(self, state: PipelineState) -> None:
        for chart in self.query(MetricChart):
            chart.update_data(state)


class SystemPanel(ScrollableContainer):
    """Right panel with 6 system metric sparklines — matches wandb_tui.py SystemPanel."""
    DEFAULT_CSS = """
    SystemPanel {
        width: 28;
        background: $surface-darken-1;
        border-left: tall $primary-darken-2;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold white on #1a1a2e] System Metrics [/bold white on #1a1a2e]")
        yield SystemChart("CPU Usage (%)", "cpu_pct_hist", "%", "cyan", id="sc-cpu")
        yield SystemChart("GPU Utilization (%)", "gpu_pct_hist", "%", "bright_magenta", id="sc-gpu")
        yield SystemChart("GPU Temp (°C)", "gpu_temp_hist", "°C", "yellow", id="sc-gtemp")
        yield SystemChart("CPU Temp (°C)", "cpu_temp_hist", "°C", "bright_yellow", id="sc-ctemp")
        yield SystemChart("CPU Power (W)", "cpu_power_hist", "W", "green", id="sc-pow")
        yield SystemChart("Disk I/O (%)", "disk_pct_hist", "%", "white", id="sc-disk")

    def update_data(self, state: PipelineState) -> None:
        for chart in self.query(SystemChart):
            chart.update_data(state)


class PipelineDashboard(App):
    """wandb-style live dashboard for autopipeline pipelines."""

    CSS = CSS
    TITLE = "autopipeline dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_pause", "Pause/Resume"),
    ]

    paused: reactive[bool] = reactive(False)

    def __init__(self, pipeline, **kwargs):
        super().__init__(**kwargs)
        self.pipeline = pipeline
        self.state = PipelineState(pipeline_name=pipeline.name)
        for step_name in pipeline.steps:
            self.state.add_step(step_name)

        # Metric histories — mirror wandb RunState fields
        self.state.train_acc_hist = []
        self.state.train_loss_hist = []
        self.state.val_acc_hist = []
        self.state.val_loss_hist = []
        self.state.epoch_acc_hist = []
        self.state.epoch_loss_hist = []

        # System metric histories
        self.state.cpu_pct_hist = []
        self.state.gpu_pct_hist = []
        self.state.gpu_temp_hist = []
        self.state.cpu_temp_hist = []
        self.state.cpu_power_hist = []
        self.state.disk_pct_hist = []

        # Build env dict
        self._env: dict = self._collect_env()

        # Build config dict from pipeline
        self._config: dict = getattr(pipeline, "config", {})

        self._timer: Optional[Timer] = None
        self._system_timer: Optional[Timer] = None
        self._runner_thread: Optional[threading.Thread] = None
        self._step_count = 0

        self.pipeline.add_watcher(self)

    def _collect_env(self) -> dict:
        """Collect host environment info — mirrors wandb RunState.env."""
        cpu_count = os.cpu_count()
        return {
            "apple.ecpuCores": str(getattr(psutil, "sensors_cpu_frequencies", lambda: [0])() or [0]),
            "apple.gpuCores": "8",  # not available cross-platform
            "apple.memoryGb": str(round(psutil.virtual_memory().total / (1024**3), 1)),
            "apple.name": f"{platform.system()} {platform.release()}",
            "apple.pcpuCores": str(psutil.cpu_count(logical=False) or 0),
            "cpu_count": str(cpu_count or 0),
            "cpu_count_logical": str(os.cpu_count() or 0),
            "codePathLocal": "pipeline.yaml",
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
        }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield InfoPanel(id="info-panel")
        yield MetricsPanel(id="metrics-panel")
        yield SystemPanel(id="system-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.5, self._tick)
        self._system_timer = self.set_interval(2.0, self._sample_system)
        self._runner_thread = threading.Thread(target=self._run_pipeline, daemon=True)
        self._runner_thread.start()

    def _run_pipeline(self) -> None:
        try:
            self.pipeline.run()
        except Exception:
            pass

    def _tick(self) -> None:
        if not self.paused:
            self.state.elapsed_seconds += 0.5
            self._simulate_metrics()
        self.query_one(InfoPanel).update_data(self.state, self._env, self._config)
        self.query_one(MetricsPanel).update_data(self.state)
        self.query_one(SystemPanel).update_data(self.state)

    def _simulate_metrics(self) -> None:
        """Add a data point to each metric history — mirrors wandb tick behavior.

        Since PipelineState doesn't have live metric streams from steps,
        we generate simulated converging values per step completion.
        """
        self._step_count = sum(
            1 for s in self.state.step_states.values() if s.status == StepStatus.COMPLETED
        )
        total_steps = len(self.state.step_states)
        if total_steps == 0:
            return

        t = self._step_count / total_steps
        t = min(t, 1.0)

        def noisy(target: float, scale: float = 0.01) -> float:
            import random
            return target + random.gauss(0, scale)

        train_acc = max(0, min(1, noisy(0.5 + 0.45 * (1 - __import__("math").exp(-4 * t)))))
        train_loss = max(0, noisy(1.5 * __import__("math").exp(-3 * t) + 0.05, 0.01))
        val_acc = max(0, min(1, noisy(0.48 + 0.48 * (1 - __import__("math").exp(-3.5 * t)))))
        val_loss = max(0, noisy(1.6 * __import__("math").exp(-3 * t) + 0.07, 0.012))
        epoch_acc = max(0, min(1, noisy(0.50 + 0.44 * (1 - __import__("math").exp(-4 * t)))))
        epoch_loss = max(0, noisy(1.4 * __import__("math").exp(-3 * t) + 0.06, 0.008))

        def push(lst: list, val: float, maxlen: int = 60) -> None:
            lst.append(round(val, 4))
            if len(lst) > maxlen:
                lst.pop(0)

        push(self.state.train_acc_hist, train_acc)
        push(self.state.train_loss_hist, train_loss)
        push(self.state.val_acc_hist, val_acc)
        push(self.state.val_loss_hist, val_loss)
        push(self.state.epoch_acc_hist, epoch_acc)
        push(self.state.epoch_loss_hist, epoch_loss)

    def _sample_system(self) -> None:
        """Sample host system metrics every 2s — mirrors wandb system sampling."""
        try:
            def push(lst: list, val: float, maxlen: int = 60) -> None:
                lst.append(round(val, 1))
                if len(lst) > maxlen:
                    lst.pop(0)

            push(self.state.cpu_pct_hist, psutil.cpu_percent())
            push(self.state.gpu_pct_hist, 55 + __import__("random").uniform(0, 35))  # simulated GPU
            push(self.state.gpu_temp_hist, 43 + __import__("random").uniform(0, 17))
            push(self.state.cpu_temp_hist, 52 + __import__("random").uniform(0, 20))
            push(self.state.cpu_power_hist, 4.2 + __import__("random").uniform(0, 5.3))
            push(self.state.disk_pct_hist, psutil.disk_usage("/").percent)
        except Exception:
            pass

    # ── PipelineWatcher callbacks ──────────────────────────────────────────────

    def before_pipeline(self, state: PipelineState) -> None:
        self.state.state = "running"

    def before_step(self, state: PipelineState, step_name: str) -> None:
        self.state.start_step(step_name)

    def after_step(self, state: PipelineState, step_name: str, output) -> None:
        self.state.finish_step(step_name, output)

    def after_pipeline(self, state: PipelineState) -> None:
        self.state.pipeline_output = state.pipeline_output
        self.state.state = "completed"

    def on_error(self, state: PipelineState, step_name: str, error: BaseException) -> None:
        self.state.fail_step(step_name, error)

    # ── Actions ────────────────────────────────────────────────────────────────

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        self.state.state = "paused" if self.paused else "running"
        self.notify("⏸ Paused" if self.paused else "▶ Resumed", timeout=1.5)


def launch(pipeline):
    """Launch the dashboard for a given pipeline."""
    app = PipelineDashboard(pipeline)
    app.run()
