"""
Serves the JavaScript and CSS (Cytoscape.js, graph.js, addmany.js) from the
plugin's own folder.

They are not Django static files on purpose: static files only reach the
web server after `collectstatic`, which a plugin installed or updated in a
container often never gets. Served from here, a restart is all an update
needs. Browsers cache them; the plugin version in the address makes them
load again after an upgrade.

Vendored: cytoscape.min.js is Cytoscape.js 3.30.2, unchanged, from
https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js (MIT, see
LICENSE-cytoscape.txt). The other files are this plugin's own.
"""
import os

from django.http import FileResponse, Http404
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

FOLDER = os.path.join(os.path.dirname(__file__), 'assets')
FILES = {
    'cytoscape.min.js': 'text/javascript',
    'graph.js': 'text/javascript',
    'graph.css': 'text/css',
    'addmany.js': 'text/javascript',
}


@require_GET
@cache_control(public=True, max_age=7 * 24 * 3600)
def asset(request, name):
    if name not in FILES:
        raise Http404()
    return FileResponse(open(os.path.join(FOLDER, name), 'rb'), content_type=FILES[name])
