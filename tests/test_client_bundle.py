"""Client bundle must never contain secrets (the browser is not a vault)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DIST = WEB / "dist"

# Patterns that must never appear in shipped JS/CSS/HTML.
SECRET_PATTERNS = (
    re.compile(rb"OWNERAI_[A-Z_]*KEY"),
    re.compile(rb"(sk-[A-Za-z0-9]{16,})"),
    re.compile(rb"(AIza[A-Za-z0-9_-]{10,})"),
    re.compile(rb"xox[bpars]-[A-Za-z0-9-]{10,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    # hardcoded-looking assignments of 40+ char hex/base64 to secret names
    re.compile(rb"(?i)(?:secret|api[_-]?key|password|passwd)[\"'=:\s]{1,12}[A-Za-z0-9+/=_-]{40,}"),
    # a raw Argon2id hash would mean a credential leaked into the bundle
    re.compile(rb"\$argon2id\$"),
)


@pytest.fixture(scope="session")
def built_dist():
    """Build the real client bundle (skip only when Node is absent)."""
    if os.name == "nt":
        findable, npm = "npm.cmd", "npm.cmd"
    else:
        findable, npm = "npm", "npm"
    if not shutil.which(findable):
        pytest.skip("npm not on PATH — cannot build client for secret scan")
    subprocess.run([npm, "run", "build"], cwd=WEB, check=True,
                   capture_output=True, timeout=300)
    assert DIST.is_dir(), "vite build did not produce web/dist"
    return DIST


def test_client_bundle_contains_no_secrets(built_dist: Path):
    files = sorted(
        p for p in built_dist.rglob("*")
        if p.is_file() and p.suffix in {".js", ".css", ".html", ".json", ".svg"}
    )
    assert files, "no client files found in dist — build produced nothing?"
    findings = []
    for path in files:
        blob = path.read_bytes()
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(blob):
                snippet = match.group(0)
                # long hex tokens inside hashes of asset names are impossible:
                # asset names are short; flag everything else
                findings.append((str(path.relative_to(DIST)), snippet[:60]))
    assert not findings, f"secret-shaped strings in client bundle: {findings}"


def test_bundle_does_not_reference_backend_env(built_dist: Path):
    """The bundle may call /api/* paths only, never import process.env."""
    blobs = b"".join(
        p.read_bytes() for p in built_dist.rglob("assets/*.js"))
    assert b"OWNERAI_" not in blobs
    assert b"process.env" not in blobs
    server_only = os.environ.get("OWNERAI_SECRET_KEY", "")
    if server_only:
        assert server_only.encode() not in blobs
