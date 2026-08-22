"""Colosseum public API."""

from importlib import metadata

from . import config, database
from .decorators import (
    CommandResult,
    MeasurementSource,
    VerificationResult,
    command,
    measurement,
    verification,
)
from .plugins.namespace import LazyNamespaceProxy
from .results import endex

try:
    __version__ = metadata.version("colosseum-core")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"


def __getattr__(name: str) -> LazyNamespaceProxy:
    """Resolve plugin namespaces (for example ``col.acme.*``) after install."""
    if name.startswith("_"):
        raise AttributeError(name)
    return LazyNamespaceProxy(name)


__all__ = [
    "__version__",
    "config",
    "database",
    "command",
    "measurement",
    "verification",
    "CommandResult",
    "MeasurementSource",
    "VerificationResult",
    "endex",
]
