"""
Versioned Prompt Template System.

Provides structured, versioned templates for prompt construction with
slot-filling validation and automatic logging for offline evaluation.
"""

from __future__ import annotations

import json
import re
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable


class TemplateError(Exception):
    """Raised when a template cannot be rendered."""
    pass


class PromptTemplate:
    """A versioned prompt template with slot-filling validation.
    
    Templates use {slot_name} syntax for variable substitution.
    Required slots are validated at render time.
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        template: str,
        description: str = "",
        required_slots: Optional[Set[str]] = None,
        optional_slots: Optional[Set[str]] = None,
        tags: Optional[List[str]] = None,
    ):
        self.name = name
        self.version = version
        self.template = template
        self.description = description
        self.required_slots = required_slots or set()
        self.optional_slots = optional_slots or set()
        self.tags = tags or []
        self._slot_pattern = re.compile(r"\{(\w+)\}")
    
    def render(self, **kwargs) -> str:
        """Fill the template with provided values.
        
        Validates that all required slots are provided and that
        no unknown slots are used.
        
        Args:
            **kwargs: Slot values to substitute.
            
        Returns:
            Rendered template string.
            
        Raises:
            TemplateError: If required slots are missing.
        """
        missing = self.required_slots - set(kwargs.keys())
        if missing:
            raise TemplateError(
                f"Template '{self.name}' v{self.version}: "
                f"missing required slots: {', '.join(sorted(missing))}"
            )
        
        # Find all slots in the template
        template_slots = set(self._slot_pattern.findall(self.template))
        unknown = set(kwargs.keys()) - template_slots
        if unknown:
            raise TemplateError(
                f"Template '{self.name}' v{self.version}: "
                f"unknown slots provided: {', '.join(sorted(unknown))}"
            )
        
        return self.template.format(**kwargs)
    
    def extract_slots(self) -> Set[str]:
        """Extract all slot names from the template."""
        return set(self._slot_pattern.findall(self.template))
    
    def validate(self) -> List[str]:
        """Validate template structure. Returns list of warnings."""
        warnings = []
        template_slots = self.extract_slots()
        
        # Check for unused required slots
        unused = self.required_slots - template_slots
        if unused:
            warnings.append(
                f"Required slots not found in template: {', '.join(sorted(unused))}"
            )
        
        # Check for missing required slots
        missing_required = template_slots - self.required_slots - self.optional_slots
        if missing_required:
            warnings.append(
                f"Slots in template not declared as required or optional: "
                f"{', '.join(sorted(missing_required))}"
            )
        
        return warnings


import hashlib
import json


class PromptTemplateRegistry:
    """Registry of versioned prompt templates with auto-logging."""
    
    def __init__(self, log_dir: Optional[Path] = None):
        self._templates: Dict[str, PromptTemplate] = {}
        self._rendered: List[Dict[str, Any]] = []
        self._log_dir = log_dir
        self._template_hashes: Dict[str, str] = {}
    
    def _compute_hash(self, template: PromptTemplate) -> str:
        """Compute SHA-256 hash of a template for integrity checking."""
        data = f"{template.name}:{template.version}:{template.template}".encode()
        return hashlib.sha256(data).hexdigest()
    
    def register(self, template: PromptTemplate) -> None:
        """Register a template, storing its hash for integrity verification."""
        self._templates[template.name] = template
        self._template_hashes[template.name] = self._compute_hash(template)
    
    def verify_integrity(self, name: str) -> bool:
        """Verify that a template hasn't been modified since registration.
        Returns True if the template is unchanged, False if modified or unknown.
        """
        template = self.get(name)
        if template is None:
            return False
        expected = self._template_hashes.get(name)
        if expected is None:
            return False
        actual = self._compute_hash(template)
        return actual == expected
    
    def check_all_integrity(self) -> Dict[str, bool]:
        """Check integrity of all registered templates.
        Returns dict of {template_name: is_intact}.
        """
        return {name: self.verify_integrity(name) for name in self._templates}
    
    def register(self, template: PromptTemplate) -> None:
        """Register a template, replacing any previous version with the same name."""
        self._templates[template.name] = template
    
    def get(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name."""
        return self._templates.get(name)
    
    def render(self, name: str, log: bool = True, **kwargs) -> str:
        """Render a template by name with automatic logging.
        
        Args:
            name: Template name.
            log: Whether to log the rendered output.
            **kwargs: Slot values.
            
        Returns:
            Rendered template string.
        """
        template = self.get(name)
        if template is None:
            raise TemplateError(f"Template '{name}' not found in registry")
        
        result = template.render(**kwargs)
        
        if log:
            self._rendered.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "template_name": name,
                "template_version": template.version,
                "slots": kwargs,
                "rendered": result,
            })
            self._flush_log()
        
        return result
    
    def _flush_log(self) -> None:
        """Write rendered templates to disk for offline evaluation."""
        if not self._log_dir:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._log_dir / "prompt_log.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(self._rendered[-1]) + "\n")
    
    def get_history(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get render history, optionally filtered by template name."""
        if name:
            return [r for r in self._rendered if r["template_name"] == name]
        return list(self._rendered)
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """List all registered templates with metadata."""
        return [
            {
                "name": t.name,
                "version": t.version,
                "description": t.description,
                "required_slots": list(t.required_slots),
                "optional_slots": list(t.optional_slots),
                "tags": t.tags,
            }
            for t in self._templates.values()
        ]


# ── Default Templates ─────────────────────────────────────────

DEFAULT_TEMPLATES = [
    PromptTemplate(
        name="user_query",
        version="1.0",
        description="Standard user query with optional memory context",
        template="""{memory_context}{user_input}""",
        required_slots={"user_input"},
        optional_slots={"memory_context"},
        tags=["core", "query"],
    ),
    PromptTemplate(
        name="user_query_with_context",
        version="1.0",
        description="User query with persistent context prefix",
        template="""[PERSISTENT CONTEXT]
{memory_context}

[USER QUERY]
{user_input}""",
        required_slots={"memory_context", "user_input"},
        tags=["core", "query"],
    ),
    PromptTemplate(
        name="agent_priming",
        version="1.0",
        description="Agent session priming with system instructions",
        template="""SYSTEM INSTRUCTIONS:
{spec_text}

PROJECT INSTRUCTIONS (AGENTS.md):
{agents_instructions}

AGENT REGISTRY:
{agent_registry}

WORKSPACE CONTEXT:
{workspace_context}

TOOL PROTOCOLS:
{base_instructions}

INITIALIZATION: Start session. Execute tasks immediately using tool blocks.""",
        required_slots={"spec_text", "agents_instructions", "agent_registry", "workspace_context", "base_instructions"},
        tags=["agent", "priming"],
    ),
    PromptTemplate(
        name="agent_task",
        version="1.0",
        description="Delegate a task to a specialized agent",
        template="""TASK: {task}""",
        required_slots={"task"},
        tags=["agent", "delegation"],
    ),
    PromptTemplate(
        name="health_check",
        version="1.0",
        description="Simple ping query for health check",
        template="Respond with only the word OKAY.",
        tags=["system", "health"],
    ),
]


def create_default_registry(log_dir: Optional[Path] = None) -> PromptTemplateRegistry:
    """Create a registry populated with default templates."""
    registry = PromptTemplateRegistry(log_dir=log_dir)
    for t in DEFAULT_TEMPLATES:
        registry.register(t)
    return registry
