"""Conservative environment and verification selection from static evidence."""

import json
import re
import shlex
import tomllib

from .diagnostics import DiscoveryError
from .documents import Documents
from .markdown import section_texts


# Discovery capability policy, not a claim that M4 container images exist yet.
RUNTIME_LINES = {"python": (3, 12, 0), "node": (22, 0, 0)}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def supports(requirement: str, family: str, source: str) -> bool:
    """Evaluate a documented, bounded version-range subset against policy lines."""
    def invalid():
        raise DiscoveryError("runtime.syntax", "Use supported numeric version ranges; see docs/DISCOVERY.md. Unrecognized constraints cannot be guessed.", source)

    if not isinstance(requirement, str) or not requirement.strip():
        invalid()
    version = RUNTIME_LINES[family]
    alternatives = requirement.split("||") if family == "node" else [requirement]
    results = []
    for alternative in alternatives:
        if not alternative.strip():
            invalid()
        alternative = re.sub(r"(>=|<=|==|!=|~=|>|<|=|\^|~)\s+", r"\1", alternative.strip())
        clauses = re.split(r"\s*,\s*|\s+", alternative)
        matches = []
        for clause in clauses:
            if clause in {"*", "x", "X"}:
                matches.append(True)
                continue
            match = re.fullmatch(r"(>=|<=|==|!=|~=|>|<|=|\^|~)?(\d+)(?:\.(\d+|\*|x|X))?(?:\.(\d+|\*|x|X))?", clause)
            if not match:
                invalid()
            operator = match[1] or "=="
            parts = [p for p in match.groups()[1:] if p is not None]
            wild = next((i for i, p in enumerate(parts) if p in {"*", "x", "X"}), len(parts))
            if any(p not in {"*", "x", "X"} for p in parts[wild:]):
                invalid()
            count = wild
            values = tuple(int(p) for p in parts[:wild])
            floor = values + (0,) * (3 - count)
            if operator in {"==", "=", "!="}:
                equal = version == floor if family == "python" and wild == len(parts) else version[:count] == values
                matches.append(not equal if operator == "!=" else equal)
            elif wild != len(parts):
                invalid()
            elif operator in {">=", "<=", ">", "<"}:
                matches.append({">=": version >= floor, "<=": version <= floor, ">": version > floor, "<": version < floor}[operator])
            else:
                if family == "python" and operator != "~=":
                    invalid()
                if family == "python" and count < 2:
                    invalid()
                if family == "node" and operator == "~=":
                    invalid()
                if operator == "^":
                    bump = next((i for i, p in enumerate(floor) if p), 2)
                else:
                    bump = max(0, count - 2) if operator == "~=" else (1 if count > 1 else 0)
                ceiling = floor[:bump] + (floor[bump] + 1,) + (0,) * (2 - bump)
                matches.append(floor <= version < ceiling)
        results.append(all(matches))
    return any(results)


def parse_commands(body: str, source: str) -> list[list[str]]:
    """Verification sections are one fenced shell block of literal argv commands."""
    match = re.fullmatch(r"(`{3,}|~{3,})(?:sh|bash|shell)\s*\n([\s\S]*?)\n\1", body)
    if not match:
        raise DiscoveryError("verification.syntax", "Use one sh/bash/shell fenced block under '## Verification', one literal command per line.", source)
    commands = []
    for line in match[2].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.search(r"[|&;<>`$\n\\]", line):
            raise DiscoveryError("verification.shell", "Split commands into literal argv lines; shell operators, expansions and continuations are unsupported.", source)
        try:
            argv = shlex.split(line)
        except ValueError as exc:
            raise DiscoveryError("verification.syntax", "Correct the command's quoting.", source) from exc
        if not argv or "=" in argv[0] or argv[0].startswith("-"):
            raise DiscoveryError("verification.syntax", "Declare an executable and arguments without shell assignments.", source)
        commands.append(argv)
    if not commands:
        raise DiscoveryError("verification.missing", "Declare at least one verification command.", source)
    return commands


def discover_runtime(documents: Documents) -> tuple[dict, list[dict]]:
    root = documents.root
    metadata = {}
    for name in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "package.json", ".python-version", ".node-version", ".nvmrc", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"):
        path = root / name
        if path.exists() or path.is_symlink():
            key = documents.add(path, "runtime")
            metadata[name] = documents.texts.get(key, "")
    python = any(n in metadata for n in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", ".python-version"))
    node = any(n in metadata for n in ("package.json", ".node-version", ".nvmrc"))
    if python == node:
        raise DiscoveryError("runtime.ambiguous", "Provide evidence for exactly one Python or Node project; mixed/unknown environments require explicit support.", str(root))
    family = "python" if python else "node"
    constraints = []
    explicit = []
    for key, text in sorted(documents.texts.items()):
        if not key.endswith(".md"):
            continue
        for body in section_texts(text, "Runtime", key):
            for line in body.splitlines():
                match = re.fullmatch(r"(Python|Node):\s*(\S.*)", line.strip())
                if not match:
                    raise DiscoveryError("runtime.syntax", "Use 'Python: <range>' or 'Node: <range>' lines under '## Runtime'.", key)
                declared = match[1].lower()
                if declared != family:
                    raise DiscoveryError("instructions.conflict", "Runtime instructions conflict with project metadata; resolve the environment explicitly.", key)
                constraints.append({"source": key, "requirement": match[2]})
        sections = section_texts(text, "Verification", key)
        if len(sections) > 1:
            raise DiscoveryError("verification.duplicate", "Keep one Verification section per document.", key)
        if sections:
            explicit.append((key, parse_commands(sections[0], key)))
    package = {}
    if python:
        try:
            project = tomllib.loads(metadata.get("pyproject.toml", "")).get("project", {})
            requirement = project.get("requires-python")
        except (tomllib.TOMLDecodeError, AttributeError) as exc:
            raise DiscoveryError("runtime.metadata", "Correct pyproject.toml and its project table.", "pyproject.toml") from exc
        if requirement is not None:
            constraints.append({"source": "pyproject.toml", "requirement": requirement})
        pins = (".python-version",)
    else:
        try:
            package = json.loads(metadata.get("package.json", "{}"), object_pairs_hook=_unique_object)
            engines = package.get("engines", {})
            scripts = package.get("scripts", {})
            if not isinstance(engines, dict) or not isinstance(scripts, dict):
                raise ValueError()
        except (ValueError, AttributeError) as exc:
            raise DiscoveryError("runtime.metadata", "Correct package.json; engines and scripts must be objects.", "package.json") from exc
        if "node" in engines:
            constraints.append({"source": "package.json:engines.node", "requirement": engines["node"]})
        pins = (".node-version", ".nvmrc")
        manager = package.get("packageManager", "npm")
        if not isinstance(manager, str) or not re.fullmatch(r"npm(?:@\d+(?:\.\d+){0,2})?", manager) or any(n in metadata for n in ("pnpm-lock.yaml", "yarn.lock")):
            raise DiscoveryError("runtime.manager", "This policy supports npm only; resolve package-manager/lockfile requirements before proceeding.", "package.json")
    for pin in pins:
        if pin in metadata:
            constraints.append({"source": pin, "requirement": metadata[pin].strip().removeprefix("v")})
    for item in constraints:
        if not supports(item["requirement"], family, item["source"]):
            raise DiscoveryError("runtime.unsupported", f"Requirements exclude the supported {family} baseline {'.'.join(map(str, RUNTIME_LINES[family]))}; resolve requirements or extend global capability policy.", item["source"])
    if explicit:
        first = explicit[0][1]
        if any(commands != first for _, commands in explicit[1:]):
            raise DiscoveryError("instructions.conflict", "Verification declarations disagree: " + ", ".join(key for key, _ in explicit) + ". Resolve them before selecting checks.", str(root))
        commands = [{"argv": argv, "sources": [key for key, _ in explicit]} for argv in first]
    elif node and isinstance(package.get("scripts", {}).get("test"), str) and package["scripts"]["test"].strip() and "no test specified" not in package["scripts"]["test"].lower():
        commands = [{"argv": ["npm", "test"], "sources": ["package.json:scripts.test"]}]
    else:
        raise DiscoveryError("verification.missing", "Declare checks in a document's '## Verification' fenced block (or a Node scripts.test entry); no verification command is inferred from filenames.", str(root))
    version = RUNTIME_LINES[family]
    runtime = {"family": family, "version_line": ".".join(map(str, version[:2])) if python else str(version[0]),
               "baseline_version": ".".join(map(str, version)), "constraints": constraints,
               "selection_source": "runner capability policy", "package_manager": "npm" if node else None}
    return runtime, commands
