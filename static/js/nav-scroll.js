document.addEventListener("DOMContentLoaded", function () {
  if (!document.body.classList.contains("hc-page-home")) return;

  const nav =
    document.querySelector(".hc-navbar") ||
    document.querySelector(".main-nav") ||
    document.querySelector("nav.navbar");

  if (!nav) return;

  function syncNavHeight() {
    const h = nav.getBoundingClientRect().height;
    const px = `${Math.round(h)}px`;
    document.documentElement.style.setProperty("--hc-nav-h", px);
    document.body.style.paddingTop = px;
  }

  function onScroll() {
    if (window.scrollY > 16) {
      nav.classList.add("is-scrolled");
      document.body.classList.add("hc-nav-scrolled");
    } else {
      nav.classList.remove("is-scrolled");
      document.body.classList.remove("hc-nav-scrolled");
    }
  }

  syncNavHeight();
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", syncNavHeight, { passive: true });
});
