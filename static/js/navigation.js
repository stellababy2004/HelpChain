/**
 * Navigation Improvements - Search, Breadcrumbs, and Enhanced Navigation
 * Provides search functionality, breadcrumb management, and navigation enhancements
 */

class HelpChainNavigation {
  constructor() {
    this.searchTimeout = null;
    this.currentSearchResults = [];
    this.init();
  }

  init() {
    this.initSearch();
    this.initBackToTop();
    this.initDropdownMenus();
    this.initKeyboardNavigation();
  }

  // Search Functionality
  initSearch() {
    const searchInputs = document.querySelectorAll(".search-input");
    searchInputs.forEach((input) => {
      input.addEventListener("input", (e) => this.handleSearchInput(e));
      input.addEventListener("keydown", (e) => this.handleSearchKeydown(e));
    });

    // Close search results when clicking outside
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".search-container")) {
        this.hideSearchResults();
      }
    });
  }

  handleSearchInput(e) {
    const query = e.target.value.trim();
    const searchContainer = e.target.closest(".search-container");

    clearTimeout(this.searchTimeout);

    if (query.length < 2) {
      this.hideSearchResults();
      return;
    }

    this.searchTimeout = setTimeout(() => {
      this.performSearch(query, searchContainer);
    }, 300);
  }

  handleSearchKeydown(e) {
    const searchContainer = e.target.closest(".search-container");
    const resultsContainer = searchContainer?.querySelector(".search-results");

    if (!resultsContainer || !resultsContainer.children.length) return;

    const currentFocus = document.activeElement;
    const results = Array.from(resultsContainer.children);

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        const nextIndex = results.indexOf(currentFocus) + 1;
        if (nextIndex < results.length) {
          results[nextIndex].focus();
        }
        break;
      case "ArrowUp":
        e.preventDefault();
        const prevIndex = results.indexOf(currentFocus) - 1;
        if (prevIndex >= 0) {
          results[prevIndex].focus();
        } else {
          e.target.focus();
        }
        break;
      case "Enter":
        e.preventDefault();
        if (currentFocus.classList.contains("search-result-item")) {
          currentFocus.click();
        }
        break;
      case "Escape":
        this.hideSearchResults();
        e.target.focus();
        break;
    }
  }

  async performSearch(query, searchContainer) {
    try {
      // Show loading state
      this.showSearchLoading(searchContainer);

      // Perform search based on current page context
      const results = await this.searchContent(query);

      this.displaySearchResults(results, searchContainer);
    } catch (error) {
      console.error("Search error:", error);
      this.showSearchError(searchContainer);
    }
  }

  async searchContent(query) {
    // Get current page context
    const currentPath = window.location.pathname;

    // Define searchable content based on page type
    const searchContexts = {
      "/": this.searchHomePage(query),
      "/dashboard": this.searchDashboard(query),
      "/admin": this.searchAdminPages(query),
      "/volunteer": this.searchVolunteerPages(query),
    };

    const searchFunction =
      searchContexts[currentPath] || this.searchGeneral(query);
    return await searchFunction;
  }

  searchHomePage(query) {
    const content = [
      {
        title: "Бърза помощ",
        description: "Свързване с доброволци в минути",
        url: "#features",
      },
      {
        title: "Стани доброволец",
        description: "Присъедини се към общността",
        url: "/become_volunteer",
      },
      {
        title: "Подай заявка",
        description: "Получи помощ когато имаш нужда",
        url: "/submit_request",
      },
      {
        title: "Категории",
        description: "Разгледай видовете помощ",
        url: "/all_categories",
      },
      {
        title: "Често задавани въпроси",
        description: "Отговори на често задавани въпроси",
        url: "/faq",
      },
    ];

    return content.filter(
      (item) =>
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.description.toLowerCase().includes(query.toLowerCase()),
    );
  }

  searchDashboard(query) {
    const content = [
      {
        title: "Моите задачи",
        description: "Преглед на активните задачи",
        url: "/my_tasks",
      },
      {
        title: "Налични задачи",
        description: "Виж откритите заявки за помощ",
        url: "/available_tasks",
      },
      {
        title: "Профил",
        description: "Управление на профила",
        url: "/profile",
      },
      {
        title: "Настройки",
        description: "Персонални настройки",
        url: "/settings",
      },
    ];

    return content.filter(
      (item) =>
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.description.toLowerCase().includes(query.toLowerCase()),
    );
  }

  searchAdminPages(query) {
    const content = [
      {
        title: "Админ панел",
        description: "Основно админ табло",
        url: "/admin",
      },
      {
        title: "Аналитика",
        description: "Статистики и метрики",
        url: "/admin/analytics",
      },
      {
        title: "Потребители",
        description: "Управление на потребители",
        url: "/admin/users",
      },
      {
        title: "Роли",
        description: "Управление на роли и права",
        url: "/admin/roles",
      },
      {
        title: "Настройки",
        description: "Системни настройки",
        url: "/admin/settings",
      },
    ];

    return content.filter(
      (item) =>
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.description.toLowerCase().includes(query.toLowerCase()),
    );
  }

  searchVolunteerPages(query) {
    const content = [
      {
        title: "Доброволческо табло",
        description: "Твоето доброволческо табло",
        url: "/volunteer/dashboard",
      },
      {
        title: "Моите задачи",
        description: "Задачи по които работиш",
        url: "/volunteer/tasks",
      },
      {
        title: "Чат",
        description: "Комуникация с нуждаещите се",
        url: "/volunteer/chat",
      },
      {
        title: "Отчети",
        description: "Твоите отчети и постижения",
        url: "/volunteer/reports",
      },
    ];

    return content.filter(
      (item) =>
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.description.toLowerCase().includes(query.toLowerCase()),
    );
  }

  searchGeneral(query) {
    // General search across common elements
    return [
      { title: "Начало", description: "Към началната страница", url: "/" },
      { title: "Вход", description: "Влез в системата", url: "/login" },
      {
        title: "Регистрация",
        description: "Създай нов акаунт",
        url: "/register",
      },
    ].filter(
      (item) =>
        item.title.toLowerCase().includes(query.toLowerCase()) ||
        item.description.toLowerCase().includes(query.toLowerCase()),
    );
  }

  showSearchLoading(searchContainer) {
    let resultsContainer = searchContainer.querySelector(".search-results");
    if (!resultsContainer) {
      resultsContainer = document.createElement("div");
      resultsContainer.className = "search-results";
      searchContainer.appendChild(resultsContainer);
    }

    resultsContainer.innerHTML = `
      <div class="search-result-item">
        <div class="search-result-title">Търсене...</div>
        <div class="search-result-description">
          <div class="spinner-border spinner-border-sm" role="status">
            <span class="visually-hidden">Зареждане...</span>
          </div>
        </div>
      </div>
    `;
  }

  showSearchError(searchContainer) {
    let resultsContainer = searchContainer.querySelector(".search-results");
    if (!resultsContainer) {
      resultsContainer = document.createElement("div");
      resultsContainer.className = "search-results";
      searchContainer.appendChild(resultsContainer);
    }

    resultsContainer.innerHTML = `
      <div class="search-result-item">
        <div class="search-result-title">Грешка при търсенето</div>
        <div class="search-result-description">Моля опитайте отново</div>
      </div>
    `;
  }

  displaySearchResults(results, searchContainer) {
    let resultsContainer = searchContainer.querySelector(".search-results");
    if (!resultsContainer) {
      resultsContainer = document.createElement("div");
      resultsContainer.className = "search-results";
      searchContainer.appendChild(resultsContainer);
    }

    if (results.length === 0) {
      resultsContainer.innerHTML = `
        <div class="search-result-item">
          <div class="search-result-title">Няма резултати</div>
          <div class="search-result-description">Опитайте с други ключови думи</div>
        </div>
      `;
      return;
    }

    resultsContainer.innerHTML = results
      .map(
        (result) => `
      <div class="search-result-item" tabindex="0" data-url="${result.url}">
        <div class="search-result-title">${result.title}</div>
        <div class="search-result-description">${result.description}</div>
      </div>
    `,
      )
      .join("");

    // Add click handlers
    resultsContainer.querySelectorAll(".search-result-item").forEach((item) => {
      item.addEventListener("click", () => {
        const url = item.dataset.url;
        if (url.startsWith("#")) {
          // Scroll to section
          const target = document.querySelector(url);
          if (target) {
            target.scrollIntoView({ behavior: "smooth" });
          }
        } else {
          // Navigate to page
          window.location.href = url;
        }
        this.hideSearchResults();
      });
    });
  }

  hideSearchResults() {
    document.querySelectorAll(".search-results").forEach((container) => {
      container.remove();
    });
  }

  // Back to Top Functionality
  initBackToTop() {
    const backToTopBtn = document.querySelector(".back-to-top");
    if (!backToTopBtn) return;

    window.addEventListener("scroll", () => {
      if (window.scrollY > 300) {
        backToTopBtn.classList.add("visible");
      } else {
        backToTopBtn.classList.remove("visible");
      }
    });

    backToTopBtn.addEventListener("click", () => {
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    });
  }

  // Dropdown Menu Enhancements
  initDropdownMenus() {
    const dropdowns = document.querySelectorAll(".nav-item-dropdown");

    dropdowns.forEach((dropdown) => {
      const toggle = dropdown.querySelector(".nav-dropdown-toggle");
      const menu = dropdown.querySelector(".nav-dropdown-menu");

      if (!toggle || !menu) return;

      // Handle keyboard navigation
      toggle.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this.toggleDropdown(dropdown);
        } else if (e.key === "Escape") {
          this.closeDropdown(dropdown);
        } else if (e.key === "ArrowDown") {
          e.preventDefault();
          this.openDropdown(dropdown);
          const firstItem = menu.querySelector(".nav-dropdown-item");
          if (firstItem) firstItem.focus();
        }
      });

      // Handle menu item navigation
      menu.addEventListener("keydown", (e) => {
        const items = Array.from(menu.querySelectorAll(".nav-dropdown-item"));
        const currentIndex = items.indexOf(document.activeElement);

        if (e.key === "ArrowDown") {
          e.preventDefault();
          const nextIndex = currentIndex + 1;
          if (nextIndex < items.length) {
            items[nextIndex].focus();
          }
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          const prevIndex = currentIndex - 1;
          if (prevIndex >= 0) {
            items[prevIndex].focus();
          } else {
            toggle.focus();
          }
        } else if (e.key === "Escape") {
          this.closeDropdown(dropdown);
          toggle.focus();
        }
      });
    });

    // Close dropdowns when clicking outside
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".nav-item-dropdown")) {
        this.closeAllDropdowns();
      }
    });
  }

  toggleDropdown(dropdown) {
    const isOpen = dropdown.classList.contains("open");
    this.closeAllDropdowns();

    if (!isOpen) {
      this.openDropdown(dropdown);
    }
  }

  openDropdown(dropdown) {
    dropdown.classList.add("open");
    const menu = dropdown.querySelector(".nav-dropdown-menu");
    if (menu) {
      menu.style.opacity = "1";
      menu.style.visibility = "visible";
      menu.style.transform = "translateY(0)";
    }
  }

  closeDropdown(dropdown) {
    dropdown.classList.remove("open");
    const menu = dropdown.querySelector(".nav-dropdown-menu");
    if (menu) {
      menu.style.opacity = "0";
      menu.style.visibility = "hidden";
      menu.style.transform = "translateY(-10px)";
    }
  }

  closeAllDropdowns() {
    document.querySelectorAll(".nav-item-dropdown.open").forEach((dropdown) => {
      this.closeDropdown(dropdown);
    });
  }

  // Keyboard Navigation Improvements
  initKeyboardNavigation() {
    document.addEventListener("keydown", (e) => {
      // Skip to main content with Ctrl+Home
      if (e.ctrlKey && e.key === "Home") {
        e.preventDefault();
        const mainContent = document.querySelector(
          'main, #main-content, [role="main"]',
        );
        if (mainContent) {
          mainContent.focus();
          mainContent.scrollIntoView();
        }
      }

      // Focus search with Ctrl+K
      if (e.ctrlKey && e.key === "k") {
        e.preventDefault();
        const searchInput = document.querySelector(".search-input");
        if (searchInput) {
          searchInput.focus();
        }
      }
    });
  }

  // Breadcrumb Management
  static createBreadcrumb(items) {
    const container = document.createElement("nav");
    container.className = "breadcrumb-container";
    container.setAttribute("aria-label", "Навигация");

    const ol = document.createElement("ol");
    ol.className = "breadcrumb";

    items.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = "breadcrumb-item";

      if (index === items.length - 1) {
        li.classList.add("active");
        li.setAttribute("aria-current", "page");
        li.textContent = item.title;
      } else {
        const a = document.createElement("a");
        a.href = item.url;
        a.textContent = item.title;
        li.appendChild(a);
      }

      ol.appendChild(li);
    });

    container.appendChild(ol);
    return container;
  }

  // Page Navigation Helper
  static createPageNavigation(title, links) {
    const container = document.createElement("div");
    container.className = "page-nav";

    const titleEl = document.createElement("h3");
    titleEl.className = "page-nav-title";
    titleEl.textContent = title;
    container.appendChild(titleEl);

    const linksContainer = document.createElement("div");
    linksContainer.className = "page-nav-links";

    links.forEach((link) => {
      const a = document.createElement("a");
      a.className = "page-nav-link";
      a.href = link.url;

      if (link.icon) {
        const icon = document.createElement("i");
        icon.className = link.icon;
        a.appendChild(icon);
      }

      const text = document.createTextNode(link.title);
      a.appendChild(text);

      linksContainer.appendChild(a);
    });

    container.appendChild(linksContainer);
    return container;
  }
}

// Initialize navigation when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  new HelpChainNavigation();
});

// Export for use in other scripts
window.HelpChainNavigation = HelpChainNavigation;
