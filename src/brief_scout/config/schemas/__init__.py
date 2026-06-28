"""Configuration schema module for future config schema extensions.

This module is reserved for Pydantic-based configuration schemas
that validate and type-check YAML configuration files at load time.

Planned extensions:
- AppConfigSchema: Root application configuration validator
- PromptTemplateSchema: Jinja2 prompt template validation
- ProviderConfigSchema: LLM provider configuration validator
"""

from __future__ import annotations
