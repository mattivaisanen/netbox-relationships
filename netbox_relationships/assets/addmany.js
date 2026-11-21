/*
 * "Add several relationships" form: picking another object type reloads
 * the form with that type, so the object search and the list of allowed
 * relationship types fit it. Choices made so far travel in the address.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.querySelector('[data-nbr-addmany]');
    if (!form) { return; }

    function reload() {
      var q = new URLSearchParams();
      ['object', 'return_url'].forEach(function (name) {
        var field = form.elements[name];
        if (field && field.value) { q.set(name, field.value); }
      });
      var direction = form.querySelector('input[name="direction"]:checked');
      if (direction) { q.set('direction', direction.value); }
      var type = form.elements.target_type;
      if (type && type.value) { q.set('target_type', type.value); }
      window.location.search = q.toString();
    }

    var type = form.elements.target_type;
    if (type) { type.addEventListener('change', reload); }
    form.querySelectorAll('input[name="direction"]').forEach(function (radio) {
      radio.addEventListener('change', reload);
    });

    // Show the group fields only when "these back each other up" is ticked.
    var redundant = form.querySelector('input[name="redundant"][type="checkbox"]');
    var groupFields = form.querySelector('[data-nbr-group]');
    function toggle() { if (groupFields) { groupFields.hidden = !(redundant && redundant.checked); } }
    if (redundant) { redundant.addEventListener('change', toggle); }
    toggle();
  });
})();
