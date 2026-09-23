"""Artifact integrity: the canonical file-byte SHA256 producer (PROVENANCE_MODEL).

Contract under test:

* ``sha256_file`` — single canonical hashing definition for file artifacts:
  exact bytes, no decoding/normalization, deterministic lowercase hex.
* ``Artifact``'s ``validates("file_path")`` hook — the single producer that
  writes ``Artifact.sha256``; hash follows path reassignment, row metadata
  never influences it, unreadable files fail closed (no placeholder hash).
* ChartArtifact's existing data hook — non-regression lives in
  ``test_charts.py`` (hash covers ``data``, not title).
"""

import hashlib
from pathlib import Path

import pytest
from app.db.models import Artifact, sha256_file
from sqlalchemy import func, select

# Known SHA-256 of the empty message (FIPS 180-4 test vector).
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _write(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return str(path)


class TestSha256File:
    def test_deterministic_across_calls_and_paths(self, tmp_path):
        a = _write(tmp_path / "a.bin", b"same content")
        b = _write(tmp_path / "b.bin", b"same content")
        assert sha256_file(a) == sha256_file(a), "same bytes must hash the same"
        assert sha256_file(a) == sha256_file(b), "identity is content, not path"

    def test_sensitive_to_single_byte(self, tmp_path):
        a = _write(tmp_path / "a.bin", b"payload-v1")
        b = _write(tmp_path / "b.bin", b"payload-v2")
        assert sha256_file(a) != sha256_file(b)

    def test_empty_file_is_the_standard_empty_digest(self, tmp_path):
        path = _write(tmp_path / "empty.bin", b"")
        assert sha256_file(path) == EMPTY_SHA256

    def test_binary_bytes_all_values_roundtrip(self, tmp_path):
        blob = bytes(range(256)) * 3
        path = _write(tmp_path / "binary.bin", blob)
        assert sha256_file(path) == hashlib.sha256(blob).hexdigest()

    def test_unicode_and_newline_differences_change_the_hash(self, tmp_path):
        nfc = _write(tmp_path / "nfc.txt", "café\n".encode())  # U+00E9
        nfd = _write(tmp_path / "nfd.txt", b"cafe\xcc\x81\n")  # e + U+0301 raw bytes
        crlf = _write(tmp_path / "crlf.txt", "café\r\n".encode())
        hashes = {sha256_file(nfc), sha256_file(nfd), sha256_file(crlf)}
        assert len(hashes) == 3, "byte-level identity must see encoding/newline differences"
        assert sha256_file(nfc) == hashlib.sha256("café\n".encode()).hexdigest()

    def test_large_payload_streams_to_the_one_shot_digest(self, tmp_path):
        blob = bytes(range(256)) * (5 * 1024 * 1024 // 256)  # 5 MiB
        path = _write(tmp_path / "large.bin", blob)
        assert sha256_file(path) == hashlib.sha256(blob).hexdigest()

    def test_missing_file_fails_closed(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            sha256_file(str(tmp_path / "nope.bin"))

    def test_directory_fails_closed(self, tmp_path):
        (tmp_path / "adir").mkdir()
        with pytest.raises(IsADirectoryError):
            sha256_file(str(tmp_path / "adir"))


class TestArtifactHashLifecycle:
    async def test_insert_persists_the_expected_hash(self, db_session, tmp_path):
        path = _write(tmp_path / "model.bin", b"artifact-bytes")
        expected = hashlib.sha256(b"artifact-bytes").hexdigest()

        row = Artifact(name="m", artifact_type="model", file_path=path, file_size=14)
        db_session.add(row)
        await db_session.commit()

        assert row.sha256 == expected, "insert must carry the file's content address"
        assert row.sha256 is not None and len(row.sha256) == 64

    async def test_roundtrip_read_keeps_the_hash_consistent(self, db_session, tmp_path):
        path = _write(tmp_path / "data.bin", b"round-trip")
        row = Artifact(name="d", artifact_type="data", file_path=path)
        db_session.add(row)
        await db_session.commit()
        row_id = row.id

        db_session.expire_all()
        fresh = await db_session.get(Artifact, row_id)
        assert fresh is not None
        assert fresh.sha256 == sha256_file(path), "persisted hash must match the file on disk"

    async def test_reassigning_file_path_rehashes(self, db_session, tmp_path):
        first = _write(tmp_path / "v1.bin", b"content-v1")
        second = _write(tmp_path / "v2.bin", b"content-v2")
        row = Artifact(name="a", artifact_type="data", file_path=first)
        db_session.add(row)
        await db_session.commit()
        hash_v1 = row.sha256

        row.file_path = second
        await db_session.commit()

        assert row.sha256 == sha256_file(second)
        assert row.sha256 != hash_v1, "hash must follow the bound content, not go stale"

    async def test_row_metadata_never_changes_the_hash(self, db_session, tmp_path):
        path = _write(tmp_path / "meta.bin", b"stable-content")
        row = Artifact(name="original", artifact_type="data", file_path=path)
        db_session.add(row)
        await db_session.commit()
        bound = row.sha256

        row.name = "renamed"
        row.artifact_type = "model"
        row.meta_data = {"note": "mutated after registration"}
        await db_session.commit()

        assert row.sha256 == bound, "identity is content, not row metadata"

    def test_missing_file_fails_at_construction(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Artifact(name="ghost", artifact_type="model", file_path=str(tmp_path / "gone.bin"))

    async def test_failed_registration_persists_nothing(self, db_session, tmp_path):
        with pytest.raises(FileNotFoundError):
            Artifact(name="ghost", artifact_type="model", file_path=str(tmp_path / "gone.bin"))
        count = await db_session.scalar(select(func.count()).select_from(Artifact))
        assert int(count or 0) == 0, "a failed registration must leave no row behind"

    async def test_post_persistence_file_mutation_is_detectable(self, db_session, tmp_path):
        """The hash is taken at registration; later byte changes diverge from it."""
        path = _write(tmp_path / "mutable.bin", b"original bytes")
        row = Artifact(name="mut", artifact_type="data", file_path=path)
        db_session.add(row)
        await db_session.commit()
        registered = row.sha256

        Path(path).write_bytes(b"tampered bytes")

        assert registered == hashlib.sha256(b"original bytes").hexdigest()
        assert sha256_file(path) != registered, (
            "integrity check = recompute and compare; divergence must be detectable"
        )

    async def test_empty_file_artifact_gets_the_empty_digest(self, db_session, tmp_path):
        path = _write(tmp_path / "empty.bin", b"")
        row = Artifact(name="e", artifact_type="data", file_path=path)
        db_session.add(row)
        await db_session.commit()
        assert row.sha256 == EMPTY_SHA256
