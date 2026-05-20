document.addEventListener("DOMContentLoaded", function () {
  var printButtons = document.querySelectorAll("[data-hc-print-report]");
  var periodSelect = document.querySelector("[data-report-period-select]");

  printButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      window.print();
    });
  });

  if (periodSelect && periodSelect.form) {
    periodSelect.addEventListener("change", function () {
      periodSelect.form.submit();
    });
  }
});
