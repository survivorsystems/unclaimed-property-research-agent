from importlib.metadata import PackageNotFoundError, version as _pkg_version

from clearfront.public_sources.quarantine import install_quarantine

# Preserve upstream source, but prevent its collectors/SDK-backed entrypoints
# from loading in this adaptation. No environment key can grant approval.
install_quarantine()

try:
    __version__ = _pkg_version("clearfront")
except PackageNotFoundError:
    __version__ = "unknown"

version = __version__
