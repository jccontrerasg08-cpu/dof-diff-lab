from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dof-monitor.yml"
CHECK_WORKFLOW = ROOT / ".github" / "workflows" / "check.yml"


def main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required_fragments = (
        "name: Monitor diario del DOF",
        "workflow_dispatch:",
        "schedule:",
        'cron: "17 16 * * *"',
        "concurrency:",
        "cancel-in-progress: false",
        "contents: read",
        "contents: write",
        "pages: write",
        "id-token: write",
        "PUBLICATION_DATE:",
        "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        'date -u -d "$publication_date"',
        "python3 -m dof_diff_lab.monitor",
        "git diff --quiet -- data site",
        "git commit -m",
        "if-no-files-found: error",
        "needs: [capture, publish]",
    )
    for fragment in required_fragments:
        assert fragment in text, fragment
    assert "pull_request:" not in text
    assert 'publication_date="${{ inputs.publication_date }}"' not in text
    assert "data/raw" not in text
    refs = re.findall(r"uses:\s*[^@\s]+@([^\s]+)", text)
    assert refs and all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs), refs

    check_text = CHECK_WORKFLOW.read_text(encoding="utf-8")
    for action_commit in (
        "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "45bfe0192ca1faeb007ade9deae92b16b8254a0d",
        "fc324d3547104276b827a68afc52ff2a11cc49c9",
        "cd2ce8fcbc39b97be8ca5fce6e763baed58fa128",
    ):
        assert action_commit in text or action_commit in check_text, action_commit
    for command in (
        "python3 tests/check_cli.py",
        "python3 tests/check_monitor.py",
        "python3 tests/check_monitor_workflow.py",
        "python3 tests/check_public_readiness.py",
    ):
        assert command in check_text, command


if __name__ == "__main__":
    main()
