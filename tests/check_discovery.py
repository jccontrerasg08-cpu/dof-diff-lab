from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dof_diff_lab.discovery import DiscoveryDisabled, filter_official_urls, tavily_search


def main() -> None:
    urls = filter_official_urls([
        "https://dof.gob.mx/nota_detalle.php?codigo=1",
        "https://sidof.segob.gob.mx/datos_abiertos",
        "https://example.com/fake-dof",
        "javascript:alert(1)",
    ])
    assert urls == [
        "https://dof.gob.mx/nota_detalle.php?codigo=1",
        "https://sidof.segob.gob.mx/datos_abiertos",
    ]

    try:
        tavily_search("DOF comercio exterior", api_key=None)
    except DiscoveryDisabled:
        pass
    else:
        raise AssertionError("Missing Tavily key must disable discovery safely")

    captured = {}
    def transport(url: str, payload: bytes, headers: dict[str, str]) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload.decode("utf-8")
        captured["headers"] = headers
        return {"results": [
            {"url": "https://dof.gob.mx/a"},
            {"url": "https://evil.example/a"},
            {"url": "https://sidof.segob.gob.mx/b"},
        ]}

    found = tavily_search("DOF cambios", api_key="test-key", transport=transport)
    assert found == ["https://dof.gob.mx/a", "https://sidof.segob.gob.mx/b"]
    assert captured["url"] == "https://api.tavily.com/search"
    assert "include_domains" in captured["payload"]
    assert captured["headers"]["Authorization"] == "Bearer test-key"


if __name__ == "__main__":
    main()
