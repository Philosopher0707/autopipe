"""Run-path file production recorder (Phase B artifact registration).

Producers call ``record_produced_file`` as they write; the dashboard runner
drains the thread-local list after execution and registers Artifact rows.
The engine never touches this module (execution-only boundary).
"""

import os
import threading

from autopipe.core.artifacts import drain_produced_files, record_produced_file


class TestRecorder:
    def test_record_then_drain_roundtrip(self):
        record_produced_file("a.png")
        record_produced_file("/tmp/b.png")
        assert drain_produced_files() == ["a.png", "/tmp/b.png"]
        assert drain_produced_files() == []

    def test_drain_empty_is_empty_not_error(self):
        assert drain_produced_files() == []

    def test_record_without_drain_accumulates(self):
        record_produced_file("x")
        record_produced_file("y")
        assert drain_produced_files() == ["x", "y"]

    def test_drain_is_thread_local(self):
        """One worker thread's files must not leak into another context."""
        seen = {}

        def worker():
            record_produced_file("worker.png")
            seen["worker"] = drain_produced_files()

        record_produced_file("main.png")
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert seen["worker"] == ["worker.png"]
        assert drain_produced_files() == ["main.png"]


class TestChartGeneratorChoke:
    def test_save_fig_writes_and_records(self, tmp_path, monkeypatch):
        import matplotlib

        matplotlib.use("Agg")
        from autopipe.visualization import ChartGenerator

        drain_produced_files()
        chart = ChartGenerator(output_dir=str(tmp_path))
        chart.plot_metrics({"loss": [1.0, 0.5]}, title="T")

        recorded = drain_produced_files()
        assert len(recorded) == 1
        path = recorded[0]
        assert os.path.isfile(path)
        assert path.endswith(".png")
        assert str(tmp_path) in os.path.abspath(path)

    def test_save_fig_returns_path(self, tmp_path):
        import matplotlib

        matplotlib.use("Agg")
        from autopipe.visualization import ChartGenerator

        chart = ChartGenerator(output_dir=str(tmp_path))
        path = chart._save_fig("probe.png")
        assert os.path.isfile(path)
        drain_produced_files()
