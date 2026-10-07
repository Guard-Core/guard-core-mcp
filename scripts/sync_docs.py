import json
import re
import shutil
import sys
from pathlib import Path

REPOSITORIES = {
    "fastapi-guard": "https://guard-core.github.io/fastapi-guard/latest/",
    "guard-core": "https://guard-core.github.io/guard-core/latest/",
    "guard-agent": "https://guard-core.github.io/guard-agent/latest/",
    "guard-core-ts": "https://rennf93.github.io/guard-core-ts/",
}

# Repos whose markdown lives deeper than docs/ (an Astro Starlight site keeps
# content under docs/src/content/docs); only that subtree gets vendored.
DOCS_SUBDIRS = {
    "guard-core-ts": "src/content/docs",
}

PACKAGE_ROOT = Path(__file__).parent.parent / "guard_core_mcp"
DOCS_ROOT = PACKAGE_ROOT / "_docs"
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
MARKDOWN_PATTERNS = ("*.md", "*.mdx")

# The CI docs-drift job clones each repo as a sibling of this checkout
# (../<package>), while the local ecosystem checkout nests them under
# per-language directories next to this repo's parent; both layouts
# resolve, siblings first. Tuple elements are joined after "../", so
# they are relative to the checkout's parent directory.
NESTED_LAYOUT = {
    "fastapi-guard": ("..", "Python", "fastapi-guard"),
    "guard-core": ("..", "Python", "guard-core"),
    "guard-agent": ("..", "Python", "guard-agent"),
    "guard-core-ts": ("..", "Typescript", "guard-core-ts"),
}


def find_repository(package: str) -> Path:
    candidates = [Path("..") / package]
    nested = NESTED_LAYOUT.get(package)
    if nested is not None:
        candidates.append(Path("..").joinpath(*nested))
    for candidate in candidates:
        if (candidate / "docs").is_dir():
            return candidate
    raise SystemExit(
        f"{candidates[0]} not found; clone {package} next to this repo "
        "(or under its ecosystem language directory)"
    )


def read_version(repository: Path) -> str:
    pyproject = repository / "pyproject.toml"
    if pyproject.is_file():
        match = VERSION_PATTERN.search(pyproject.read_text())
        if match is None:
            raise SystemExit(f"no version found in {repository}/pyproject.toml")
        return match.group(1)
    package_json = repository / "package.json"
    if package_json.is_file():
        version = json.loads(package_json.read_text()).get("version")
        if version is None:
            raise SystemExit(f"no version found in {repository}/package.json")
        return str(version)
    raise SystemExit(f"no version source found in {repository}")


def sync(package: str, site_url: str) -> dict[str, str]:
    repository = find_repository(package)
    source = repository / "docs" / DOCS_SUBDIRS.get(package, "")
    if not source.is_dir():
        raise SystemExit(f"{source} not found; clone {package} next to this repo")

    destination = DOCS_ROOT / package
    shutil.rmtree(destination, ignore_errors=True)
    for pattern in MARKDOWN_PATTERNS:
        for markdown in sorted(source.rglob(pattern)):
            target = destination / markdown.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(markdown, target)

    return {"site_url": site_url, "version": read_version(repository)}


def main() -> None:
    DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        package: sync(package, site_url) for package, site_url in REPOSITORIES.items()
    }
    (DOCS_ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(f"vendored docs for {', '.join(manifest)}", file=sys.stderr)


if __name__ == "__main__":
    main()
