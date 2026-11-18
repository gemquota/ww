"""Central risk classification for WW tool execution.

Policy names are canonical registry names. Unknown tools fail closed.
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


# Model-facing aliases are normalized before policy lookup.
_TOOL_ALIASES = {
    "git": "git_tool",
    "write": "write_file",
    "read": "read_file",
    "list": "list_dir",
    "shell": "shell_exec",
    "search": "code_search",
    "replace": "file_patch",
    "fetch": "url_fetch",
    "doc": "doc_search",
}


_POLICIES = {
    "read_file": ToolPolicy(ToolRisk.READ_ONLY, remote_allowed=True),
    "list_dir": ToolPolicy(ToolRisk.READ_ONLY, remote_allowed=True),
    "doc_search": ToolPolicy(ToolRisk.READ_ONLY),
    "code_search": ToolPolicy(ToolRisk.READ_ONLY),
    "request_clarification": ToolPolicy(ToolRisk.READ_ONLY),
    "write_file": ToolPolicy(ToolRisk.MUTATION),
    "file_patch": ToolPolicy(ToolRisk.MUTATION),
    "git_tool": ToolPolicy(ToolRisk.MUTATION),
    "shell_exec": ToolPolicy(ToolRisk.EXECUTION),
    "url_fetch": ToolPolicy(ToolRisk.NETWORK),
}

_DENIED = ToolPolicy(ToolRisk.DENY)


def canonical_tool_name(name: str) -> str:
    """Normalize a model-facing alias to its registry policy name."""
    return _TOOL_ALIASES.get(name, name)


def policy_for_tool(name: str) -> ToolPolicy:
    """Return the explicit policy for a known tool; unknown names are denied."""
    return _POLICIES.get(canonical_tool_name(name), _DENIED)


def remote_tool_allowed(name: str) -> bool:
    """Whether the tool belongs on the narrow remote read-only surface."""
    return policy_for_tool(name).remote_allowed
