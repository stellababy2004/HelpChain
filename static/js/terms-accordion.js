(function () {
  function initTermsAccordion() {
    document.querySelectorAll(".hc-terms-reading > section").forEach(function (section) {
      var heading = section.querySelector("h2");
      if (!heading) return;

      var details = document.createElement("details");
      details.className = "hc-terms-accordion";

      var summary = document.createElement("summary");
      summary.innerHTML = heading.innerHTML;
      details.appendChild(summary);

      Array.from(section.children).forEach(function (child) {
        if (child !== heading) details.appendChild(child);
      });
      section.replaceWith(details);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTermsAccordion, { once: true });
  } else {
    initTermsAccordion();
  }
})();
