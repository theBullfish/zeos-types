"""Zeos Wire Types — shared data models for the entire Zeos ecosystem."""

from .signal import Signal
from .score import Score
from .address import CfaAddress
from .device import DeviceProfile
from .telemetry import Telemetry
from .identity import Identity
from .vault_entry import VaultEntry
from .registry import ServiceEntry, RegistryClient
from . import zes
from . import spine_auth

# SpineAuthMiddleware requires fastapi — import only when available
try:
    from .spine_middleware import SpineAuthMiddleware
except ImportError:
    SpineAuthMiddleware = None  # type: ignore

__all__ = [
    "Signal",
    "Score",
    "CfaAddress",
    "DeviceProfile",
    "Telemetry",
    "Identity",
    "VaultEntry",
    "ServiceEntry",
    "RegistryClient",
    "zes",
    "spine_auth",
    "SpineAuthMiddleware",
]
