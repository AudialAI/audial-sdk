"""
Every script in examples/ runs against the Audial dev API without an exception.

These tests use real runs on a real deployment, so they are marked ``dev`` and
skipped unless asked for explicitly::

    AUDIAL_DEV_API_BASE_URL=https://<dev host>/api \\
    AUDIAL_DEV_API_KEY=aud_... \\
    pytest -m dev tests/test_examples.py

``AUDIAL_DEV_USER_ID`` is needed only with an older key. ``AUDIAL_DEV_EXAMPLES``
limits the run to some scripts (comma separated, e.g.
``segmentation.py,lyrics_lines.py``). The production host is refused: these runs
are for the dev API only.
"""

import os
import subprocess
import sys

import pytest

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
PRODUCTION_HOSTS = ("api.audialmusic.ai",)

# Read before conftest's autouse fixture replaces the key for unit tests.
DEV_BASE_URL = os.environ.get("AUDIAL_DEV_API_BASE_URL", "")
DEV_API_KEY = os.environ.get("AUDIAL_DEV_API_KEY", "")
DEV_USER_ID = os.environ.get("AUDIAL_DEV_USER_ID", "")
ONLY = [name.strip() for name in os.environ.get("AUDIAL_DEV_EXAMPLES", "").split(",") if name.strip()]


def _scripts():
    names = sorted(name for name in os.listdir(EXAMPLES) if name.endswith(".py"))
    return [name for name in names if not ONLY or name in ONLY]


def _needs_your_own_file(path):
    """Examples that leave the input file to the reader ("path/to/clip.wav")."""
    with open(path, encoding="utf-8") as f:
        return '"path/to/' in f.read()


@pytest.mark.dev
@pytest.mark.parametrize("script", _scripts())
def test_examples(script, tmp_path):
    if not DEV_BASE_URL or not DEV_API_KEY:
        pytest.skip("set AUDIAL_DEV_API_BASE_URL and AUDIAL_DEV_API_KEY to run the examples on the dev API")
    if any(host in DEV_BASE_URL for host in PRODUCTION_HOSTS):
        pytest.fail("AUDIAL_DEV_API_BASE_URL points at production; the examples run on the dev API only")

    path = os.path.join(EXAMPLES, script)
    if _needs_your_own_file(path):
        pytest.skip(f"{script} takes an input file the reader supplies")

    env = dict(os.environ)
    env["AUDIAL_API_BASE_URL"] = DEV_BASE_URL
    env["AUDIAL_API_KEY"] = DEV_API_KEY
    if DEV_USER_ID:
        env["AUDIAL_USER_ID"] = DEV_USER_ID
    else:
        env.pop("AUDIAL_USER_ID", None)

    completed = subprocess.run(
        [sys.executable, path],
        cwd=str(tmp_path),            # results land in a temporary audial_results/
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert completed.returncode == 0, (
        f"{script} exited with {completed.returncode}\n"
        f"--- stdout ---\n{completed.stdout[-4000:]}\n--- stderr ---\n{completed.stderr[-4000:]}"
    )
