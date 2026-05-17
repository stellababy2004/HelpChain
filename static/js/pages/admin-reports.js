document.addEventListener("DOMContentLoaded", function () {
  var printButtons = document.querySelectorAll("[data-hc-print-report]");

  printButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      window.print();
    });
  });
});
