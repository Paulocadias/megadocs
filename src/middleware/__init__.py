"""
MegaDoc Middleware Package

Provides cross-cutting concerns for request handling:
- xray: Request tracing and observability
"""

from .xray import xray_trace, update_xray_from_gateway, XRayTrace

__all__ = ['xray_trace', 'update_xray_from_gateway', 'XRayTrace']
