(function () {
  const form = document.querySelector(".hc-intervenants-form[data-geocode-url]");
  if (!form) {
    return;
  }

  const cityInput = document.getElementById("city");
  const addressInput = document.getElementById("address");
  const latitudeInput = document.getElementById("latitude");
  const longitudeInput = document.getElementById("longitude");
  const hintNode = document.getElementById("hcIntervenantGeoHint");

  if (!cityInput || !addressInput || !latitudeInput || !longitudeInput || !hintNode) {
    return;
  }

  const debounceMs = 700;
  const timeoutMs = 4500;
  let debounceHandle = null;
  let activeController = null;
  let requestToken = 0;
  let manualCoordsDirty = false;
  let isApplyingAutofill = false;
  let lastAddressKey = "";

  const setHint = (message) => {
    hintNode.textContent = message || "";
  };

  const currentAddressKey = () => `${addressInput.value.trim()}|${cityInput.value.trim()}`;

  const handleManualCoordinateInput = () => {
    if (!isApplyingAutofill) {
      manualCoordsDirty = true;
    }
  };

  const scheduleGeocode = () => {
    const nextKey = currentAddressKey();
    if (nextKey !== lastAddressKey) {
      manualCoordsDirty = false;
      lastAddressKey = nextKey;
    }

    if (debounceHandle) {
      window.clearTimeout(debounceHandle);
    }

    const address = addressInput.value.trim();
    const city = cityInput.value.trim();
    if (!address || !city) {
      setHint("");
      return;
    }

    debounceHandle = window.setTimeout(() => {
      const token = ++requestToken;
      if (activeController) {
        activeController.abort();
      }
      activeController = new AbortController();
      const timeoutHandle = window.setTimeout(() => activeController.abort(), timeoutMs);
      setHint("Recherche automatique des coordonnees...");

      const url = new URL(form.dataset.geocodeUrl, window.location.origin);
      url.searchParams.set("address", address);
      url.searchParams.set("city", city);

      fetch(url.toString(), {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: activeController.signal,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          if (token !== requestToken) {
            return;
          }
          if (!data || !data.ok) {
            setHint("Coordonnees introuvables - vous pouvez les saisir manuellement");
            return;
          }
          if (manualCoordsDirty) {
            setHint("Coordonnees modifiees manuellement");
            return;
          }

          isApplyingAutofill = true;
          latitudeInput.value = data.latitude ?? "";
          longitudeInput.value = data.longitude ?? "";
          isApplyingAutofill = false;
          setHint("Coordonnees detectees automatiquement");
        })
        .catch(() => {
          if (token === requestToken) {
            setHint("Coordonnees introuvables - vous pouvez les saisir manuellement");
          }
        })
        .finally(() => {
          window.clearTimeout(timeoutHandle);
        });
    }, debounceMs);
  };

  addressInput.addEventListener("input", scheduleGeocode);
  cityInput.addEventListener("input", scheduleGeocode);
  latitudeInput.addEventListener("input", handleManualCoordinateInput);
  longitudeInput.addEventListener("input", handleManualCoordinateInput);

  lastAddressKey = currentAddressKey();
  if (
    addressInput.value.trim()
    && cityInput.value.trim()
    && !latitudeInput.value.trim()
    && !longitudeInput.value.trim()
  ) {
    scheduleGeocode();
  }
}());
