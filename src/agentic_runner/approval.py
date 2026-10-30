"""Committed approval scope and precise exceptions for progress/evidence edits."""

import hashlib
import base64
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .discovery import discover
from .documents import Documents, inside, markdown_links, read_file
from .durable import StateError, canonical_json
from .markdown import section_texts, structure
from .repository import Repository
from .roadmap import parse_roadmap


def digest(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class RunnerPolicy:
    requested_model: str = "GPT-6.1-Sol"
    reasoning_effort: str = "high"
    max_ci_repairs: int = 2
    global_concurrency: int = 1

    def as_dict(self):
        data = asdict(self)
        if self.requested_model != "GPT-6.1-Sol" or self.reasoning_effort != "high":
            raise StateError("approval.policy", "Model/effort downgrades are not authorized; verify CLI representation in M4.", "policy")
        if type(self.max_ci_repairs) is not int or self.max_ci_repairs != 2 or type(self.global_concurrency) is not int or self.global_concurrency < 1:
            raise StateError("approval.policy", "Use the approved repair budget and a positive integer global concurrency.", "policy")
        return {"version": 1, **data}


def evidence_path(path):
    value = Path(path)
    return path in {"HANDOFF.md", "CHECKPOINT.md"} or (value.parts[:2] == ("docs", "evidence") and value.suffix == ".md")


def roadmap_scope(text):
    """Mask only status cell bytes, preserving all other roadmap prose/formatting."""
    parse_roadmap(text)
    lines, headings, _ = structure(text, "ROADMAP.md")
    start = next(h.index for h in headings if h.level == 2 and h.title == "Milestone Progress")
    end = next((h.index for h in headings if h.level <= 2 and h.index > start), len(lines))
    original = text.splitlines(keepends=True)
    for index in range(start + 1, end):
        original[index] = re.sub(r"^(\s*\|\s*M[1-9][0-9]*\s*\|\s*)(complete|in progress|not started)(\s*\|\s*)$", r"\1<status>\3", original[index])
    return "".join(original)


def tracked_files(repository, revision):
    result = {}
    for entry in repository._run(["ls-tree", "-r", "-z", "--full-tree", revision]).split("\0"):
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        mode, kind, oid = metadata.split()
        if mode not in {"100644", "100755"} or kind != "blob":
            raise StateError("approval.file_type", "Submodules and committed symlinks need explicit future support.", path)
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise StateError("approval.path", "Invalid committed path.", path)
        result[path] = (mode, oid)
        if len(result) > 20000:
            raise StateError("approval.size", "Committed file inventory exceeds 20000 entries.", str(repository.root))
    return result


def require_clean(repository, revision, tracked):
    index = {}
    for entry in repository._run(["ls-files", "--stage", "-z"]).split("\0"):
        if entry:
            metadata, path = entry.split("\t", 1)
            mode, oid, stage = metadata.split()
            if stage != "0":
                raise StateError("approval.dirty", "Resolve index conflicts before a new start.", str(repository.root))
            index[path] = (mode, oid)
    if index != tracked or repository._run(["ls-files", "--others", "--exclude-standard", "-z"]):
        raise StateError("approval.dirty", "New starts require an index and worktree matching the committed revision, with no untracked files.", str(repository.root))
    for path, (mode, oid) in tracked.items():
        file = repository.root / path
        if file.is_symlink() or inside(repository.root, file) != file:
            raise StateError("approval.dirty", "Committed paths must remain regular files inside the checkout.", path)
        data = read_file(file)
        algorithm = hashlib.sha1 if len(oid) == 40 else hashlib.sha256
        actual = algorithm(f"blob {len(data)}\0".encode() + data).hexdigest()
        if actual != oid or bool(file.stat().st_mode & stat.S_IXUSR) != (mode == "100755"):
            raise StateError("approval.dirty", "Commit or restore existing changes before a new start; filters are not run to normalize content.", path)
    if repository._run(["rev-parse", "--verify", "HEAD"]) != revision:
        raise StateError("approval.moved", "HEAD moved during approval inspection; retry under stable ownership.", str(repository.root))


def scope_snapshot(repository, policy):
    result = discover(repository.root)
    if result["external_links"]:
        raise StateError("approval.external", "Capture external linked requirements as committed local files before approval; external links are not silently authorized.", str(repository.root))
    documents = Documents(repository.root)
    documents.collect()
    # Match discovery's runtime inventory as well as the document closure.
    for record in result["documents"]:
        key = documents.add(Path(record["path"]) if Path(record["path"]).is_absolute() else repository.root / record["path"], record["kind"], ancestor=Path(record["path"]).is_absolute(), scope=record["scope"])
        if documents.records[key]["sha256"] != record["sha256"]:
            raise StateError("approval.moved", "Discovery sources changed while capturing scope; retry.", key)
    protected = {key for key, record in documents.records.items() if record["kind"] == "instructions" or not evidence_path(key)}
    for key, text in documents.texts.items():
        if evidence_path(key) and (section_texts(text, "Runtime", key) or section_texts(text, "Verification", key)):
            protected.add(key)
    pending = list(protected)
    while pending:
        key = pending.pop()
        if Path(key).suffix.lower() != ".md":
            continue
        origin = Path(key) if Path(key).is_absolute() else repository.root / key
        for link in markdown_links(documents.texts[key], key, include_images=True):
            try:
                target = urlsplit(link)
            except ValueError as exc:
                raise StateError("approval.reference", "Correct the malformed requirement/asset link.", key) from exc
            if target.scheme or target.netloc:
                raise StateError("approval.external", "Capture external linked requirements/assets as committed local files before approval.", key)
            if not target.path:
                continue
            resolved = inside(repository.root, origin.parent / unquote(target.path))
            relative = str(resolved.relative_to(repository.root))
            documents.add(origin.parent / unquote(target.path), "requirement")
            if relative not in protected:
                protected.add(relative)
                pending.append(relative)
    files = {}
    for key in sorted(protected):
        path = Path(key) if Path(key).is_absolute() else repository.root / key
        data = read_file(path)
        if hashlib.sha256(data).hexdigest() != documents.records[key]["sha256"]:
            raise StateError("approval.moved", "Requirement bytes changed during scope inspection; retry.", key)
        normalized = roadmap_scope(data.decode()) if key == "ROADMAP.md" else None
        files[key] = {"sha256": hashlib.sha256(data).hexdigest(), "scope_sha256": hashlib.sha256(normalized.encode() if normalized is not None else data).hexdigest(), "committed": not Path(key).is_absolute()}
    configuration = {"policy": policy.as_dict(), "runtime": result["runtime"], "verification": result["verification"]}
    scope = {key: value["scope_sha256"] for key, value in files.items()}
    return {"repository": result["repository"], "files": files, "scope_hash": digest(scope),
            "configuration": configuration, "configuration_hash": digest(configuration), "milestone": result["roadmap"]["next_milestone"]}


def capture_approval(repository, policy):
    snapshot = scope_snapshot(repository, policy)
    identity = snapshot["repository"]
    if identity["branch"] != identity["default_branch"]:
        raise StateError("approval.branch", "A new start requires the local default branch checkout.", str(repository.root))
    tracked = tracked_files(repository, identity["head"])
    require_clean(repository, identity["head"], tracked)
    if snapshot["milestone"] is None:
        raise StateError("approval.complete", "The roadmap has no incomplete milestone to authorize.", str(repository.root))
    for path, value in snapshot["files"].items():
        if value["committed"] and path not in tracked:
            raise StateError("approval.uncommitted", "Commit every protected requirement before start.", path)
        if value["committed"]:
            oid = tracked[path][1]
            size = int(repository._run(["cat-file", "-s", oid]))
            if size > 1024 * 1024:
                raise StateError("approval.size", "Split committed requirements exceeding 1 MiB.", path)
            data = repository._run(["cat-file", "blob", oid], binary=True)
            if hashlib.sha256(data).hexdigest() != value["sha256"]:
                raise StateError("approval.moved", "Requirement bytes changed during approval inspection; retry.", path)
            value["blob_oid"] = oid
        else:
            data = read_file(Path(path))
            if hashlib.sha256(data).hexdigest() != value["sha256"]:
                raise StateError("approval.moved", "Ancestor instructions changed during approval inspection.", path)
        value["content_base64"] = base64.b64encode(data).decode()
    if len(canonical_json(snapshot)) > 4 * 1024 * 1024:
        raise StateError("approval.size", "Approval exceeds the 4 MiB snapshot limit; reduce captured requirements.", str(repository.root))
    return {"version": 1, "approved_revision": identity["head"], **snapshot}
