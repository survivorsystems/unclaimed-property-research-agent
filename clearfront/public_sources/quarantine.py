"""Quarantine inherited collectors before their modules or SDKs are loaded.

This is an application routing guard, not a sandbox for hostile Python code.
There is intentionally no environment-variable switch to turn it off.
"""

from importlib.abc import MetaPathFinder
import sys


class LegacyResearchDisabled(ImportError):
    """A preserved upstream entrypoint cannot be used by this adaptation."""


QUARANTINED_MODULES = frozenset({
    "clearfront.tools", "clearfront.agent", "clearfront.cli", "clearfront.repl",
    "clearfront.web_server", "clearfront.mcp_server", "clearfront.pivot",
    "clearfront.multi_target", "clearfront.serp", "clearfront.brightdata",
    "clearfront.utils",
})


def is_quarantined_module(name: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".")
               for prefix in QUARANTINED_MODULES)


class _LegacyGuard(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if is_quarantined_module(fullname):
            # No targets, arguments, credentials, or raw exception data in errors.
            raise LegacyResearchDisabled(
                "Inherited research entrypoints are disabled. "
                "Use the approved-source dispatcher; no live sources are approved by default."
            )
        return None


def install_quarantine() -> None:
    if not any(isinstance(finder, _LegacyGuard) for finder in sys.meta_path):
        sys.meta_path.insert(0, _LegacyGuard())
