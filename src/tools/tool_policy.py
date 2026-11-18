"""Central risk classification for WW tool execution.

This module is policy metadata only. Callers must enforce the returned policy;
unknown tools fail closed.
"""
from dataclasses import dataclass
from enum import StrEnum


class ToolRisk(StrEnum):
    READ_ONLY = "read_only"
    MUTATION = "mutation"
    EXECUTION = "execution"
    NETWORK = "network"
    DENY = "deny"


@dataclass(frozen=True)
class ToolPolicy:
    risk: ToolRisk
    remote_allowed: bool = False

    @property
    def requires_approval(self) -> bool:
        return self.risk in {
            ToolRisk.MUTATION,
            ToolRisk.EXECUTION,
            ToolRisk.NETWORK,
        }


_POLICIES = {
    "read_file": ToolPolicy(ToolRisk.READ_ONLY, remote_allowed=True),
    "list_dir": ToolPolicy(ToolRisk.READ_ONLY, remote_allowed=True),
    "doc_search": ToolPolicy(ToolRisk.READ_ONLY),
    "code_search": ToolPolicy(ToolRisk.READ_ONLY),
    "write_file": ToolPolicy(ToolRisk.MUTATION),
    "file_patch": ToolPolicy(ToolRisk.MUTATION),
    "git_tool": ToolPolicy(ToolRisk.MUTATION),
    "shell_exec": ToolPolicy(ToolRisk.EXECUTION),
    "url_fetch": ToolPolicy(ToolRisk.NETWORK),
}

_DENIED = ToolPolicy(ToolRisk.DENY)


def policy_for_tool(name: str) -> ToolPolicy:
    """Return the explicit policy for a tool; unknown names are denied."""
    return _POLICIES.get(name, _DENIED)


def remote_tool_allowed(name: str) -> bool:
    """Whether the tool belongs on the narrow remote read-only surface."""
    return policy_for_tool(name).remote_allowed
