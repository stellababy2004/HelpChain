(() => {
  let deferredInstallPrompt = null;
  const promptEl = document.getElementById("hcInstallPrompt");
  const actionEl = document.getElementById("hcInstallAction");
  const closeEl = document.getElementById("hcInstallClose");
  const textEl = document.getElementById("hcInstallText");
  const mobileInstallItem = document.getElementById("hcMobileInstallItem");
  const footerInstallLink = document.getElementById("hcFooterInstallLink");
  const footerInstallSeparator = document.getElementById("hcFooterInstallSeparator");
  const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  const isIos = /iphone|ipad|ipod/i.test(window.navigator.userAgent);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  }

  const closePrompt = () => {
    if (promptEl) promptEl.hidden = true;
  };

  const setInstallAccess = (visible) => {
    [mobileInstallItem, footerInstallLink, footerInstallSeparator].forEach((element) => {
      if (element) element.hidden = !visible;
    });
  };

  const preparePrompt = () => {
    if (isIos && textEl) {
      textEl.textContent = textEl.dataset.iosMessage || textEl.textContent;
      if (actionEl) {
        actionEl.hidden = true;
      }
    } else if (actionEl) {
      actionEl.hidden = false;
    }
  };

  const openPrompt = (event) => {
    event?.preventDefault();
    if (!promptEl || standalone) return;
    preparePrompt();
    promptEl.hidden = false;
    closeEl?.focus();
  };

  if (standalone) {
    setInstallAccess(false);
    closePrompt();
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    if (!standalone) setInstallAccess(true);
  });

  if (isIos && !standalone) {
    setInstallAccess(true);
  }

  mobileInstallItem?.querySelector("a")?.addEventListener("click", openPrompt);
  footerInstallLink?.addEventListener("click", openPrompt);

  actionEl?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    closePrompt();
  });
  closeEl?.addEventListener("click", closePrompt);
  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    setInstallAccess(false);
    closePrompt();
  });
})();
