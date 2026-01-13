// Common JavaScript utilities for HelpChain dashboards
class HelpChainUtils {
  constructor() {
    this.initThemeToggle();
    this.initLoadingSpinner();
  }

  // Theme Toggle Functionality
  initThemeToggle() {
    const themeToggle = document.getElementById("themeToggle");
    if (!themeToggle) return;

    const html = document.documentElement;
    const themeIcon = themeToggle.querySelector("i");

    // Load saved theme
    const savedTheme = localStorage.getItem("theme") || "light";
    html.setAttribute("data-theme", savedTheme);
    this.updateThemeIcon(savedTheme);

    themeToggle.addEventListener("click", () => {
      const currentTheme = html.getAttribute("data-theme");
      const newTheme = currentTheme === "light" ? "dark" : "light";

      html.setAttribute("data-theme", newTheme);
      localStorage.setItem("theme", newTheme);
      this.updateThemeIcon(newTheme);
    });
  }

  updateThemeIcon(theme) {
    const themeToggle = document.getElementById("themeToggle");
    if (!themeToggle) return;

    const themeIcon = themeToggle.querySelector("i");
    if (themeIcon) {
      themeIcon.className = theme === "light" ? "fas fa-moon" : "fas fa-sun";
    }
  }

  // Loading Spinner
  initLoadingSpinner() {
    // Loading spinner is already in HTML, this just ensures it's available
  }

  showLoading() {
    const spinner = document.getElementById("loadingSpinner");
    if (spinner) {
      spinner.style.display = "block";
    }
  }

  hideLoading() {
    const spinner = document.getElementById("loadingSpinner");
    if (spinner) {
      spinner.style.display = "none";
    }
  }

  // Utility functions
  confirmAction(message) {
    return confirm(message);
  }

  showAlert(message) {
    alert(message);
  }

  // Real-time updates simulation (can be overridden by specific dashboards)
  startRealtimeUpdates(updateCallback, interval = 30000) {
    setInterval(updateCallback, interval);
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  window.helpChainUtils = new HelpChainUtils();
});
