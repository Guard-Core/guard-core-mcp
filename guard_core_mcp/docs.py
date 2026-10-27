import json
from functools import lru_cache
from pathlib import Path

from guard_core_mcp.json_types import JsonObject

DOCS_ROOT = Path(__file__).parent / "_docs"
KNOWLEDGE_ROOT = Path(__file__).parent / "_knowledge"


@lru_cache(maxsize=1)
def manifest() -> dict[str, dict[str, str]]:
    loaded: dict[str, dict[str, str]] = json.loads(
        (DOCS_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    return loaded


@lru_cache(maxsize=1)
def knowledge_manifest() -> dict[str, dict[str, str]]:
    loaded: dict[str, dict[str, str]] = json.loads(
        (KNOWLEDGE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    return loaded


def document_url(package: str, relative_path: str) -> str:
    site_url = manifest()[package]["site_url"]
    slug = Path(relative_path).with_suffix("")
    if slug.name == "index":
        slug = slug.parent
    return site_url if str(slug) == "." else f"{site_url}{slug}/"


def _knowledge_url(package: str) -> str:
    return knowledge_manifest()[package]["site_url"]


def _corpora() -> list[tuple[Path, dict[str, dict[str, str]]]]:
    return [(DOCS_ROOT, manifest()), (KNOWLEDGE_ROOT, knowledge_manifest())]


def _entry_url(root: Path, package: str, relative_path: str) -> str:
    if root is KNOWLEDGE_ROOT:
        return _knowledge_url(package)
    return document_url(package, relative_path)


def _score(text: str, tokens: list[str]) -> tuple[int, str, str]:
    heading = ""
    best_score = 0
    best_heading = ""
    best_line = ""
    total = 0
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        lowered = line.lower()
        hits = sum(lowered.count(token) for token in tokens)
        total += hits
        if hits > best_score:
            best_score, best_heading, best_line = hits, heading, line.strip()
    return total, best_heading, best_line


def _package_pages(root: Path, name: str) -> list[Path]:
    base = root / name
    return sorted(base.rglob("*.md")) + sorted(base.rglob("*.mdx"))


def search_docs(query: str, package: str | None = None, limit: int = 5) -> JsonObject:
    tokens = query.lower().split()
    ranked: list[tuple[int, JsonObject]] = []
    for root, entries in _corpora():
        names = [package] if package else sorted(entries)
        for name in names:
            if name not in entries:
                continue
            for markdown in _package_pages(root, name):
                relative = markdown.relative_to(root / name)
                score, heading, snippet = _score(
                    markdown.read_text(encoding="utf-8"), tokens
                )
                if score:
                    ranked.append(
                        (
                            score,
                            {
                                "package": name,
                                "path": str(relative),
                                "heading": heading,
                                "snippet": snippet[:300],
                                "url": _entry_url(root, name, str(relative)),
                                "score": score,
                            },
                        )
                    )
    ranked.sort(key=lambda scored: -scored[0])
    return {"query": query, "results": [entry for _, entry in ranked[:limit]]}


def get_doc(package: str, path: str) -> JsonObject:
    root = DOCS_ROOT
    if package not in manifest():
        root = KNOWLEDGE_ROOT
        if package not in knowledge_manifest():
            return {"error": "unknown doc path"}
    package_root = (root / package).resolve()
    target = (package_root / path).resolve()
    if not target.is_relative_to(package_root) or not target.is_file():
        return {"error": "unknown doc path"}
    return {
        "package": package,
        "path": path,
        "url": _entry_url(root, package, path),
        "content": target.read_text(encoding="utf-8"),
    }
