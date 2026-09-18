"""Extra macro tools for FLDigi."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fltools")
except PackageNotFoundError:  # not installed, e.g. a bare source checkout
    __version__ = "0.1.0+dev"

__all__ = ["__version__"]
