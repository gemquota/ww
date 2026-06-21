"""
Agent Profile Manifest — captures agent configuration for reproducibility.
Addresses V4-P3: Agent Identity Drift
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable


@dataclass
class AgentProfileManifest:
    """Captures the full agent configuration for reproducibility.
    
    Two installations with the same manifest should produce the same
    agent behavior, even across different bridge versions.
    """
    
    # Template versions
    template_versions: Dict[str, str] = field(default_factory=dict)
    
    # Plugin set with hash
    plugins: List[Dict[str, str]] = field(default_factory=list)
    
    # Memory/context policies
    memory_max_tier_a: int = 20
    compress_threshold: int = 50
    
    # Tool policies
    tool_allowlist: List[str] = field(default_factory=list)
    tool_denylist: List[str] = field(default_factory=list)
    
    # Agent specs (name -> hash of agent spec file)
    agent_spec_hashes: Dict[str, str] = field(default_factory=dict)
    
    # Workspace state
    workspace_hash: str = ""
    
    # Metadata
    bridge_version: str = ""
    created_at: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentProfileManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))
    
    @classmethod
    def load(cls, path: Path) -> "AgentProfileManifest":
        return cls.from_dict(json.loads(path.read_text()))
    
    def compute_fingerprint(self) -> str:
        """Compute a hash of the entire manifest for quick identity comparison."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()
    
    def compare(self, other: "AgentProfileManifest") -> Dict[str, Any]:
        """Compare two manifests and return differences."""
        diff = {}
        for key in self.__dataclass_fields__:
            a = getattr(self, key)
            b = getattr(other, key)
            if a != b:
                diff[key] = {"expected": a, "actual": b}
        return diff
