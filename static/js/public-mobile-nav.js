(function () {
  const toggleBtn = document.getElementById("hcMobileNavToggle");
  const nav = document.getElementById("hcMobileNav");
  const navRoot = document.querySelector(".hc-public-nav-root");
  const desktopNav = document.getElementById("navbarNav");
  if (!toggleBtn || !nav || !navRoot || !desktopNav) return;

  navRoot.setAttribute("data-hc-nav-js", "bound");

  const closeEls = nav.querySelectorAll("[data-mobile-nav-close='1']");
  const firstLink = nav.querySelector(".hc-mobile-nav__item a");
  const isHomePage = document.body.classList.contains("hc-page-home");
  const widthSwitch = 1079;

  function isCrowdedDesktop() {
    const navList = desktopNav.querySelector(".navbar-nav");
    const actionRow = desktopNav.querySelector(".hc-public-nav-actions");
    const tooTallDesktop = desktopNav.scrollHeight > desktopNav.clientHeight + 8;
    const navWrap = navList && navList.scrollHeight > navList.clientHeight + 4;
    const tooWideDesktop = desktopNav.scrollWidth > desktopNav.clientWidth + 56;
    const navOverflow = navList && navList.scrollWidth > navList.clientWidth + 36;
    const actionsOverflow = actionRow && actionRow.scrollWidth > actionRow.clientWidth + 10;
    return Boolean(tooTallDesktop || navWrap || tooWideDesktop || navOverflow || actionsOverflow);
  }

  function closeNav(returnFocus) {
    nav.classList.remove("is-open");
    nav.setAttribute("aria-hidden", "true");
    toggleBtn.setAttribute("aria-expanded", "false");
    document.body.classList.remove("hc-mobile-nav-open");
    if (returnFocus !== false) toggleBtn.focus({ preventScroll: true });
  }

  function applyResponsiveNavMode() {
    let useMobile = window.innerWidth <= widthSwitch;
    if (!useMobile) {
      navRoot.classList.remove("hc-nav-mobile-mode");
      useMobile = !isHomePage && isCrowdedDesktop();
    }
    navRoot.classList.toggle("hc-nav-mobile-mode", useMobile);
    if (!useMobile && nav.classList.contains("is-open")) closeNav(false);
  }

  function openNav() {
    nav.classList.add("is-open");
    nav.setAttribute("aria-hidden", "false");
    toggleBtn.setAttribute("aria-expanded", "true");
    document.body.classList.add("hc-mobile-nav-open");
    if (firstLink) firstLink.focus({ preventScroll: true });
  }

  toggleBtn.addEventListener("click", function () {
    if (nav.classList.contains("is-open")) closeNav();
    else openNav();
  });

  closeEls.forEach(function (el) {
    el.addEventListener("click", function () {
      closeNav(false);
    });
  });

  nav.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () {
      closeNav(false);
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && nav.classList.contains("is-open")) closeNav();
  });

  let resizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(applyResponsiveNavMode, 120);
  });

  applyResponsiveNavMode();
})();
