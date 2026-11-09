/*
 * Dependency graph for netbox-relationships.
 *
 * Reads the graph API (nodes and edges around one object) and draws it with
 * Cytoscape.js. The toolbar reloads it with another depth, direction or
 * layout. Click a node to highlight everything it needs and everything that
 * needs it; double-click to open it. No other libraries, nothing loaded from
 * the internet.
 */
(function () {
  'use strict';

  // Node fill and border per group, light and dark.
  var GROUPS = {
    business: ['#f1ebfb', '#6b4bb8', '#2d2340', '#a58be0'],
    application: ['#e8eefb', '#2f6fdf', '#1d2740', '#7aa2f0'],
    external: ['#f3f4f6', '#6b7280', '#2a2d33', '#9ca3af'],
    service: ['#e3f4f1', '#1f7a6b', '#17302c', '#5bbfab'],
    vm: ['#ffffff', '#5b6475', '#22262e', '#9aa3b2'],
    cluster: ['#ffffff', '#1d2330', '#22262e', '#d0d5dd'],
    chassis: ['#f2f7fc', '#3b82c4', '#1c2633', '#7fb1e0'],
    device: ['#f5f6f8', '#5b6475', '#2a2e36', '#9aa3b2'],
    circuit: ['#fff4e5', '#b26a00', '#33281a', '#e0a24a'],
    power: ['#fff1e8', '#e65100', '#36231a', '#ff8a50'],
    other: ['#ffffff', '#9aa3b2', '#22262e', '#6b7280'],
    hidden: ['#e5e7eb', '#9ca3af', '#30333a', '#5b6475']
  };

  function dark() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
  }

  function style() {
    var d = dark();
    var text = d ? '#e5e7eb' : '#1d2330';
    var rules = [
      {
        selector: 'node',
        style: {
          'shape': 'round-rectangle', 'width': 170, 'height': 46, 'label': 'data(display)',
          'text-wrap': 'wrap', 'text-max-width': 156, 'text-valign': 'center', 'font-size': 12,
          'color': text, 'border-width': 1.5, 'background-color': '#fff', 'border-color': '#9aa3b2'
        }
      },
      {selector: 'node[?root]', style: {'border-width': 3.5, 'border-color': '#2f6fdf'}},
      {
        selector: 'edge',
        style: {
          'curve-style': 'bezier', 'width': 1.5, 'line-color': 'data(color)', 'target-arrow-color': 'data(color)',
          'target-arrow-shape': 'triangle', 'arrow-scale': 0.9, 'label': 'data(label)', 'font-size': 10,
          'color': d ? '#c9d1de' : '#465063', 'text-background-color': d ? '#1f2633' : '#ffffff',
          'text-background-opacity': 0.9, 'text-background-padding': 2, 'text-rotation': 'autorotate'
        }
      },
      {
        // A virtual chassis drawn as a box around its members.
        selector: ':parent',
        style: {
          'shape': 'round-rectangle', 'text-valign': 'top', 'text-halign': 'center', 'text-margin-y': -4,
          'padding': 14, 'border-style': 'dashed', 'border-width': 1.5, 'font-weight': 600,
          'background-opacity': 0.35
        }
      },
      {selector: 'edge[?symmetric]', style: {'target-arrow-shape': 'none'}},
      {selector: 'edge[group != ""]', style: {'line-style': 'solid', 'width': 2.5, 'source-arrow-shape': 'none'}},
      {selector: 'edge[origin = "netbox"][group = ""]', style: {'line-style': 'dotted'}},
      {selector: 'edge[status = "planned"]', style: {'line-style': 'dashed', 'line-dash-pattern': [8, 5]}},
      {selector: 'edge[impact = "hard"][origin = "manual"]', style: {'width': 2.5}},
      {selector: '.nbr-faded', style: {'opacity': 0.18}},
      {selector: 'node.nbr-picked', style: {'border-width': 4, 'border-color': '#f59f00'}}
    ];
    Object.keys(GROUPS).forEach(function (group) {
      var c = GROUPS[group];
      rules.push({
        selector: 'node[group = "' + group + '"]',
        style: {'background-color': d ? c[2] : c[0], 'border-color': d ? c[3] : c[1]}
      });
    });
    return rules;
  }

  /*
   * Positions for the layered layout, top to bottom: what needs something
   * sits above it. Members of a virtual chassis are drawn inside its box and
   * take part through the box.
   *
   * 1. Layers: each node goes one row below the lowest thing that needs it
   *    (longest path), so chains read straight down. Peer and other
   *    symmetric links don't set rows; peers end up side by side.
   * 2. Order within a row: a few sweeps that move each node towards the
   *    average position of its neighbours, which removes most crossings.
   * 3. Rows are centred; a box is as wide as its members.
   */
  var NODE_W = 190, ROW_H = 130, MEMBER_W = 180;

  function layered(data, parentOf) {
    var top = data.nodes.filter(function (n) { return !parentOf[n.id]; }).map(function (n) { return n.id; });
    var lift = function (id) { return parentOf[id] || id; };
    var down = {}, up = {}, peers = {};
    top.forEach(function (id) { down[id] = []; up[id] = []; peers[id] = []; });
    data.edges.forEach(function (e) {
      var a = lift(e.source), b = lift(e.target);
      if (a === b || !(a in down) || !(b in down)) { return; }
      if (e.symmetric) { peers[a].push(b); peers[b].push(a); return; }
      down[a].push(b);
      up[b].push(a);
    });

    // 1. Longest-path layers, guarded against loops.
    var level = {};
    top.forEach(function (id) { level[id] = 0; });
    for (var round = 0; round < top.length; round++) {
      var moved = false;
      top.forEach(function (id) {
        down[id].forEach(function (t) {
          if (level[t] < level[id] + 1 && level[id] + 1 < top.length) { level[t] = level[id] + 1; moved = true; }
        });
      });
      if (!moved) { break; }
    }
    // A node with only peer links joins its peer's row.
    top.forEach(function (id) {
      if (!down[id].length && !up[id].length && peers[id].length) { level[id] = level[peers[id][0]]; }
    });

    var rows = {};
    top.forEach(function (id) { (rows[level[id]] = rows[level[id]] || []).push(id); });
    var keys = Object.keys(rows).map(Number).sort(function (a, b) { return a - b; });
    var width = function (id) { return Math.max(1, (data.children[id] || []).length) * (data.children[id] ? MEMBER_W : NODE_W); };

    // 2. Barycenter sweeps, down then up.
    var order = {};
    var place = function () {
      keys.forEach(function (k) { rows[k].forEach(function (id, i) { order[id] = i; }); });
    };
    place();
    var mean = function (list) {
      var known = list.filter(function (id) { return id in order; });
      if (!known.length) { return null; }
      return known.reduce(function (sum, id) { return sum + order[id]; }, 0) / known.length;
    };
    for (var sweep = 0; sweep < 4; sweep++) {
      var seq = sweep % 2 ? keys.slice().reverse() : keys;
      seq.forEach(function (k) {
        var scored = rows[k].map(function (id) {
          var m = mean(sweep % 2 ? down[id].concat(peers[id]) : up[id].concat(peers[id]));
          return {id: id, score: m === null ? order[id] : m};
        });
        scored.sort(function (a, b) { return a.score - b.score; });
        rows[k] = scored.map(function (x) { return x.id; });
      });
      place();
    }

    // 3. Coordinates.
    var positions = {};
    keys.forEach(function (k, row) {
      var total = rows[k].reduce(function (sum, id) { return sum + width(id); }, 0);
      var x = -total / 2;
      rows[k].forEach(function (id) {
        var w = width(id);
        var cx = x + w / 2;
        var members = data.children[id];
        if (members) {
          members.forEach(function (m, i) {
            positions[m] = {x: cx + (i - (members.length - 1) / 2) * MEMBER_W, y: row * ROW_H};
          });
        } else {
          positions[id] = {x: cx, y: row * ROW_H};
        }
        x += w;
      });
    });
    return positions;
  }

  function layoutFor(name, data) {
    if (name === 'force') {
      return {name: 'cose', animate: false, nodeRepulsion: 9000, idealEdgeLength: 120, padding: 30};
    }
    if (name === 'concentric') {
      return {
        name: 'concentric', animate: false, padding: 30, minNodeSpacing: 30,
        concentric: function (node) { return 100 - node.data('hops'); }, levelWidth: function () { return 1; }
      };
    }
    // Layered: what an object needs sits below it, what needs it above.
    return {name: 'preset', positions: layered(data, data.parentOf), fit: true, padding: 30, animate: false};
  }

  /*
   * Cytoscape elements. A virtual chassis and its members become a box with
   * the members inside, instead of a node with "runs on" links to each.
   * Fills data.parentOf and data.children for the layout.
   */
  function elements(data) {
    var ids = {};
    data.nodes.forEach(function (n) { ids[n.id] = true; });
    data.parentOf = {};
    data.children = {};
    var edges = data.edges.filter(function (e) {
      if (e.kind === 'virtual_chassis' && ids[e.source] && ids[e.target] && !data.parentOf[e.target]) {
        data.parentOf[e.target] = e.source;
        (data.children[e.source] = data.children[e.source] || []).push(e.target);
        return false;
      }
      return true;
    });
    var nodes = data.nodes.map(function (n) {
      var display = n.label + (n.kind ? '\n' + n.kind : '');
      var extra = {display: display};
      if (data.parentOf[n.id]) { extra.parent = data.parentOf[n.id]; extra.display = n.label; }
      return {data: Object.assign({}, n, extra)};
    });
    edges = edges.map(function (e) {
      var label = e.label + (e.link_count > 1 ? ' \u00d7' + e.link_count : '') + (e.note && e.origin === 'manual' ? ': ' + e.note : '');
      return {data: Object.assign({}, e, {color: '#' + (e.color || '6b7690'), label: label, group: e.group || ''})};
    });
    return nodes.concat(edges);
  }

  function download(name, type, content) {
    var link = document.createElement('a');
    link.href = typeof content === 'string' ? URL.createObjectURL(new Blob([content], {type: type})) : content;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function mermaid(data) {
    var ids = {};
    var lines = ['flowchart TD'];
    data.nodes.forEach(function (n, i) {
      ids[n.id] = 'n' + i;
      lines.push('  n' + i + '["' + String(n.label).replace(/"/g, "'") + '"]');
    });
    data.edges.forEach(function (e) {
      var arrow = e.symmetric ? ' --- ' : (e.origin === 'netbox' ? ' -.-> ' : ' --> ');
      lines.push('  ' + ids[e.source] + arrow.replace(/ $/, '') + '|' + e.label + '| ' + ids[e.target]);
    });
    return lines.join('\n') + '\n';
  }

  function hoverCard(container) {
    var card = document.createElement('div');
    card.className = 'nbr-hover';
    card.hidden = true;
    container.appendChild(card);
    return card;
  }

  function init(container) {
    var form = document.querySelector('[data-nbr-toolbar]');
    var status = document.getElementById('nbr-status');
    var card = hoverCard(container);
    var cy = null;
    var data = null;

    function params() {
      var q = new URLSearchParams();
      q.append('object', container.dataset.object);
      q.append('depth', form.elements.depth.value);
      q.append('direction', form.elements.direction.value);
      q.append('derived', form.elements.derived.checked ? 'true' : 'false');
      return q;
    }

    function draw() {
      if (cy) { cy.destroy(); }
      cy = cytoscape({
        container: container, elements: elements(data), style: style(),
        layout: layoutFor(form.elements.layout.value, data),
        wheelSensitivity: 0.25, minZoom: 0.15, maxZoom: 2.5
      });
      cy.on('tap', 'node', function (evt) {
        var node = evt.target;
        var chain = node.union(node.successors()).union(node.predecessors());
        cy.elements().addClass('nbr-faded').removeClass('nbr-picked');
        chain.removeClass('nbr-faded');
        node.addClass('nbr-picked');
      });
      cy.on('tap', function (evt) {
        if (evt.target === cy) { cy.elements().removeClass('nbr-faded nbr-picked'); }
      });
      cy.on('dbltap', 'node', function (evt) {
        var url = evt.target.data('url');
        if (url) { window.location.href = url; }
      });
      cy.on('mouseover', 'node', function (evt) {
        var n = evt.target.data();
        var pos = evt.target.renderedPosition();
        card.textContent = '';
        var title = document.createElement('strong');
        title.textContent = n.label;
        card.appendChild(title);
        [n.kind, n.status ? 'Status: ' + n.status : null, n.hops ? n.hops + ' hop(s) away' : 'This object']
          .filter(Boolean).forEach(function (line) {
            var div = document.createElement('div');
            div.textContent = line;
            card.appendChild(div);
          });
        card.style.left = (pos.x + 95) + 'px';
        card.style.top = Math.max(0, pos.y - 30) + 'px';
        card.hidden = false;
      });
      cy.on('mouseout', 'node', function () { card.hidden = true; });
    }

    function load() {
      status.textContent = '…';
      fetch(container.dataset.api + '?' + params().toString(), {
        credentials: 'same-origin', headers: {'Accept': 'application/json'}
      }).then(function (response) {
        if (!response.ok) { throw new Error(response.status + ' ' + response.statusText); }
        return response.json();
      }).then(function (json) {
        data = json;
        draw();
        var text = json.nodes.length + ' objects, ' + json.edges.length + ' links.';
        if (json.edges.length === 0) { text = container.dataset.empty; }
        if (json.truncated) { text += ' ' + container.dataset.truncated; }
        status.textContent = text;
      }).catch(function (error) {
        status.textContent = String(error);
      });
    }

    form.addEventListener('change', function (evt) {
      if (evt.target.name === 'layout' && data) { draw(); } else { load(); }
    });
    form.addEventListener('submit', function (evt) { evt.preventDefault(); });
    form.querySelectorAll('[data-nbr-action]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (!cy || !data) { return; }
        var action = button.dataset.nbrAction;
        if (action === 'fit') { cy.fit(undefined, 30); }
        if (action === 'png') { download('dependency-graph.png', 'image/png', cy.png({full: true, scale: 2, bg: dark() ? '#1f2633' : '#ffffff'})); }
        if (action === 'json') { download('dependency-graph.json', 'application/json', JSON.stringify(data, null, 2)); }
        if (action === 'mermaid') { download('dependency-graph.mmd', 'text/plain', mermaid(data)); }
      });
    });
    // Redraw in the new colours when NetBox's theme switches.
    new MutationObserver(function () { if (cy) { cy.style(style()); } })
      .observe(document.documentElement, {attributes: true, attributeFilter: ['data-bs-theme']});

    load();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('nbr-graph');
    if (container && window.cytoscape) { init(container); }
  });
})();
