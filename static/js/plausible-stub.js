// Plausible queue stub.
// Keeps calls safe when the Plausible script is delayed/blocked/not loaded.
(function () {
  window.plausible =
    window.plausible ||
    function () {
      (window.plausible.q = window.plausible.q || []).push(arguments);
    };
})();
