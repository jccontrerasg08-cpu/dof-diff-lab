from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dof_diff_lab", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for command in ("sync", "build", "search", "discover"):
        assert command in result.stdout, (command, result.stdout)


if __name__ == "__main__":
    main()
