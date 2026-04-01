"""Configuration loading for Bloomberg MCP.

Loads FieldSet definitions from YAML config, falling back to
code-defined FieldSets if YAML is unavailable.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent
_FIELDSETS_YAML = _CONFIG_DIR / "fieldsets.yaml"

# Cached parsed config
_fieldsets_from_yaml: Optional[Dict[str, List[str]]] = None


def load_fieldsets_yaml() -> Dict[str, List[str]]:
    """Load FieldSet definitions from YAML config file.

    Returns:
        Dict mapping uppercase FieldSet names to lists of Bloomberg fields.
        Returns empty dict if YAML is missing or malformed.
    """
    global _fieldsets_from_yaml
    if _fieldsets_from_yaml is not None:
        return _fieldsets_from_yaml

    if not _FIELDSETS_YAML.exists():
        logger.debug("fieldsets.yaml not found at %s, using code defaults", _FIELDSETS_YAML)
        _fieldsets_from_yaml = {}
        return _fieldsets_from_yaml

    try:
        import yaml
    except ImportError:
        logger.debug("PyYAML not installed, using code defaults for FieldSets")
        _fieldsets_from_yaml = {}
        return _fieldsets_from_yaml

    try:
        with open(_FIELDSETS_YAML, "r") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            logger.warning("fieldsets.yaml is not a dict, ignoring")
            _fieldsets_from_yaml = {}
            return _fieldsets_from_yaml

        # Normalize keys to uppercase
        _fieldsets_from_yaml = {
            k.upper(): v for k, v in raw.items()
            if isinstance(v, list)
        }
        logger.info("Loaded %d FieldSets from fieldsets.yaml", len(_fieldsets_from_yaml))
        return _fieldsets_from_yaml

    except Exception as e:
        logger.warning("Error loading fieldsets.yaml: %s — using code defaults", e)
        _fieldsets_from_yaml = {}
        return _fieldsets_from_yaml


def reset_fieldsets_cache() -> None:
    """Reset cached YAML config (for testing)."""
    global _fieldsets_from_yaml
    _fieldsets_from_yaml = None
