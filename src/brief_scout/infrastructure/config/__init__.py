"""Configuration infrastructure adapters.

Provides configuration loading implementations that conform to the
ConfigurationPort Protocol.
"""

from brief_scout.infrastructure.config.yaml_config_adapter import YAMLConfigAdapter

__all__ = [
    "YAMLConfigAdapter",
]
