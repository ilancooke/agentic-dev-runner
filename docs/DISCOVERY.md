# Read-only discovery contract

```bash
.venv-dev/bin/agentic-runner discover /path/to/checkout
# Equivalent:
.venv-dev/bin/python -m agentic_runner discover /path/to/checkout
```

Discovery prints JSON to stdout. Exit 0 means all supported evidence agrees; exit 2
means a diagnostic stopped selection. Invalid CLI syntax also exits 2 (argparse
prints usage to stderr). No report file, runner state, branch, index, commit,
network request or project process is created by discovery. Nothing is authorized
for execution by this command.

The success object has `ok: true`, `discovery_version: 1`, `repository`, `roadmap`,
`runtime`, `verification`, `documents`, `external_links`, and `limitations`.
It includes the ordered requirement bodies, next milestone ID (or null when all
are complete), literal command argument vectors and their source paths. Document
records include path, role, SHA-256 and instruction scope. Failures contain only
`ok: false` and `diagnostics` with `code`, `message`, `source`, and optional `line`;
no partial milestone/check selection is emitted. Correct the indicated evidence
and rerun. The first diagnostic is reported; this is not a full lint report.

## Repository evidence

The input must be a directory in a non-bare checkout. Discovery canonicalizes it
and finds the nearest enclosing `.git` directory or worktree gitdir file. Linked
worktrees share an identity derived from the canonical common Git directory and
remote URL; their checkout roots, private Git directories, branch/HEAD and cached
default-branch OID are reported separately. Detached HEAD is allowed for inspection.
Unborn/invalid HEAD or missing default refs produce diagnostics. No clean-start or
authorization decision is made here; those are later milestone responsibilities.

Exactly one remote with one fetch URL and the same push URL is required. Multiple
remotes are ambiguous even when one is named `origin`. Credential-free HTTPS,
SSH and scp-style SSH URLs are supported; credential-bearing URLs, local paths,
remote helpers, config includes, URL rewrites and worktree-specific config are
diagnosed. Raw URLs are not repeated in error messages. Supported remote names
contain letters, digits, dots, underscores and hyphens, starting with a letter or
digit.

The default branch comes solely from the cached symbolic
`refs/remotes/<remote>/HEAD` and its existing target ref. Neither `main`, the current
branch, nor a similarly named branch is a fallback. Missing/stale evidence must be
resolved by the operator outside discovery; discovery never fetches or queries a
remote. Results describe local evidence, not server freshness or repository rules.

Only fixed system Git reads are used: explicit-file config listing with includes
disabled, symbolic-ref, show-ref and rev-parse. The subprocess environment is
allowlisted, with user/system Git config, optional locks, lazy fetch and replace
objects disabled. Hooks and fsmonitor are disabled for these reads. No status,
diff, filter, credential helper, project command, transport or shell is invoked.
Each Git read has a 10-second timeout. This is a narrow read-only adapter, not the
setup/run Git adapter described in the root ARCHITECTURE.md.

## Roadmap grammar

`ROADMAP.md` is required at the worktree root. The supported grammar is:

1. Exactly one ATX heading `## Milestone Progress`, with no closing hashes.
2. A table consisting only of these header/separator lines and one or more rows,
   with optional blank lines. The header is exactly `| Milestone | Status |`.
   Separators use at least three dashes per cell, with optional alignment colons.
3. Every row has exactly two cells and outer pipes: stable case-sensitive ID
   `M[1-9][0-9]*` and status `complete`, `in progress`, or `not started`. Cell
   whitespace is ignored. Leading zeros, duplicate IDs and unknown statuses fail.
4. Table order defines execution order. IDs need not be contiguous. Complete rows
   form a prefix. Only the first incomplete row may be `in progress`; all following
   rows are `not started`. All-complete returns a null next milestone.
5. After the table, every row has exactly one matching section heading
   `## M1 — Title` in the same order, using an em dash and nonempty title. No extra,
   missing or duplicated milestone section is allowed. Milestone-like malformed
   headings are rejected. Other level-two contextual sections are allowed.
6. Every milestone has exactly one `### Deliverables` and one
   `### Acceptance criteria`, each with nonempty text. A subsection ends at the
   next level-three heading or the end of its milestone. Other level-three context
   is allowed. Use level-four or deeper headings inside requirement bodies.
   Level-one document titles must precede the progress section.

This minimal example is complete and valid:

```markdown
# Example roadmap

## Milestone Progress

| Milestone | Status |
| --- | --- |
| M1 | complete |
| M2 | not started |

## M1 — Baseline

### Deliverables

Preserve the baseline.

### Acceptance criteria

Existing behavior passes the declared checks.

## M2 — Feature

### Deliverables

Implement [the specification](docs/spec.md).

### Acceptance criteria

The feature passes the declared checks and specification examples.
```

Only structure and ordering are interpreted. Requirement bodies preserve ordinary
Markdown prose, lists, tables, links, inline code and fenced code. ATX headings in
backtick or tilde fences are ignored. Fences may be indented up to three spaces;
closing fences use the same character and at least the opening length. An unclosed
fence is an error. Setext headings, HTML-hidden structural headings and arbitrary
roadmap formats are not structural alternatives. Content is not silently rewritten.
Nonempty text is not proof that subjective acceptance criteria are satisfiable.

## Supporting documents and instruction scope

Discovery inventories root and ancestor `AGENTS.md` files and nested `AGENTS.md`
files, recording their directory scopes. It also inventories README, HANDOFF and
CHECKPOINT Markdown files, Markdown under `docs/`, and GitHub workflow YAML files.
It follows local inline Markdown links and reference-link definitions recursively,
including URL-encoded paths and anchors (file existence is checked; anchor targets
are not validated). Cycles are deduplicated. Links inside fenced/inline code and
inline images are not followed. The prose is preserved; this small scanner is not
a general Markdown renderer or semantic requirements validator.

Local evidence must be regular files inside the canonical worktree and outside
`.git`; escaping traversal/symlinks, missing files, directories and ambiguous
symlinked evidence/source directories fail. Explicit ancestor AGENTS files are
the only documents read outside the worktree. Their local links must point into
the worktree too. External links are listed for inspection without fetching them;
they do not authorize execution. The revised runner supplies only the five required
root documents and the selected milestone; operators must capture required external
context locally before running.

The scan skips `.git`, `.venv`, `.venv-dev`, `node_modules`, `__pycache__`, `.tox`,
`.pytest_cache`, `build` and `dist`. It fails on scan errors, more than 20000 scan
entries, more than 256 evidence files, or files larger than 1 MiB. Text evidence
must be UTF-8. These limits give actionable unsupported-input diagnostics rather
than partial discovery. Generated/dependency directories are not instruction roots.

## Runtime policy

No per-project runner config is needed. Python evidence is `pyproject.toml`, root
`requirements.txt`/`requirements-dev.txt` or `.python-version`. Node evidence is
`package.json`, `.node-version` or `.nvmrc`. Mixed Python/Node roots and unknown
environments fail until their execution environment has explicit support. Setup
scripts, imports, package scripts and dependency resolution never run in preflight.

The initial global discovery policy advertises Python **3.12.0** and Node
**22.0.0** baselines, selecting lines `3.12` and `22` respectively. These are
static discovery targets, not a claim about installed runtimes. Run uses explicit
project configuration and the operator-provisioned native environment.
`requires-python`, `engines.node`, version files, and documented Runtime declarations
must all admit the selected baseline. Absence of a version constraint uses the
policy default and records that source. Constraints needing another minor/major
or a newer exact/minimum patch fail; extending this conservative policy requires
deliberate discovery-policy changes. Requirements are retained in the result.

The version subset is numeric major/minor/patch, equality/inequality, `>=`, `<=`,
`>`, `<`, and trailing `.*`/`.x` wildcards for equality. Python supports `~=` with
at least major/minor; Node supports `^`, `~`, and `||` alternatives. Commas/spaces
join simultaneous clauses. Unknown syntax anywhere fails, including an unsupported
alternative. Prereleases, named versions and arbitrary environment-manager syntax
are not guessed. `.nvmrc`/`.node-version` may have a leading `v`. Python numeric
equality compares padded versions; bare Node numbers select a prefix.

Node currently supports npm, optionally declared by `packageManager: "npm@<numeric
version>"`. Yarn/pnpm declarations or lockfiles fail. npm version declarations are
retained as source evidence, not capability-verified here. Python dependency files
and npm lockfiles are inventoried; they are not installed or resolved in M2.

Optional ordinary documentation can add constraints without a runner config:

```markdown
## Runtime

Python: >=3.11,<3.13
```

Every line under that exact heading must declare `Python:` or `Node:` with a range.
All declarations are combined with metadata, never used to override it.

## Verification declarations and conflicts

Any inventoried Markdown document can declare one exact `## Verification` section
containing one `sh`, `bash` or `shell` fenced block. Each nonblank/noncomment line
is one literal argv command. Shell operators, expansions, continuations and leading
environment assignments are diagnosed. Commands are recorded, never executed:

````markdown
## Verification

```sh
python -m pytest -q
python -m compileall src
```
````

All explicit declarations, including ancestor and scoped instructions, must agree
on the ordered argv list. Differing checks cause an `instructions.conflict` error;
no implicit instruction precedence or selection among conflicting declarations is
applied. To declare several required checks, use the same integrated list in the
relevant declarations. Runtime-family disagreements also fail; incompatible
version constraints fail as unsupported runtime evidence.

If there is no explicit declaration, a nonempty Node `scripts.test` yields
`["npm", "test"]` (npm's default no-test placeholder is rejected). Explicit checks
take precedence over this metadata fallback. Python needs an explicit declaration;
test filenames or a pytest dependency alone do not select a command. Missing checks
fail even when the roadmap is already complete. Malformed or duplicate JSON keys,
invalid TOML, multiple Verification sections, and unknown syntax fail.

Free-form AGENTS prose is inventoried and hashed for the implementing agent; it
does not control the deterministic runtime/check selectors. Arbitrary natural
language contradictions cannot be proven or reconciled by this scanner. They
require review before authorization; success here does not waive those instructions
or authorize any command. CI files are inventory only. Configure any required CI
verification explicitly for run; local discovery is not CI success.

## Limits of this evidence

Results describe a local working-tree read and can include uncommitted documents.
They are not an atomic snapshot or an approval record. No remote freshness, scope
authorization, sandbox compatibility, runtime installation, verification success,
service behavior or publication safety is claimed. The revised setup/run commands
use their own explicit configuration, checkpoints and Git boundary; they do not
import discovery JSON as authorization. Concurrent hostile filesystem changes are
outside this read-only inspection guarantee.
