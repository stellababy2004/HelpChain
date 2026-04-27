
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-proposal-print]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      window.print();
    });
  });
});
