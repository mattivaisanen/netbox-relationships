from django.utils.translation import gettext_lazy as _

from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem


def _add(link, permission):
    return (PluginMenuButton(link=link, title=_('Add'), icon_class='mdi mdi-plus-thick', permissions=[permission]),)


# Its own tab in the navigation bar, like "IPAM" or "Virtualization".
menu = PluginMenu(
    label=_('Relationships'),
    icon_class='mdi mdi-graph-outline',
    groups=(
        (_('Relationships'), (
            PluginMenuItem(
                link='plugins:netbox_relationships:relationship_list',
                link_text=_('Manual Relationships'),
                permissions=['netbox_relationships.view_relationship'],
                buttons=_add('plugins:netbox_relationships:relationship_add', 'netbox_relationships.add_relationship'),
            ),
            PluginMenuItem(
                link='plugins:netbox_relationships:link_list',
                link_text=_('All Links'),
                permissions=['netbox_relationships.view_relationship'],
            ),
            PluginMenuItem(
                link='plugins:netbox_relationships:logicalservice_list',
                link_text=_('Logical Services'),
                permissions=['netbox_relationships.view_logicalservice'],
                buttons=_add(
                    'plugins:netbox_relationships:logicalservice_add', 'netbox_relationships.add_logicalservice',
                ),
            ),
        )),
        (_('Analysis'), (
            PluginMenuItem(
                link='plugins:netbox_relationships:impact',
                link_text=_('Impact Analysis'),
                permissions=['netbox_relationships.view_relationship'],
            ),
            PluginMenuItem(
                link='plugins:netbox_relationships:servicemap',
                link_text=_('Service Map'),
                permissions=['netbox_relationships.view_logicalservice'],
            ),
        )),
        (_('Setup'), (
            PluginMenuItem(
                link='plugins:netbox_relationships:networktier_list',
                link_text=_('Network Tiers'),
                permissions=['netbox_relationships.view_networktier'],
                buttons=_add('plugins:netbox_relationships:networktier_add', 'netbox_relationships.add_networktier'),
            ),
            PluginMenuItem(
                link='plugins:netbox_relationships:relationshiptype_list',
                link_text=_('Relationship Types'),
                permissions=['netbox_relationships.view_relationshiptype'],
                buttons=_add(
                    'plugins:netbox_relationships:relationshiptype_add', 'netbox_relationships.add_relationshiptype',
                ),
            ),
        )),
    ),
)
