// Base client-side helpers for HelpChain (moved from inline template)
(function () {
  function safeLog() {
    if (window.console && console.log) console.log.apply(console, arguments);
  }

  // PWA: service worker registration
  if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      try {
        if (
          location.protocol !== 'https:' &&
          location.hostname !== 'localhost' &&
          location.hostname !== '127.0.0.1'
        ) {
          safeLog('[PWA] Service Worker requires HTTPS or localhost');
          return;
        }

        navigator.serviceWorker
          .register('/sw.js', { scope: '/' })
          .then(function (registration) {
            safeLog('[PWA] Service Worker registered successfully:', registration.scope);

            registration.addEventListener('updatefound', function () {
              var newWorker = registration.installing;
              if (newWorker) {
                newWorker.addEventListener('statechange', function () {
                  if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    if (window.HC && window.HC.strings && window.HC.strings.update_available) {
                      showUpdateNotification(window.HC.strings.update_available);
                    } else {
                      showUpdateNotification('A new version is available');
                    }
                  }
                });
              }
            });
          })
          .catch(function (error) {
            safeLog('[PWA] Service Worker registration failed:', error);
          });
      } catch (e) {
        safeLog('[PWA] Registration failed', e);
      }
    });
  }

  // Notification for updates
  function showUpdateNotification(message) {
    var updateToast = document.createElement('div');
    updateToast.className = 'toast align-items-center text-white bg-primary border-0 position-fixed';
    updateToast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    updateToast.setAttribute('role', 'alert');
    updateToast.innerHTML = '\n      <div class="d-flex">\n        <div class="toast-body">' + (message || 'New version available') + '</div>\n        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>\n      </div>\n      <div class="toast-body border-top border-white border-opacity-25 pt-2">\n        <button type="button" class="btn btn-sm btn-light me-2" onclick="updateApp()">\n          <i class="bi bi-download me-1"></i>' + ((window.HC && window.HC.strings && window.HC.strings.update_now) || 'Update now') + '\n        </button>\n        <button type="button" class="btn btn-sm btn-outline-light" data-bs-dismiss="toast">' + ((window.HC && window.HC.strings && window.HC.strings.later) || 'Later') + '</button>\n      </div>\n    ';

    document.body.appendChild(updateToast);
    try {
      var toast = new bootstrap.Toast(updateToast);
      toast.show();
    } catch (e) {
      // bootstrap may be missing in some test contexts
    }

    setTimeout(function () {
      if (updateToast.parentNode) updateToast.remove();
    }, 10000);
  }

  window.showUpdateNotification = showUpdateNotification;

  // Update app (reload + update SW)
  window.updateApp = function () {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then(function (registrations) {
        for (var i = 0; i < registrations.length; i++) {
          try {
            registrations[i].update();
          } catch (e) {
            safeLog('updateApp: update failed', e);
          }
        }
      });
    }
    window.location.reload();
  };

  // Theme helpers
  var THEME_META_COLORS = { light: '#1976d2', dark: '#0f172a' };

  function setTheme(theme, options) {
    var settings = options || {};
    var persist = settings.persist !== undefined ? settings.persist : true;
    var html = document.documentElement;
    var toggleButton = document.getElementById('theme-toggle');
    var themeIcon = document.getElementById('theme-icon');
    var metaTheme = document.querySelector('meta[name="theme-color"]');
    var normalizedTheme = theme === 'dark' ? 'dark' : 'light';

    if (normalizedTheme === 'dark') {
      html.setAttribute('data-theme', 'dark');
      if (themeIcon) themeIcon.className = 'bi bi-sun theme-toggle-icon';
      if (toggleButton) toggleButton.setAttribute('aria-pressed', 'true');
      if (metaTheme) metaTheme.setAttribute('content', THEME_META_COLORS.dark);
    } else {
      html.removeAttribute('data-theme');
      if (themeIcon) themeIcon.className = 'bi bi-moon theme-toggle-icon';
      if (toggleButton) toggleButton.setAttribute('aria-pressed', 'false');
      if (metaTheme) metaTheme.setAttribute('content', THEME_META_COLORS.light);
    }

    if (persist) localStorage.setItem('theme', normalizedTheme); else localStorage.removeItem('theme');
  }

  window.toggleTheme = function () {
    var html = document.documentElement;
    var isDark = html.getAttribute('data-theme') === 'dark';
    setTheme(isDark ? 'light' : 'dark', { persist: true });
  };

  // Initialize theme based on saved or system preference
  function initializeTheme() {
    var savedTheme = null;
    try { savedTheme = localStorage.getItem('theme'); } catch (e) { }
    if (savedTheme === 'dark' || savedTheme === 'light') { setTheme(savedTheme, { persist: true }); return; }

    if (window.matchMedia) {
      var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      setTheme(mediaQuery.matches ? 'dark' : 'light', { persist: false });
      var handleSystemThemeChange = function (event) {
        try {
          if (!localStorage.getItem('theme')) setTheme(event.matches ? 'dark' : 'light', { persist: false });
        } catch (e) { }
      };
      if (typeof mediaQuery.addEventListener === 'function') mediaQuery.addEventListener('change', handleSystemThemeChange); else if (typeof mediaQuery.addListener === 'function') mediaQuery.addListener(handleSystemThemeChange);
    } else {
      setTheme('light', { persist: false });
    }
  }

  // Hide loader on window load and reveal elements
  window.addEventListener('load', function () {
    try {
      var loader = document.getElementById('loader');
      if (loader) loader.style.display = 'none';
      document.querySelectorAll('.glass').forEach(function (el) { el.classList.add('visible'); });
    } catch (e) { }
  });

  // Run theme initialization on DOMContentLoaded
  document.addEventListener('DOMContentLoaded', initializeTheme);
})();
