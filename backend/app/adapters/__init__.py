"""Source-type parser adapters for TraceGraph."""

from app.adapters.auth import AuthAdapter
from app.adapters.base import ParserAdapter
from app.adapters.edr import EDRAdapter
from app.adapters.network import NetworkAdapter
from app.adapters.public_dataset import PublicDatasetAdapter
from app.adapters.siem import SIEMAdapter
from app.adapters.sysmon import SysmonAdapter


def register_default_adapters(registry=None):
    """Register all 6 default parser adapters into the provided or default registry."""
    if registry is None:
        from app.services.parser_registry import default_registry
        registry = default_registry

    adapters = [
        SIEMAdapter(),
        EDRAdapter(),
        SysmonAdapter(),
        AuthAdapter(),
        NetworkAdapter(),
        PublicDatasetAdapter(),
    ]
    for adapter in adapters:
        registry.register(adapter)
    return registry


__all__ = [
    "ParserAdapter",
    "SIEMAdapter",
    "EDRAdapter",
    "SysmonAdapter",
    "AuthAdapter",
    "NetworkAdapter",
    "PublicDatasetAdapter",
    "register_default_adapters",
]

