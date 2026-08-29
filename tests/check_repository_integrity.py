from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from dof_diff_lab.monitor import canonical_bytes, note_key, sha256_bytes
from dof_diff_lab.sources import OFFICIAL_HOSTS

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_SCHEMAS = {"1.0", "1.1"}


def main() -> None:
    normalized_root = ROOT / "data" / "normalized"
    files = sorted(normalized_root.glob("*/*.json"))
    assert files, "No committed normalized catalogs found"

    for path in files:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(catalog, dict), path
        assert catalog.get("schema_version") in SUPPORTED_SCHEMAS, path
        source = catalog.get("source")
        notes = catalog.get("notes")
        assert isinstance(source, dict), path
        assert isinstance(notes, list), path
        assert source.get("publication_date") == path.parent.name, path
        assert source.get("edition") == path.stem, path

        seen: set[str] = set()
        for note in notes:
            assert isinstance(note, dict), path
            assert note.get("title"), path
            canonical_url = str(note.get("canonical_url") or "")
            parsed = urlsplit(canonical_url)
            assert parsed.scheme == "https" and parsed.hostname in OFFICIAL_HOSTS, canonical_url
            key = note_key(note)
            assert key not in seen, f"duplicate note {key} in {path}"
            seen.add(key)
            stored_hash = note.get("record_sha256")
            assert isinstance(stored_hash, str) and len(stored_hash) == 64, f"missing record hash in {path}"
            unhashed = dict(note)
            unhashed.pop("record_sha256")
            assert stored_hash == sha256_bytes(canonical_bytes(unhashed)), f"record hash mismatch: {path} {key}"

        manifest_path = ROOT / "data" / "manifests" / path.parent.name / path.name
        assert manifest_path.is_file(), f"missing manifest for {path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest.get("schema_version") in SUPPORTED_SCHEMAS, manifest_path
        assert manifest.get("publication_date") == path.parent.name, manifest_path
        assert manifest.get("edition") == path.stem, manifest_path
        assert manifest.get("note_count") == len(notes), manifest_path
        assert manifest.get("normalized_path") == str(path.relative_to(ROOT)), manifest_path
        assert manifest.get("normalized_sha256") == sha256_bytes(canonical_bytes(catalog)), manifest_path

    robots = ROOT / "site" / "robots.txt"
    assert robots.read_text(encoding="utf-8") == "User-agent: *\nDisallow: /\n"


if __name__ == "__main__":
    main()
