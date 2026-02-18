(() => {
  const btn = document.getElementById("hcCopyLinkBtn");
  if (!btn) return;

  async function copyText(text){
    // modern clipboard
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    // fallback
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }

  function showToast(message, ok){
    let t = document.getElementById("hcToast");
    if (!t){
      t = document.createElement("div");
      t.id = "hcToast";
      t.className = "hc-toast";
      t.innerHTML = `<span class="hc-toast__dot" aria-hidden="true"></span><span id="hcToastMsg"></span>`;
      document.body.appendChild(t);
    }

    t.classList.toggle("hc-toast--ok", !!ok);
    t.classList.toggle("hc-toast--bad", !ok);

    const msg = t.querySelector("#hcToastMsg");
    if (msg) msg.textContent = message;

    // show
    t.classList.add("hc-toast--show");

    clearTimeout(window.__hcToastTimer);
    window.__hcToastTimer = setTimeout(() => {
      t.classList.remove("hc-toast--show");
    }, 1400);
  }

  btn.addEventListener("click", async () => {
    try {
      await copyText(window.location.href);
      showToast("Lien copié", true);
      btn.classList.add("hc-copy-ok");
      setTimeout(() => btn.classList.remove("hc-copy-ok"), 600);
    } catch (e) {
      showToast("Impossible de copier", false);
    }
  });
})();
