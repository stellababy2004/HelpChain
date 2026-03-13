document.addEventListener("DOMContentLoaded", function () {
  const pagePath = String(document.body?.dataset?.hcPage || "");
  if (pagePath.startsWith("/admin")) return;

  const nav =
    document.querySelector(".hc-navbar") ||
    document.querySelector(".main-nav") ||
    document.querySelector("nav.navbar");

  if (!nav) return;

  function syncNavHeight() {
    const h = nav.getBoundingClientRect().height;
    const px = `${Math.round(h)}px`;
    document.documentElement.style.setProperty("--hc-nav-h", px);
    const pos = window.getComputedStyle(nav).position;
    if (pos === "fixed") {
      document.body.style.paddingTop = px;
    } else {
      document.body.style.paddingTop = "";
    }
  }

  function onScroll() {
    if (window.scrollY > 16) {
      nav.classList.add("is-scrolled");
      document.body.classList.add("hc-nav-scrolled");
      document.body.classList.add("hc-scrolled");
    } else {
      nav.classList.remove("is-scrolled");
      document.body.classList.remove("hc-nav-scrolled");
      document.body.classList.remove("hc-scrolled");
    }
  }

  syncNavHeight();
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", syncNavHeight, { passive: true });
});
