"""Track B: runtime dependency identity — full package set + environment_hash."""

import json
import re

from app.core.provenance import (
    _canonical_package_records,
    _environment_fingerprint,
    _environment_hash,
    build_provenance,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_environment_fingerprint_includes_all_relevant_packages():
    fp = _environment_fingerprint()
    assert "fastapi" in fp["packages"]
    assert "pydantic" in fp["packages"]
    assert len(fp["packages"]) > 5, "full installed set, not the old fixed five"
    assert HEX64.match(fp["environment_hash"]), "64-char sha256 hex"


def test_environment_hash_is_deterministic():
    assert (
        _environment_fingerprint()["environment_hash"]
        == _environment_fingerprint()["environment_hash"]
    )


def test_environment_hash_discriminates_version_change():
    assert _environment_hash([("pkg-a", "1.0.0")], "3.12.0") != _environment_hash(
        [("pkg-a", "1.0.1")], "3.12.0"
    )


def test_environment_hash_is_order_independent():
    pairs = [("a", "1.0"), ("b", "2.0"), ("c", "3.0")]
    assert _environment_hash(pairs, "3.12.0") == _environment_hash(list(reversed(pairs)), "3.12.0")


def test_environment_hash_discriminates_python_change():
    pairs = [("pkg-a", "1.0.0")]
    assert _environment_hash(pairs, "3.12.0") != _environment_hash(pairs, "3.13.0")


def test_canonical_package_records_normalizes_sorts_and_dedupes():
    raw = [
        ("Zope.Interface", "5.4.0"),
        ("zope_interface", "5.4.0"),
        ("B_Pkg", "2.0"),
        ("a-pkg", "1.0"),
    ]
    records = _canonical_package_records(raw)
    assert records == [("a-pkg", "1.0"), ("b-pkg", "2.0"), ("zope-interface", "5.4.0")]
    # same name, two versions: both pairs kept, greater version last
    dup = _canonical_package_records([("pkg", "1.0"), ("pkg", "2.0")])
    assert dup == [("pkg", "1.0"), ("pkg", "2.0")]


def test_build_provenance_carries_environment_hash():
    env = build_provenance("test", {})["environment"]
    assert HEX64.match(env["environment_hash"])
    assert env["python"] and env["platform"] and isinstance(env["packages"], dict)


def test_environment_fingerprint_never_contains_secret_shapes(monkeypatch):
    monkeypatch.setenv("SOME_API_KEY", "sk-sentinel")
    assert "sk-sentinel" not in json.dumps(_environment_fingerprint())
