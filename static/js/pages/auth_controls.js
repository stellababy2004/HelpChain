(function () {
  "use strict";

  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
      return;
    }
    fn();
  }

  function initPasswordToggle() {
    var toggle = document.getElementById("passwordToggle");
    var input = document.getElementById("password");
    var icon = toggle ? toggle.querySelector("i") : null;
    if (!toggle || !input || !icon) return;

    toggle.addEventListener("click", function () {
      var nextType = input.getAttribute("type") === "password" ? "text" : "password";
      input.setAttribute("type", nextType);
      toggle.setAttribute("aria-pressed", nextType === "text" ? "true" : "false");
      icon.className = nextType === "password" ? "fas fa-eye" : "fas fa-eye-slash";
    });
  }

  function initVolunteerLoginLoading() {
    var form = document.querySelector('form[action$="/volunteer_login"]');
    var button = document.getElementById("submitBtn");
    if (!form || !button) return;

    var originalHtml = button.innerHTML;
    var loadingLabel = button.getAttribute("data-loading-label") || "Sending...";

    form.addEventListener(
      "submit",
      function () {
        button.disabled = true;
        button.innerHTML =
          '<i class="fas fa-spinner fa-spin me-2"></i>' + loadingLabel;
        var spinner = document.getElementById("loadingSpinner");
        if (spinner) spinner.style.display = "block";
      },
      { capture: true },
    );

    window.addEventListener("pageshow", function () {
      button.disabled = false;
      button.innerHTML = originalHtml;
    });
  }

  function initVerifyCodeForm() {
    var form = document.querySelector('form[action=""], form:not([action])');
    var codeInput = document.getElementById("code");
    if (!form || !codeInput) return;

    try {
      codeInput.focus();
    } catch (_) {}

    codeInput.addEventListener("input", function (event) {
      event.target.value = (event.target.value || "").replace(/\D/g, "").slice(0, 6);
    });

    form.addEventListener("submit", function (event) {
      var code = (codeInput.value || "").trim();
      if (code.length === 6 && /^\d{6}$/.test(code)) return;
      event.preventDefault();
      codeInput.focus();
      codeInput.reportValidity();
    });
  }

  function updateCheckboxCard(card) {
    if (!card) return;
    var checkbox = card.querySelector('input[type="checkbox"]');
    if (!checkbox) return;
    card.classList.toggle("selected", !!checkbox.checked);
  }

  function initRegisterCheckboxCards() {
    var cards = Array.prototype.slice.call(
      document.querySelectorAll("#volunteerOption, #organizationOption, #termsOption"),
    );
    if (!cards.length) return;

    cards.forEach(function (card) {
      var checkbox = card.querySelector('input[type="checkbox"]');
      if (!checkbox) return;

      updateCheckboxCard(card);

      card.addEventListener("click", function (event) {
        if (event.target.closest("a")) return;
        if (event.target === checkbox) return;
        event.preventDefault();
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      });

      checkbox.addEventListener("change", function () {
        updateCheckboxCard(card);
      });
    });
  }

  function initRegisterThemeToggle() {
    var toggle = document.getElementById("themeToggle");
    if (!toggle) return;

    var html = document.documentElement;
    var icon = toggle.querySelector("i");

    function updateThemeIcon(theme) {
      if (!icon) return;
      icon.className = theme === "light" ? "fas fa-moon" : "fas fa-sun";
    }

    var savedTheme = "light";
    try {
      savedTheme = localStorage.getItem("theme") || "light";
    } catch (_) {}

    html.setAttribute("data-theme", savedTheme);
    updateThemeIcon(savedTheme);

    toggle.addEventListener("click", function () {
      var currentTheme = html.getAttribute("data-theme");
      var nextTheme = currentTheme === "light" ? "dark" : "light";
      html.setAttribute("data-theme", nextTheme);
      try {
        localStorage.setItem("theme", nextTheme);
      } catch (_) {}
      updateThemeIcon(nextTheme);
    });
  }

  function initRegisterPasswordStrength() {
    var input = document.getElementById("password");
    var box = document.getElementById("passwordStrength");
    var fill = document.getElementById("passwordStrengthFill");
    var text = document.getElementById("passwordStrengthText");
    if (!input || !box || !fill || !text) return;

    function scorePassword(password) {
      var score = 0;
      if (password.length >= 8) score += 25;
      if (password.length >= 12) score += 25;
      if (/[a-z]/.test(password)) score += 15;
      if (/[A-Z]/.test(password)) score += 15;
      if (/[0-9]/.test(password)) score += 10;
      if (/[^A-Za-z0-9]/.test(password)) score += 10;
      return Math.min(score, 100);
    }

    function updateStrength(score) {
      fill.style.width = score + "%";
      if (score < 30) {
        fill.style.background = "#dc3545";
        text.textContent = "ÐœÐ½Ð¾Ð³Ð¾ ÑÐ»Ð°Ð±Ð° Ð¿Ð°Ñ€Ð¾Ð»Ð°";
        text.style.color = "#dc3545";
      } else if (score < 50) {
        fill.style.background = "#fd7e14";
        text.textContent = "Ð¡Ð»Ð°Ð±Ð° Ð¿Ð°Ñ€Ð¾Ð»Ð°";
        text.style.color = "#fd7e14";
      } else if (score < 70) {
        fill.style.background = "#ffc107";
        text.textContent = "Ð¡Ñ€ÐµÐ´Ð½Ð° Ð¿Ð°Ñ€Ð¾Ð»Ð°";
        text.style.color = "#ffc107";
      } else if (score < 90) {
        fill.style.background = "#20c997";
        text.textContent = "Ð¡Ð¸Ð»Ð½Ð° Ð¿Ð°Ñ€Ð¾Ð»Ð°";
        text.style.color = "#20c997";
      } else {
        fill.style.background = "#28a745";
        text.textContent = "ÐœÐ½Ð¾Ð³Ð¾ ÑÐ¸Ð»Ð½Ð° Ð¿Ð°Ñ€Ð¾Ð»Ð°";
        text.style.color = "#28a745";
      }
    }

    input.addEventListener("input", function () {
      var password = input.value || "";
      if (!password.length) {
        box.style.display = "none";
        return;
      }
      box.style.display = "block";
      updateStrength(scorePassword(password));
    });
  }

  function initRegisterCitizenId() {
    var citizenId = document.getElementById("citizen_id");
    if (!citizenId) return;

    citizenId.addEventListener("input", function () {
      this.value = (this.value || "").replace(/\D/g, "").slice(0, 10);
    });
  }

  function initRegisterSubmitState() {
    var form = document.getElementById("registerForm");
    var button = document.getElementById("registerBtn");
    var spinner = document.getElementById("loadingSpinner");
    if (!form || !button) return;

    var originalHtml = button.innerHTML;

    form.addEventListener("submit", function (event) {
      var password = document.getElementById("password");
      var confirmPassword = document.getElementById("confirm_password");
      if (password && confirmPassword) {
        confirmPassword.setCustomValidity(
          password.value === confirmPassword.value ? "" : "Passwords must match.",
        );
      }

      if (!form.checkValidity()) return;

      button.disabled = true;
      button.innerHTML =
        '<i class="fas fa-spinner fa-spin me-2"></i>Ð ÐµÐ³Ð¸ÑÑ‚Ñ€Ð¸Ñ€Ð°Ð½Ðµ...';
      if (spinner) spinner.style.display = "block";
    });

    window.addEventListener("pageshow", function () {
      button.disabled = false;
      button.innerHTML = originalHtml;
    });
  }

  onReady(function () {
    initPasswordToggle();
    initVolunteerLoginLoading();
    initVerifyCodeForm();
    initRegisterThemeToggle();
    initRegisterCheckboxCards();
    initRegisterPasswordStrength();
    initRegisterCitizenId();
    initRegisterSubmitState();
  });
})();
