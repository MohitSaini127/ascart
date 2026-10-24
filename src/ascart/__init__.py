"""ascart's public package information."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("ascart")
except PackageNotFoundError:
    # A source checkout can be imported before it is installed.
    __version__ = "unknown"
