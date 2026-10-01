"use strict";

// Keep the secret out of request URLs, referrers and subsequent history entries.
const resetToken = document.getElementById("reset-token");
if (resetToken) {
  resetToken.value = window.location.hash.slice(1);
  window.history.replaceState(null, "", window.location.pathname);
}
