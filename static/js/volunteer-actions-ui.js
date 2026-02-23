(function () {
  function showToast(msg) {
    const el = document.getElementById("hc-toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("is-on");
    window.clearTimeout(el._t);
    el._t = window.setTimeout(() => el.classList.remove("is-on"), 1800);
  }

  document.addEventListener(
    "submit",
    (e) => {
      const form = e.target;
      if (!form.matches("[data-hc-action-form='1']")) return;

      const btns = form.querySelectorAll("button[type='submit'], input[type='submit']");
      btns.forEach((b) => {
        b.disabled = true;
        b.dataset.prevText = b.textContent || "";
        if (b.tagName.toLowerCase() === "button") b.textContent = "Saved";
      });

      showToast("Action saved.");
    },
    true
  );
})();
