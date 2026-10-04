"""The JWT_SECRET production safety guard raises at import time (before the
app can serve a single request), so it can't be exercised via the normal
in-process TestClient — a subprocess is the only way to observe "does this
process actually fail to start" without poisoning the test process's own
already-imported app.main module for every other test in the suite."""

import os
import subprocess
import sys

import pytest

_CHECK_CODE = "import app.main"


def _run_with_env(extra_env: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, **extra_env}
    return subprocess.run(
        [sys.executable, "-c", _CHECK_CODE],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("jwt_secret", ["dev-only-insecure-secret-change-me", ""])
def test_refuses_to_start_in_production_with_unsafe_secret(jwt_secret):
    result = _run_with_env({"ENV": "production", "JWT_SECRET": jwt_secret})
    assert result.returncode != 0
    assert "JWT_SECRET" in result.stderr


def test_starts_fine_in_production_with_a_real_secret():
    result = _run_with_env({"ENV": "production", "JWT_SECRET": "a-real-random-secret-value"})
    assert result.returncode == 0, result.stderr


def test_dev_default_is_fine_outside_production():
    result = _run_with_env({"ENV": "development", "JWT_SECRET": "dev-only-insecure-secret-change-me"})
    assert result.returncode == 0, result.stderr
