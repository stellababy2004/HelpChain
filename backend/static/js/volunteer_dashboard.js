// Volunteer dashboard JS (moved from inline template). Expects window.HC config object.
(function () {
  var userLocale = (window.HC && window.HC.current_locale) || 'bg';
  var priorityLabels = (window.HC && window.HC.priorityLabels) || { urgent: 'Спешна', high: 'Висока', medium: 'Средна', low: 'Ниска' };
  var strings = (window.HC && window.HC.strings) || {};
  var currentUserId = (window.HC && window.HC.current_user_id) || null;

  var availableTasks = [];
  var filteredTasks = [];
  var activePriorityFilter = '';
  var activeSort = 'recent';

  document.addEventListener('DOMContentLoaded', function () {
    initializeDashboard();
    // Try to auto-fill coordinates on load if fields are empty
    try {
      // Delay slightly to allow DOM inputs to be present
      setTimeout(function () {
        autoFillCoordinatesIfEmpty();
      }, 300);
    } catch (e) {
      console.warn('Auto-fill coordinates initialization failed', e);
    }
  });

  function initializeDashboard() {
    loadAvailableTasks();
    setupSearchAndFilter();
    setupAvailableTaskActions();
    setupActiveTaskActions();
    initializeProgressIndicators();
  }

  async function loadAvailableTasks() {
    try {
      var resp = await fetch('/api/tasks?status=open&limit=10');
      var data = await resp.json();
      if (!data || data.success === false) {
        showNotification(strings.error_loading_tasks || 'Error loading tasks', 'danger');
        return;
      }
      availableTasks = Array.isArray(data.tasks) ? data.tasks : [];
      filteredTasks = sortTasks(availableTasks.slice(), activeSort);
      updateTaskSummary(filteredTasks);
      updatePriorityCounts(availableTasks);
      renderAvailableTasks(filteredTasks);
    } catch (err) {
      console.error('Error loading tasks:', err);
      showNotification(strings.error_connecting || 'Server connection error', 'danger');
    }
  }

  function updateTaskSummary(tasks) {
    var summary = tasks.reduce(function (acc, task) {
      var priority = (task.priority || 'low').toLowerCase();
      acc.all += 1;
      acc[priority] = (acc[priority] || 0) + 1;
      return acc;
    }, { all: 0, urgent: 0, high: 0, medium: 0, low: 0 });

    document.querySelectorAll('[data-task-summary]').forEach(function (node) {
      var key = node.dataset.taskSummary;
      node.textContent = summary[key] || 0;
    });
  }

  function updatePriorityCounts(tasks) {
    var counts = tasks.reduce(function (acc, task) {
      var priority = (task.priority || '').toLowerCase();
      acc.all += 1;
      if (priority) acc[priority] = (acc[priority] || 0) + 1;
      return acc;
    }, { all: 0 });

    document.querySelectorAll('[data-priority-count]').forEach(function (badge) {
      var key = badge.dataset.priorityCount;
      var value = key === 'all' ? counts.all : counts[key] || 0;
      badge.textContent = value;
    });
  }

  function renderAvailableTasks(tasks) {
    var container = document.getElementById('availableTasksContainer');
    if (!container) return;
    if (!tasks.length) {
      container.innerHTML = '\n      <div class="empty-state">\n        <div class="empty-icon">\n          <i class="fas fa-search"></i>\n        </div>\n        <h5 class="empty-title">' + (strings.no_tasks_found || 'No tasks found') + '</h5>\n        <p class="empty-description">' + (strings.try_other_filters || 'Try different filters.') + '</p>\n      </div>\n    ';
      return;
    }

    var cards = tasks.map(function (task) {
      var createdAt = task.created_at ? new Date(task.created_at).toLocaleDateString(userLocale || 'bg-BG') : '';
      var duration = task.estimated_hours ? (task.estimated_hours + (strings.hours_suffix || 'ч')) : (strings.no_info || 'N/A');
      var location = task.location_text || (strings.no_location || 'No location');
      var description = task.description || (strings.no_description || 'No description');
      var priority = (task.priority || 'low').toLowerCase();

      return '\n      <div class="task-card">\n        <div class="task-header">\n          <div class="flex-grow-1">\n            <h5 class="task-title">' + (task.title || '') + '</h5>\n            <div class="task-meta">\n              <span><i class="fas fa-map-marker-alt"></i>' + location + '</span>\n              <span><i class="fas fa-calendar"></i>' + createdAt + '</span>\n              <span><i class="fas fa-clock"></i>' + duration + '</span>\n            </div>\n          </div>\n          <span class="priority-badge priority-' + priority + '">\n            ' + (priorityLabels[priority] || priority) + '\n          </span>\n        </div>\n\n        <p class="task-description">' + description + '</p>\n\n        <div class="task-actions">\n          <button class="btn btn-outline-info btn-task js-view-task" data-task-id="' + (task.id || '') + '">\n            <i class="fas fa-eye me-1"></i>' + (strings.details || 'Details') + '\n          </button>\n          <button class="btn btn-primary btn-task js-accept-task" data-task-id="' + (task.id || '') + '">\n            <i class="fas fa-hand-paper me-1"></i>' + (strings.accept || 'Accept') + '\n          </button>\n        </div>\n      </div>\n    ';
    }).join('');

    container.innerHTML = cards;
  }

  function setupSearchAndFilter() {
    var searchInput = document.getElementById('taskSearch');
    var filterSelect = document.getElementById('taskFilter');
    var sortSelect = document.getElementById('taskSort');
    var priorityPills = Array.from(document.querySelectorAll('[data-priority-pill]'));

    var applyFilters = function () {
      var term = (searchInput && searchInput.value || '').toLowerCase();
      var priority = activePriorityFilter || (filterSelect && filterSelect.value) || '';

      filteredTasks = availableTasks.filter(function (task) {
        var titleMatch = task.title ? task.title.toLowerCase().includes(term) : false;
        var descriptionMatch = task.description ? task.description.toLowerCase().includes(term) : false;
        var matchesSearch = term ? (titleMatch || descriptionMatch) : true;
        var matchesPriority = priority ? ((task.priority || '').toLowerCase() === priority) : true;
        return matchesSearch && matchesPriority;
      });

      filteredTasks = sortTasks(filteredTasks, activeSort);
      updateTaskSummary(filteredTasks);
      renderAvailableTasks(filteredTasks);
    };

    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (filterSelect) filterSelect.addEventListener('change', function (event) { activePriorityFilter = event.target.value; priorityPills.forEach(function (pill) { var pillPriority = pill.dataset.priorityPill || ''; pill.classList.toggle('active', pillPriority === activePriorityFilter); }); applyFilters(); });
    if (sortSelect) sortSelect.addEventListener('change', function (event) { activeSort = event.target.value; filteredTasks = sortTasks(filteredTasks, activeSort); updateTaskSummary(filteredTasks); renderAvailableTasks(filteredTasks); });

    priorityPills.forEach(function (pill) { pill.addEventListener('click', function () { activePriorityFilter = pill.dataset.priorityPill || ''; if (filterSelect) filterSelect.value = activePriorityFilter; priorityPills.forEach(function (button) { button.classList.toggle('active', button === pill); }); applyFilters(); }); });
    applyFilters();
  }

  function sortTasks(tasks, sortValue) {
    var sorted = tasks.slice();
    switch (sortValue) {
      case 'oldest': sorted.sort(function (a, b) { return new Date(a.created_at || 0) - new Date(b.created_at || 0); }); break;
      case 'shortest': sorted.sort(function (a, b) { return (a.estimated_hours || Infinity) - (b.estimated_hours || Infinity); }); break;
      case 'longest': sorted.sort(function (a, b) { return (b.estimated_hours || 0) - (a.estimated_hours || 0); }); break;
      default: sorted.sort(function (a, b) { return new Date(b.created_at || 0) - new Date(a.created_at || 0); }); break;
    }
    return sorted;
  }

  function setupAvailableTaskActions() {
    var container = document.getElementById('availableTasksContainer');
    if (!container) return;
    container.addEventListener('click', function (event) {
      var viewButton = event.target.closest('.js-view-task');
      var acceptButton = event.target.closest('.js-accept-task');
      if (viewButton) { var taskId = parseInt(viewButton.dataset.taskId, 10); if (!Number.isNaN(taskId)) viewTaskDetails(taskId); return; }
      if (acceptButton) { var taskId = parseInt(acceptButton.dataset.taskId, 10); if (!Number.isNaN(taskId)) acceptTask(taskId); }
    });
  }

  function setupActiveTaskActions() {
    Array.from(document.querySelectorAll('.js-update-progress')).forEach(function (button) {
      button.addEventListener('click', function () { var taskId = parseInt(button.dataset.taskId, 10); var nextValue = parseFloat(button.dataset.progressNext); if (!Number.isNaN(taskId)) updateProgress(taskId, nextValue); });
    });
    Array.from(document.querySelectorAll('.js-complete-task')).forEach(function (button) {
      button.addEventListener('click', function () { var taskId = parseInt(button.dataset.taskId, 10); if (!Number.isNaN(taskId)) completeTask(taskId); });
    });
  }

  function initializeProgressIndicators() {
    document.querySelectorAll('[data-progress-value]').forEach(function (bar) {
      var value = parseFloat(bar.dataset.progressValue);
      if (!Number.isNaN(value)) { var bounded = Math.min(Math.max(value, 0), 100); bar.style.width = bounded + '%'; }
    });
  }

  async function acceptTask(taskId) {
    if (!confirm(strings.confirm_accept || 'Are you sure?')) return;
    try {
      var response = await fetch('/api/tasks/' + taskId + '/assign/' + (currentUserId || ''), { method: 'POST' });
      var data = await response.json();
      if (data && data.success) { showNotification(strings.task_accepted || 'Task accepted', 'success'); setTimeout(function () { location.reload(); }, 1500); } else { showNotification((strings.error_accepting || 'Error accepting: ') + (data && data.error ? data.error : ''), 'danger'); }
    } catch (err) { console.error('Error accepting task:', err); showNotification(strings.error_connecting || 'Server connection error', 'danger'); }
  }

  function viewTaskDetails(taskId) { showNotification(strings.details_modal || 'Task details will be shown in modal', 'info'); }

  async function updateProgress(taskId, newProgress) {
    try {
      var response = await fetch('/api/tasks/' + taskId, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ progress: Math.min(newProgress, 100) }) });
      var data = await response.json();
      if (data && data.success) { showNotification(strings.progress_updated || 'Progress updated', 'success'); setTimeout(function () { location.reload(); }, 1000); } else { showNotification(strings.error_updating || 'Error updating progress', 'danger'); }
    } catch (err) { console.error('Error updating progress:', err); showNotification(strings.error_connecting || 'Server connection error', 'danger'); }
  }

  async function completeTask(taskId) {
    if (!confirm(strings.confirm_complete || 'Confirm complete?')) return;
    try {
      var response = await fetch('/api/tasks/' + taskId + '/complete', { method: 'POST' });
      var data = await response.json();
      if (data && data.success) { showNotification(strings.task_completed || 'Task completed', 'success'); setTimeout(function () { location.reload(); }, 1500); } else { showNotification(strings.error_completing || 'Error completing task', 'danger'); }
    } catch (err) { console.error('Error completing task:', err); showNotification(strings.error_connecting || 'Server connection error', 'danger'); }
  }

  async function updateLocation(evt) {
    // Accept an optional event (button click) or try to find the button in DOM.
    var btn = null;
    try {
      if (evt && evt.target) btn = evt.target;
    } catch (e) {
      btn = null;
    }
    if (!btn) {
      btn = document.querySelector('[data-action="update-location"]') || document.getElementById('updateLocationBtn') || document.querySelector('button[type=submit]');
    }

    var latNode = document.getElementById('latitude');
    var lonNode = document.getElementById('longitude');
    var locNode = document.getElementById('locationText');
    var latitude = latNode ? latNode.value : '';
    var longitude = lonNode ? lonNode.value : '';
    var locationText = locNode ? locNode.value : '';

    if (!latitude || !longitude) {
      showNotification(strings.enter_valid_coordinates || 'Please enter valid coordinates', 'warning');
      return;
    }

    var originalText = null;
    try {
      if (btn) {
        originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>' + (strings.saving || 'Saving...');
        btn.disabled = true;
      }

      var response = await fetch('/api/volunteers/' + (currentUserId || '') + '/location', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: parseFloat(latitude), longitude: parseFloat(longitude), location: locationText })
      });
      var data = await response.json();
      if (data && data.success) {
        showNotification(strings.location_updated || 'Location updated', 'success');
        setTimeout(function () { location.reload(); }, 1500);
      } else {
        showNotification((strings.error_updating_location || 'Error updating location: ') + (data && data.error ? data.error : ''), 'danger');
      }
    } catch (err) {
      console.error('Update location error:', err);
      showNotification(strings.error_connecting || 'Server connection error', 'danger');
    } finally {
      try {
        if (btn) {
          btn.innerHTML = originalText;
          btn.disabled = false;
        }
      } catch (e) {
        /* ignore cleanup errors */
      }
    }
  }

  // Attempt to obtain browser geolocation and fill latitude/longitude fields
  function autoFillCoordinatesIfEmpty() {
    try {
      var latNode = document.getElementById('latitude');
      var lonNode = document.getElementById('longitude');
      if (!latNode || !lonNode) return;
      var lat = (latNode.value || '').toString().trim();
      var lon = (lonNode.value || '').toString().trim();
      if (lat !== '' && lon !== '') return; // already populated

      if (!navigator.geolocation) {
        // Geolocation not supported by browser
        return;
      }

      navigator.geolocation.getCurrentPosition(function (pos) {
        try {
          var latitude = pos.coords.latitude;
          var longitude = pos.coords.longitude;
          if (latNode && (!latNode.value || latNode.value === '')) latNode.value = latitude.toFixed(6);
          if (lonNode && (!lonNode.value || lonNode.value === '')) lonNode.value = longitude.toFixed(6);
          showNotification(strings.location_success || 'Location obtained', 'success');
        } catch (e) {
          console.warn('Failed to set coords from geolocation', e);
        }
      }, function (err) {
        // Silent fail — user may have denied permission
        console.warn('Geolocation failed or denied', err);
      }, { enableHighAccuracy: true, timeout: 5000, maximumAge: 60000 });
    } catch (e) {
      console.warn('autoFillCoordinatesIfEmpty error', e);
    }
  }

  // Function wired to template's GPS button
  window.getCurrentLocation = function () {
    try {
      var latNode = document.getElementById('latitude');
      var lonNode = document.getElementById('longitude');
      if (!navigator.geolocation) {
        showNotification(strings.geo_unsupported || 'Geolocation not supported', 'warning');
        return;
      }
      var btn = document.querySelector('[onclick="getCurrentLocation()"]');
      var original = null;
      if (btn) { original = btn.innerHTML; btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>' + (strings.loading_location || 'Loading...'); btn.disabled = true; }
      navigator.geolocation.getCurrentPosition(function (pos) {
        try {
          var latitude = pos.coords.latitude;
          var longitude = pos.coords.longitude;
          if (latNode) latNode.value = latitude.toFixed(6);
          if (lonNode) lonNode.value = longitude.toFixed(6);
          showNotification(strings.location_success || 'Location obtained', 'success');
        } catch (e) {
          console.warn('getCurrentLocation success handler error', e);
        } finally {
          if (btn) { btn.innerHTML = original; btn.disabled = false; }
        }
      }, function (err) {
        console.warn('Geolocation error', err);
        showNotification(strings.location_fail || 'Could not get your location', 'warning');
        if (btn) { btn.innerHTML = original; btn.disabled = false; }
      }, { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 });
    } catch (e) {
      console.error('getCurrentLocation error', e);
      showNotification(strings.location_fail || 'Could not get your location', 'danger');
    }
  };

  function showNotification(message, type) {
    var container = document.getElementById('notificationContainer');
    var notificationId = 'notification-' + Date.now();
    var notificationHtml = '\n    <div id="' + notificationId + '" class="alert alert-' + (type || 'info') + ' alert-dismissible fade show" role="alert">' + message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>\n  ';
    container.insertAdjacentHTML('beforeend', notificationHtml);
    setTimeout(function () { var n = document.getElementById(notificationId); if (n) n.remove(); }, 5000);
  }

})();
