document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("dev-bootstrap-btn");
  const status = document.getElementById("dev-bootstrap-status");

  if (!button || !status) return;

  const defaultLabel = button.textContent.trim();
  const pendingLabel = "Initialisation système...";

  function setStatus(kind, message) {
    status.textContent = message;
    status.className = `alert mt-3 mb-0 alert-${kind}`;
    status.hidden = false;
  }

  function resetButton() {
    button.disabled = false;
    button.textContent = defaultLabel;
  }

  button.addEventListener("click", async (event) => {
    event.preventDefault();

    button.disabled = true;
    button.textContent = pendingLabel;
    status.hidden = true;
    status.textContent = "";

    const headers = {
      "X-Requested-With": "XMLHttpRequest",
      "Accept": "application/json"
    };

    const csrfInput = document.querySelector('input[name="csrf_token"]');
    if (csrfInput && csrfInput.value) {
      headers["X-CSRFToken"] = csrfInput.value;
    }

    const endpoint = new URL("/admin/dev/bootstrap", window.location.origin).toString();

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: headers,
        credentials: "same-origin",
        cache: "no-store"
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.ok) {
        setStatus("success", "Système prêt.");
        window.location.reload();
        return;
      }

      setStatus("danger", data.error || "L'initialisation du système a échoué.");
      resetButton();
    } catch (error) {
      setStatus("danger", "Impossible de joindre le serveur. Réessayez dans un instant.");
      resetButton();
    }
  });
});
