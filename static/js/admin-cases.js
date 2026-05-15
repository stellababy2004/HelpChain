(() => {
  const rows = Array.from(document.querySelectorAll(".hc-case-row"));
  if (!rows.length) return;

  const isInteractive = (el) =>
    !!el?.closest(
      "a, button, input, select, textarea, label, form, [role='button'], [data-no-rowclick]"
    );

  const getRowHref = (row) => {
    const detailLink = row.querySelector("a[href*='/cases/']");
    return detailLink ? detailLink.getAttribute("href") : "";
  };

  rows.forEach((row) => {
    const href = getRowHref(row);
    if (!href) return;

    row.classList.add("hc-case-row--clickable");
    row.tabIndex = 0;
    row.setAttribute("role", "link");

    row.addEventListener("click", (event) => {
      if (isInteractive(event.target)) return;
      window.location.href = href;
    });

    row.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      if (isInteractive(event.target)) return;
      event.preventDefault();
      window.location.href = href;
    });
  });
})();
