"""Phase C: dataset input identity recorded by loaders (run path).

Loaders call ``record_dataset_input`` after a successful read; the runner
drains the thread-local list and persists ``provenance["datasets"]``.
"""

import hashlib
import threading

from autopipe.core.artifacts import (
    drain_dataset_inputs,
    drain_produced_files,
    record_dataset_input,
    sha256_file,
)


class TestDatasetRecorder:
    def test_record_then_drain_roundtrip(self):
        record_dataset_input({"kind": "file", "source": "a.csv"})
        record_dataset_input({"kind": "builtin", "name": "iris"})
        assert drain_dataset_inputs() == [
            {"kind": "file", "source": "a.csv"},
            {"kind": "builtin", "name": "iris"},
        ]
        assert drain_dataset_inputs() == []

    def test_drain_empty(self):
        assert drain_dataset_inputs() == []

    def test_thread_local(self):
        seen = {}

        def worker():
            record_dataset_input({"kind": "builtin", "name": "w"})
            seen["w"] = drain_dataset_inputs()

        record_dataset_input({"kind": "builtin", "name": "main"})
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert seen["w"] == [{"kind": "builtin", "name": "w"}]
        assert drain_dataset_inputs() == [{"kind": "builtin", "name": "main"}]

    def test_separate_from_produced_files(self):
        record_dataset_input({"kind": "builtin", "name": "x"})
        assert drain_produced_files() == []
        drain_dataset_inputs()


class TestSha256File:
    def test_matches_hashlib(self, tmp_path):
        p = tmp_path / "d.csv"
        blob = b"a,b\n1,2\n"
        p.write_bytes(blob)
        assert sha256_file(str(p)) == hashlib.sha256(blob).hexdigest()

    def test_fail_closed_missing(self, tmp_path):
        import pytest

        with pytest.raises(OSError):
            sha256_file(str(tmp_path / "nope.csv"))


class TestDataLoaderRecordsFile:
    def test_csv_load_records_source_and_hash(self, tmp_path):

        from autopipe.steps.data import DataLoaderStep

        drain_dataset_inputs()
        p = tmp_path / "in.csv"
        blob = b"col\n1\n2\n"
        p.write_bytes(blob)

        step = DataLoaderStep(name="dl", source=str(p), format="csv")
        df = step.run()
        assert len(df) == 2

        entries = drain_dataset_inputs()
        assert len(entries) == 1
        e = entries[0]
        assert e["kind"] == "file"
        assert e["source"] == str(p.resolve())
        assert e["format"] == "csv"
        assert e["sha256"] == hashlib.sha256(blob).hexdigest()

    def test_sql_load_never_records_connection(self, monkeypatch):
        import pandas as pd
        import pytest

        # sqlalchemy backs an optional path (DataLoaderStep format="sql") and is
        # not in [project.dependencies]; skip rather than fail on a clean install.
        sqlalchemy = pytest.importorskip("sqlalchemy")

        from autopipe.steps.data import DataLoaderStep

        secret = "postgres://user:SECRET-PW@internal:5432/db"
        monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_a, **_k: object())
        monkeypatch.setattr(pd, "read_sql", lambda *_a, **_k: pd.DataFrame({"x": [1]}))

        drain_dataset_inputs()
        step = DataLoaderStep(name="dl", format="sql", sql_connection=secret, sql_query="select 1")
        step.run()

        entries = drain_dataset_inputs()
        assert len(entries) == 1
        assert "SECRET-PW" not in repr(entries)
        assert "connection" not in entries[0]
        assert entries[0]["kind"] == "sql"
        assert entries[0]["sha256"] == "unavailable"

    def test_missing_file_raises_before_recording(self, tmp_path):
        import contextlib

        from autopipe.steps.data import DataLoaderStep

        drain_dataset_inputs()
        step = DataLoaderStep(name="dl", source=str(tmp_path / "ghost.csv"), format="csv")
        with contextlib.suppress(OSError):
            step.run()
        assert drain_dataset_inputs() == []


class TestBuiltinLoaderRecordsName:
    def test_iris_records_builtin_entry(self):
        from autopipe.core.steps import DataLoaderStep

        drain_dataset_inputs()
        step = DataLoaderStep(name="sample", dataset="iris")
        df = step.run()
        assert len(df) > 0

        entries = drain_dataset_inputs()
        assert entries == [{"kind": "builtin", "name": "iris", "sha256": "unavailable"}]

    def test_unknown_dataset_records_nothing(self):
        import contextlib

        from autopipe.core.steps import DataLoaderStep

        drain_dataset_inputs()
        with contextlib.suppress(ValueError):
            DataLoaderStep(name="sample", dataset="nope").run()
        assert drain_dataset_inputs() == []
