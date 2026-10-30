"""Read-only preflight composition. No state, authorization or execution effects."""

from pathlib import Path

from .documents import Documents
from .repository import Repository
from .roadmap import parse_roadmap
from .runtime import discover_runtime


def discover(target: str | Path) -> dict:
    repository = Repository(Path(target))
    identity = repository.discover()
    documents = Documents(repository.root)
    documents.collect()
    key = documents.add(repository.root / "ROADMAP.md", "roadmap")
    roadmap = parse_roadmap(documents.texts[key], key)
    runtime, commands = discover_runtime(documents)
    return {
        "ok": True, "discovery_version": 1, "repository": identity,
        "roadmap": roadmap.as_dict(), "runtime": runtime, "verification": commands,
        "documents": documents.as_list(), "external_links": sorted(documents.external_links),
        "limitations": [
            "Local cached remote identity/default refs only; no server freshness check.",
            "Unstructured instruction prose is retained as source evidence, not semantically reconciled.",
            "Discovery is not authorization, verification success, or an execution sandbox.",
        ],
    }
