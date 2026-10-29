document.addEventListener("DOMContentLoaded", function () {
  const pagePath = String(document.body?.dataset?.hcPage || "");
  if (pagePath.startsWith("/admin")) return;

  const nav =
    document.querySelector(".hc-navbar") ||
    document.querySelector(".main-nav") ||
    document.querySelector("nav.navbar");

  if (!nav) return;

  let lastScrollY = window.scrollY;
  let ticking = false;

  function isProtected() {
    return Boolean(
      document.body.classList.contains("hc-mobile-nav-open") ||
        nav.matches(":focus-within") ||
        nav.querySelector(".hc-nav-mega.is-open")
    );
  }

  function syncNavHeight() {
    const h = nav.getBoundingClientRect().height;
    const px = `${Math.round(h)}px`;
    document.documentElement.style.setProperty("--hc-nav-h", px);
    document.body.style.paddingTop = "";
  }

  function onScroll() {
    const currentY = Math.max(0, window.scrollY);
    if (window.scrollY > 16) {
      nav.classList.add("is-scrolled");
      document.body.classList.add("hc-nav-scrolled");
      document.body.classList.add("hc-scrolled");
    } else {
      nav.classList.remove("is-scrolled");
      document.body.classList.remove("hc-nav-scrolled");
      document.body.classList.remove("hc-scrolled");
    }

    if (isProtected() || currentY <= 16 || currentY < lastScrollY) {
      nav.classList.remove("hc-nav-scroll-hidden");
    } else if (currentY > lastScrollY + 4) {
      nav.classList.add("hc-nav-scroll-hidden");
    }
    lastScrollY = currentY;
    ticking = false;
  }

  function requestScrollSync() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(onScroll);
  }

  syncNavHeight();
  onScroll();
  window.addEventListener("scroll", requestScrollSync, { passive: true });
  window.addEventListener("resize", syncNavHeight, { passive: true });
  nav.addEventListener("focusin", () => nav.classList.remove("hc-nav-scroll-hidden"));
  nav.addEventListener("focusout", requestScrollSync);
  nav.addEventListener("click", requestScrollSync);
});
