(() => {
  const rows = Array.from(document.querySelectorAll("[data-request-id]"));
  if (!rows.length) return;

  const citySelect = document.getElementById("hcFilterCity");
  const serviceSelect = document.getElementById("hcFilterService");
  const prioritySelect = document.getElementById("hcFilterPriority");

  if (!citySelect || !serviceSelect || !prioritySelect) return;

  const normalize = (v) => String(v || "").trim().toLowerCase();

  const uniqueSorted = (values) =>
    Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));

  const cityValues = uniqueSorted(rows.map((r) => normalize(r.dataset.city)));
  const serviceValues = uniqueSorted(rows.map((r) => normalize(r.dataset.service)));

  const appendOptions = (select, values, emptyLabel) => {
    if (!select) return;
    select.innerHTML = `<option value="">${emptyLabel}</option>`;
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value
        .split(" ")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
      select.appendChild(option);
    });
  };

  appendOptions(citySelect, cityValues, "Ville");
  appendOptions(serviceSelect, serviceValues, "Service");

  const applyFilters = () => {
    const selectedCity = normalize(citySelect.value);
    const selectedService = normalize(serviceSelect.value);
    const selectedPriority = normalize(prioritySelect.value);

    rows.forEach((row) => {
      const rowCity = normalize(row.dataset.city);
      const rowService = normalize(row.dataset.service);
      const rowPriority = normalize(row.dataset.priorityLabel || row.dataset.priority);

      const matchCity = !selectedCity || rowCity === selectedCity;
      const matchService = !selectedService || rowService === selectedService;
      const matchPriority = !selectedPriority || rowPriority === selectedPriority;

      row.style.display = matchCity && matchService && matchPriority ? "" : "none";
    });
  };

  citySelect.addEventListener("change", applyFilters);
  serviceSelect.addEventListener("change", applyFilters);
  prioritySelect.addEventListener("change", applyFilters);
})();
