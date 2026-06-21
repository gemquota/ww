"""
WW Bridge — Configuration Management

Reads from config.yaml with environment variable overrides (WW_ prefix).
Provides a single Settings object consumed by gemini_bridge.py and submodules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GeminiCredentials(BaseSettings):
    secure_1psid: str = Field("", repr=False)
    secure_1psidts: str = Field("", repr=False)

    model_config = SettingsConfigDict(env_prefix="ww_gemini_credentials_", extra="allow")


class GeminiConfig(BaseSettings):
    timeout: int = 45
    max_retries: int = 3
    rate_limit_rpm: int = 10
    credentials: GeminiCredentials = GeminiCredentials()

    model_config = SettingsConfigDict(env_prefix="ww_gemini_", extra="allow")


class MemoryConfig(BaseSettings):
    max_tier_a: int = 20
    compress_threshold: int = 50
    session_name: str = "default"
    max_checkpoint_count: int = 20

    model_config = SettingsConfigDict(env_prefix="ww_memory_", extra="allow")

    @field_validator("max_checkpoint_count")
    @classmethod
    def validate_max_checkpoints(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("max_checkpoint_count must be between 1 and 100")
        return v


class DashboardConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"

    model_config = SettingsConfigDict(env_prefix="ww_dashboard_", extra="allow")


class PluginsConfig(BaseSettings):
    directory: str = "plugins"
    auto_load: bool = True

    model_config = SettingsConfigDict(env_prefix="ww_plugins_", extra="allow")


class LoggingConfig(BaseSettings):
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"

    model_config = SettingsConfigDict(env_prefix="ww_logging_", extra="allow")


def get_env(key: str, default: str = "") -> str:
    """Centralized environment variable access. Every getenv call should go through here."""
    import os
    return os.environ.get(key, default)


class Settings(BaseSettings):

    """Top-level WW Bridge configuration.
    
    Reads config.yaml by default, then applies env var overrides with WW_ prefix.
    """
    
    workspace: str = Field(".", description="Workspace root directory for file operations")
    data_dir: str = Field(".tel", description="Data directory for state files (relative to workspace)")
    session: str = Field("default", description="Session name for memory persistence")
    verbose: bool = Field(False, description="Enable verbose output mode")
    context_window: int = Field(128_000, description="Context window token limit for the LLM")
    policy: str = Field("on-request", description="Approval policy: always, on-request, or never")
    max_file_size_kb: int = Field(512, description="Maximum file size in KB for surgical reading")

    gemini: GeminiConfig = GeminiConfig()
    memory: MemoryConfig = MemoryConfig()
    dashboard: DashboardConfig = DashboardConfig()
    plugins: PluginsConfig = PluginsConfig()
    logging: LoggingConfig = LoggingConfig()

    model_config = SettingsConfigDict(
        env_prefix="ww_",
        env_nested_delimiter="__",
        extra="allow",
    )

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> "Settings":
        """Load settings from YAML file + env overrides."""
        path = path or Path(os.getenv("WW_CONFIG", "config.yaml"))
        yaml_path = Path(path)
        
        if yaml_path.is_file():
            with open(yaml_path) as f:
                yaml_data = yaml.safe_load(f) or {}
            return cls(**yaml_data)
        return cls()

    def resolve_workspace(self) -> Path:
        return Path(self.workspace).resolve()

    def get_data_path(self, subdir: str = "") -> Path:
        """Resolve a path within the data directory.
        
        Args:
            subdir: Optional subdirectory within data_dir (e.g., "sessions", "checkpoints")
            
        Returns:
            Absolute Path to the data directory or subdirectory.
        """
        root = self.resolve_workspace()
        data = root / self.data_dir
        if subdir:
            data = data / subdir
        data.mkdir(parents=True, exist_ok=True)
        return data

    @field_validator("workspace")
    @classmethod
    def validate_workspace(cls, v: str) -> str:
        p = Path(v)
        if not p.exists():
            import warnings
            warnings.warn(f"Workspace path '{v}' does not exist, will be created on first use.")
        return v

    @field_validator("context_window")
    @classmethod
    def validate_context_window(cls, v: int) -> int:
        if v < 1000:
            raise ValueError(f"Context window {v} is too small (minimum 1000)")
        if v > 2_000_000:
            raise ValueError(f"Context window {v} is too large (maximum 2,000,000)")
        return v

    @field_validator("policy")
    @classmethod
    def validate_policy(cls, v: str) -> str:
        valid = {"always", "on-request", "never"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid policy '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v.lower()

    @field_validator("max_file_size_kb")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        if v < 1 or v > 10240: # 10MB max
            raise ValueError("max_file_size_kb must be between 1 and 10240 (10MB)")
        return v

    def to_dict(self) -> dict:
        return self.model_dump()


# Module-level singleton (lazy loaded)
_settings: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """Get the global Settings singleton."""
    global _settings
    if _settings is None or reload:
        _settings = Settings.load()
    return _settings


def reload_settings() -> Settings:
    """Reload config from disk."""
    return get_settings(reload=True)
