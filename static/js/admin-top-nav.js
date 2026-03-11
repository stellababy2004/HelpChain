(function () {
  function initAdminTopNav() {
    var audioTrigger = document.querySelector("[data-hc-a11y-open-audio='true']");
    if (!audioTrigger) return;

    audioTrigger.addEventListener("click", function () {
      var openA11y = document.getElementById("hcA11yBtn");
      if (openA11y) openA11y.click();

      window.setTimeout(function () {
        var audioTab = document.getElementById("hcA11yTabAudio");
        if (audioTab) audioTab.click();
      }, 60);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAdminTopNav);
    return;
  }
  initAdminTopNav();
})();
