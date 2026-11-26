from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "web-watch.yml"
DOF_WORKFLOW = ROOT / ".github" / "workflows" / "dof-monitor.yml"
CHECK_WORKFLOW = ROOT / ".github" / "workflows" / "check.yml"


def main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for fragment in (
        "workflow_dispatch:",
        'cron: "23 3,9,15,21 * * *"',
        "group: dof-monitor-publication",
        "cancel-in-progress: false",
        "contents: read",
        "contents: write",
        "timeout-minutes: 10",
        "id: watch",
        "python3 -m dof_diff_lab.web_watch --root .",
        "if: always() && !cancelled() && steps.checkout.outcome == 'success'",
        "git add -- data/web-watch",
        "git diff --cached --quiet -- data/web-watch",
        "git pull --rebase origin main",
        "git push",
        "if: always() && steps.watch.outcome == 'failure'",
        "exit 1",
    ):
        assert fragment in text, fragment
    refs = re.findall(r"uses:\s*[^@\s]+@([^\s]+)", text)
    assert refs and all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs), refs
    assert text.count("contents: write") == 1
    assert "data/normalized" not in text
    assert "data/manifests" not in text
    assert "secrets." not in text

    dof_text = DOF_WORKFLOW.read_text(encoding="utf-8")
    assert "group: dof-monitor-publication" in dof_text

    check_text = CHECK_WORKFLOW.read_text(encoding="utf-8")
    assert "python3 tests/check_web_watch.py" in check_text
    assert "python3 tests/check_web_watch_workflow.py" in check_text


if __name__ == "__main__":
    main()
