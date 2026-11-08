"""Reads PLUGINS_CONFIG['netbox_relationships'], falling back to default_settings."""
from netbox.plugins import get_plugin_config

PLUGIN = 'netbox_relationships'


def get(name):
    return get_plugin_config(PLUGIN, name)


def derived_enabled(key):
    """True when the derived link kind `key` is switched on."""
    from . import NetBoxRelationshipsConfig
    defaults = NetBoxRelationshipsConfig.default_settings['derived']
    configured = get('derived') or {}
    return bool(configured.get(key, defaults.get(key, False)))


def depth(requested=None):
    """A traversal depth: the request's, else the default, never above max_depth."""
    try:
        value = int(requested) if requested not in (None, '') else int(get('default_depth'))
    except (TypeError, ValueError):
        value = int(get('default_depth'))
    return max(1, min(value, int(get('max_depth'))))
