"""
Capability-centric tool registry.
Addresses V4-P1: Missing Capability Registry
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class Capability:
    """A capability that can be provided by one or more tool implementations."""
    name: str
    description: str
    provider_names: Set[str] = field(default_factory=set)


class CapabilityRegistry:
    """Maps capabilities to tool providers.
    
    Instead of calling Tool A directly, callers request a capability
    and the registry selects the appropriate provider.
    """
    
    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._providers: Dict[str, Callable] = {}
    
    def register_capability(self, name: str, description: str) -> Capability:
        """Register a capability that tools can provide."""
        cap = Capability(name=name, description=description)
        self._capabilities[name] = cap
        return cap
    
    def register_provider(self, capability_name: str, provider_name: str, fn: Callable) -> None:
        """Register a tool/function as a provider for a capability."""
        if capability_name not in self._capabilities:
            self._capabilities[capability_name] = Capability(
                name=capability_name, description=""
            )
        self._capabilities[capability_name].provider_names.add(provider_name)
        self._providers[provider_name] = fn
    
    def get_capability(self, name: str) -> Optional[Capability]:
        """Get capability metadata."""
        return self._capabilities.get(name)
    
    def list_capabilities(self) -> List[Dict[str, Any]]:
        """List all registered capabilities and their providers."""
        return [
            {"name": c.name, "description": c.description, "providers": list(c.provider_names)}
            for c in self._capabilities.values()
        ]
    
    def execute(self, capability_name: str, provider_name: Optional[str] = None, **kwargs) -> Any:
        """Execute a capability, optionally selecting a specific provider.
        
        If no provider is specified, uses the first available provider.
        """
        cap = self._capabilities.get(capability_name)
        if not cap:
            raise ValueError(f"Unknown capability: {capability_name}")
        
        providers = list(cap.provider_names)
        if not providers:
            raise ValueError(f"No providers for capability: {capability_name}")
        
        selected = provider_name or providers[0]
        fn = self._providers.get(selected)
        if not fn:
            raise ValueError(f"Provider '{selected}' not found for capability '{capability_name}'")
        
        return fn(**kwargs)
