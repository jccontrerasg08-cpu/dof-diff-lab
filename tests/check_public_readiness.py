from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dof-monitor.yml"


def main() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "No afiliación" in readme
    assert "no sustituye" in readme
    assert "fuente primaria" in readme.lower()
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "SECURITY.md").is_file()
    assert (ROOT / "site" / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nDisallow: /\n"

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.log", ".pytest_cache/", "tmp/"):
        assert pattern in ignored, pattern

    assert not (ROOT / "data" / "raw").exists()

    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'publication_date="${{ inputs.publication_date }}"' not in workflow
    assert "PUBLICATION_DATE:" in workflow
    assert "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" in workflow
    assert "data/raw" not in workflow
    assert "contents: read" in workflow
    assert "contents: write" in workflow
    assert "id-token: write" in workflow
    refs = re.findall(r"uses:\s*[^@\s]+@([^\s]+)", workflow)
    assert refs and all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs), refs

    check_workflow = (ROOT / ".github" / "workflows" / "check.yml").read_text(encoding="utf-8")
    assert "Detectar credenciales rastreadas" in check_workflow
    assert "git grep -nE" in check_workflow


if __name__ == "__main__":
    main()
