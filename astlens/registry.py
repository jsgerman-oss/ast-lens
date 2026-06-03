"""Op registry: op name -> the module's ``compute_change`` (guarded/lazy).

The four write-side ops are built by *parallel* agents; only one
(``strip-trailing-ws``) is owned by the spine. The registry must therefore
tolerate any subset of the op modules being absent: a missing op module is
SKIPPED, never fatal, so one unfinished sibling never breaks the others.

Resolution is lazy. ``resolve(name)`` imports the backing module on demand and
caches the result. An import error (module not yet written, or it raises on
import) is captured and surfaced only when *that* op is requested — listing and
resolving other ops keeps working.

Each backing module must expose ``compute_change(file_path, args) -> dict|None``
per the shared contract. The registry validates that surface lazily and raises
a clear ``OpError`` if a present module is malformed.
"""

from __future__ import annotations

import importlib

__all__ = ["resolve", "available", "all_op_names", "OpError"]


class OpError(Exception):
    """Raised when a requested op is unknown, unavailable, or malformed."""


# Stable op name -> backing module path. Order is the canonical listing order.
# `strip-trailing-ws` is the spine's demo op (always present). The other three
# are produced by sibling agents; their modules may not exist yet, and the
# guarded import below makes their absence a non-event.
_REGISTRY: dict[str, str] = {
    "strip-trailing-ws": "astlens.ops.strip_trailing_ws",
    "fix-imports": "astlens.ops.fix_imports",
    "rename-symbol": "astlens.ops.rename_symbol",
    "extract-to-package": "astlens.ops.extract_to_package",
}

# Cache: op name -> compute_change callable (populated on first successful resolve).
_RESOLVED: dict[str, object] = {}


def all_op_names() -> list[str]:
    """Every registered op name, present or not, in canonical order."""
    return list(_REGISTRY.keys())


def _load(name: str):
    """Import a backing module and return its ``compute_change``.

    Raises OpError if the module is absent, fails to import, or does not expose
    a callable ``compute_change``.
    """
    module_path = _REGISTRY[name]
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        raise OpError(
            f"op '{name}' is registered but its module '{module_path}' is not "
            f"available (built by a sibling agent?): {exc}"
        ) from exc
    fn = getattr(mod, "compute_change", None)
    if not callable(fn):
        raise OpError(
            f"op '{name}' module '{module_path}' does not expose a callable "
            f"compute_change(file_path, args) -> dict|None"
        )
    return fn


def resolve(name: str):
    """Return the ``compute_change`` callable for op ``name``.

    Lazy + cached. Raises :class:`OpError` if the name is unknown or its module
    is unavailable/malformed. Resolving one op never imports the others, so an
    unfinished sibling op cannot break this one.
    """
    if name not in _REGISTRY:
        known = ", ".join(_REGISTRY)
        raise OpError(f"unknown op '{name}'. Registered ops: {known}")
    if name not in _RESOLVED:
        _RESOLVED[name] = _load(name)
    return _RESOLVED[name]


def available() -> dict[str, bool]:
    """Map each registered op name -> whether its module resolves right now.

    Probes by attempting a (cached) resolve and swallowing OpError, so it is
    safe to call when sibling op modules are still missing.
    """
    out: dict[str, bool] = {}
    for name in _REGISTRY:
        try:
            resolve(name)
            out[name] = True
        except OpError:
            out[name] = False
    return out
