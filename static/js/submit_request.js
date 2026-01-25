// --- Sticky CTA: hide when the real submit button is visible ---
(() => {
  const bar = document.querySelector(".hc-sticky-cta");
  if (!bar) return;

  // Exclude the sticky bar's own submit button.
  const form = bar.closest("form") || document.querySelector("form");
  const realSubmit =
    form?.querySelector(
      'button[type="submit"]:not(.hc-sticky-cta__submit), input[type="submit"]:not(.hc-sticky-cta__submit)',
    ) || null;

  if (!realSubmit) return;

  if (!("IntersectionObserver" in window)) {
    bar.classList.add("is-visible");
    bar.classList.remove("is-hidden");
    return;
  }

  // Treat the bottom area occupied by the sticky bar as "not visible",
  // otherwise we may hide the bar while the real submit is still behind it.
  const barHeight = Math.ceil(bar.getBoundingClientRect().height || 0);
  const bottomMargin = Math.min(240, Math.max(80, barHeight + 16));

  const io = new IntersectionObserver(
    (entries) => {
      const isVisible = entries[0]?.isIntersecting === true;
      bar.classList.toggle("is-visible", !isVisible);
      bar.classList.toggle("is-hidden", isVisible);
    },
    {
      threshold: 0.15,
      rootMargin: `0px 0px -${bottomMargin}px 0px`,
    },
  );

  io.observe(realSubmit);
})();

