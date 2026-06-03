# ast-lens

**Outline-first reading for Gas City agents.** A self-contained gc pack that lets
LLM agents read a compact Markdown *structural outline* of a source file instead
of consuming the whole file — cutting the "read tax" by ~75–98% on large files.

Clean-room implementation of the read side of *"The AST as LLM Lens"*
([blackrim-ast-paper](https://github.com/jsgerman-oss/research/tree/main/blackrim-ast-paper)),
built straight from the paper's §5 algorithm + appendix. It does **not** import or
depend on Blackrim's `gt`.

## What's in the box

| Layer | File | Paper § |
|-------|------|---------|
| **Emitter** | `bin/outline` → `bin/outline.py` | §5, App B/C/D |
| **Skill** (agent-facing) | `skills/read-with-outline/SKILL.md` | §4.2 |
| **Prompt fragment** (system-prompt discipline) | `template-fragments/read-with-outline.template.md` | §4.3 |
| **PreToolUse hook** (auto-prepend on `Read`) | `overlay/per-provider/claude/.claude/settings.json` + `hooks/outline-on-read.sh` | §4.1 |
| **Tests** | `tests/` (44, behavioral) | §5.3/§5.4 contracts |

These are the paper's "one emitter, three surfaces" plus the three discipline
layers (hook, skill, CLAUDE.md instruction).

## The emitter

`bin/outline <file>` prints a Markdown outline: header (`# name (LoC, N decls)`),
sanitised package doc, imports, types, and functions — every declaration carrying
an `L<start>–<end>` anchor so an agent can `Read offset/limit` a specific body.
Supports **Go, Python, TypeScript, JavaScript** (canonical `tree-sitter` + per-grammar
packages). It is a pure, stateless, read-only function and degrades to **empty
output (passthrough)** for files < 200 LoC, unsupported types, an `outline:skip`
comment, a missing parser, or any parse error — so it can never break a `Read`.

Measured on real files: **94–98% token savings** (TS/Go/Python, 450–1400 LoC).

```bash
./setup.sh                       # one-time: build the venv (tree-sitter + grammars)
./bin/outline path/to/file.ts    # Markdown outline (silent if < 200 LoC)
./bin/outline --format json f.go
```

Config (env or flags): `--budget` (default 300 tokens), `--threshold` (default 200 LoC).

## Install & wire into a city

```bash
# 1. Vendor or import the pack, then build the emitter venv:
packs/ast-lens/setup.sh

# 2. Import it in city.toml (or `gc import add ./packs/ast-lens`):
#    [imports.ast-lens]
#    source = "./packs/ast-lens"

# 3. (recommended) opt the discipline fragment into every agent prompt:
#    global_fragments = [ ..., "read-with-outline" ]
```

The `read-with-outline` skill and the Claude `PreToolUse` overlay are picked up by
convention — gc deep-merges the overlay's hooks into the projected Claude settings
(it does not overwrite the core hooks).

**Escape hatches:** `BLACKRIM_DISABLE_OUTLINE_HOOK=1` disables the hook; `outline:skip`
in a file's first lines skips that file; `--threshold` raises the LoC floor.

## Caveats (honest)

- **Token budget (300) is a soft target.** Public-heavy files (e.g. a 51-class test
  file) exceed it — the truncation precedence (§5.3) never drops *public* top-level
  decls. This matches the paper's "conformance is an empirical claim."
- **Activation is deliberate.** The PreToolUse hook fires on *every* `Read` once
  enabled. Validate the overlay materialization path (`$CLAUDE_PROJECT_DIR/packs/ast-lens/...`)
  on a scratch city / single rig before enabling town-wide — see
  `docs/hook-projection-findings.md`.
- **Block-mode not implemented.** Warn-mode only (the paper's 80%-adoption → block
  escalation is future work).
- Multi-line signatures truncate to their first line; the significance pass is light.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q     # 44 behavioral tests
```

They validate the paper's *contracts* (passthrough, schema shape, line-span anchors,
public/private, sanitisation, compression) — not byte-equality with any other tool.
