from __future__ import annotations

import json
import os
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .sources import OFFICIAL_HOSTS


class DiscoveryDisabled(RuntimeError):
    pass


def filter_official_urls(urls: list[str]) -> list[str]:
    accepted: list[str] = []
    for value in urls:
        try:
            parsed = urlsplit(value)
        except ValueError:
            continue
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
            continue
        accepted.append(value)
    return accepted


def _transport(url: str, payload: bytes, headers: dict[str, str]) -> dict[str, object]:
    request = Request(url, data=payload, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"Tavily respondió HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def tavily_search(
    query: str,
    api_key: str | None = None,
    transport: Callable[[str, bytes, dict[str, str]], dict[str, object]] = _transport,
) -> list[str]:
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        raise DiscoveryDisabled("TAVILY_API_KEY no está configurada; discovery permanece desactivado.")
    body = {
        "query": query,
        "search_depth": "advanced",
        "max_results": 10,
        "include_domains": sorted(OFFICIAL_HOSTS),
        "include_answer": False,
        "include_raw_content": False,
    }
    response = transport(
        "https://api.tavily.com/search",
        json.dumps(body).encode("utf-8"),
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    urls = [str(item.get("url")) for item in response.get("results", []) if isinstance(item, dict) and item.get("url")]
    return filter_official_urls(urls)
