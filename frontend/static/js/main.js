// HelpChain JavaScript Utilities

// Global Search Functionality
class GlobalSearch {
  constructor(searchInput, resultsContainer) {
    this.searchInput = searchInput;
    this.resultsContainer = resultsContainer;
    this.debounceTimer = null;
    this.init();
  }

  init() {
    this.searchInput.addEventListener("input", (e) => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.performSearch(e.target.value);
      }, 300);
    });
  }

  async performSearch(query) {
    if (query.length < 2) {
      this.resultsContainer.innerHTML = "";
      return;
    }

    try {
      const response = await fetch(
        `/api/search?q=${encodeURIComponent(query)}`,
      );
      const results = await response.json();
      this.displayResults(results);
    } catch (error) {
      console.error("Search error:", error);
      this.showError("Грешка при търсене");
    }
  }

  displayResults(results) {
    if (!results.requests && !results.volunteers) {
      this.resultsContainer.innerHTML =
        '<div class="empty-state"><i class="fas fa-search"></i><h3>Няма резултати</h3></div>';
      return;
    }

    let html = '<div class="search-results">';

    if (results.requests && results.requests.length > 0) {
      html += '<h4><i class="fas fa-clipboard-list"></i> Заявки</h4>';
      results.requests.forEach((request) => {
        html += `
          <div class="card mb-2">
            <div class="card-body">
              <h6 class="card-title">${request.name}</h6>
              <p class="card-text text-truncate-2">${request.description}</p>
              <small class="text-muted">${request.location} • ${request.category}</small>
            </div>
          </div>
        `;
      });
    }

    if (results.volunteers && results.volunteers.length > 0) {
      html += '<h4><i class="fas fa-users"></i> Доброволци</h4>';
      results.volunteers.forEach((volunteer) => {
        html += `
          <div class="card mb-2">
            <div class="card-body">
              <h6 class="card-title">${volunteer.name}</h6>
              <p class="card-text text-truncate-2">${volunteer.skills || "Няма описани умения"}</p>
              <small class="text-muted">${volunteer.location}</small>
            </div>
          </div>
        `;
      });
    }

    html += "</div>";
    this.resultsContainer.innerHTML = html;
  }

  showError(message) {
    this.resultsContainer.innerHTML = `<div class="error-state"><i class="fas fa-exclamation-triangle"></i> ${message}</div>`;
  }
}

// Loading States
class LoadingManager {
  static showSpinner(element = document.body) {
    const spinner = document.createElement("div");
    spinner.className = "loading-overlay";
    spinner.innerHTML = `
      <div class="loading-card">
        <div class="loading-spinner"></div>
        <p class="mt-2">Зареждане...</p>
      </div>
    `;
    element.appendChild(spinner);
    return spinner;
  }

  static hideSpinner(spinner) {
    if (spinner && spinner.parentNode) {
      spinner.parentNode.removeChild(spinner);
    }
  }

  static showInlineSpinner(button) {
    const originalText = button.innerHTML;
    button.innerHTML = '<span class="loading-spinner me-2"></span>Зареждане...';
    button.disabled = true;
    return () => {
      button.innerHTML = originalText;
      button.disabled = false;
    };
  }
}

// Empty States
class EmptyState {
  static show(
    container,
    icon = "fas fa-inbox",
    title = "Няма данни",
    message = "Все още няма съдържание тук.",
  ) {
    container.innerHTML = `
      <div class="empty-state">
        <i class="${icon}"></i>
        <h3>${title}</h3>
        <p>${message}</p>
      </div>
    `;
  }
}

// Error States
class ErrorState {
  static show(container, message = "Възникна грешка") {
    container.innerHTML = `
      <div class="error-state">
        <i class="fas fa-exclamation-triangle"></i>
        ${message}
      </div>
    `;
  }
}

// Status Badges
class StatusBadge {
  static getBadge(status) {
    const statusMap = {
      pending: { class: "status-pending", text: "Очаква" },
      in_progress: { class: "status-in_progress", text: "В процес" },
      completed: { class: "status-completed", text: "Завършена" },
      cancelled: { class: "status-cancelled", text: "Отказана" },
    };

    const statusInfo = statusMap[status] || {
      class: "status-pending",
      text: status,
    };
    return `<span class="status-badge ${statusInfo.class}">${statusInfo.text}</span>`;
  }
}

// Initialize components when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Initialize global search if elements exist
  const searchInput = document.getElementById("global-search-input");
  const searchResults = document.getElementById("global-search-results");

  if (searchInput && searchResults) {
    new GlobalSearch(searchInput, searchResults);
  }

  // Auto-hide alerts after 5 seconds
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach((alert) => {
    setTimeout(() => {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });
});

// Utility functions
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString("bg-BG");
}

function truncateText(text, maxLength = 100) {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
}
