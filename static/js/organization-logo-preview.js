(() => {
  const file = document.getElementById("hc-org-logo-file");
  const img = document.getElementById("hc-org-logo-preview");
  const placeholder = document.getElementById("hc-org-logo-placeholder");
  const saved = document.getElementById("hc-org-logo-saved");
  const zoom = document.getElementById("hc-org-logo-zoom");
  const reset = document.getElementById("hc-org-logo-reset");
  const error = document.getElementById("hc-org-logo-error");

  if (!file || !img || !zoom || !reset) return;

  const form = file.closest("form");
  let offsetX = 0;
  let offsetY = 0;
  let drag = null;
  let originalFile = null;
  let submitting = false;

  const applyTransform = () => {
    const scale = Number(zoom.value) / 100;
    img.style.transform =
      `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
  };

  function clear() {
    img.removeAttribute("src");
    img.hidden = true;
    placeholder.hidden = Boolean(saved);
    if (saved) saved.hidden = false;
    zoom.value = "100";
    zoom.disabled = true;
    reset.disabled = true;
    offsetX = 0;
    offsetY = 0;
    drag = null;
    originalFile = null;
    img.style.transform = "";
  }

  file.addEventListener("change", () => {
    clear();
    error.textContent = "";

    const selected = file.files && file.files[0];
    if (!selected) return;

    if (
      !["image/png", "image/jpeg", "image/webp"].includes(selected.type) ||
      selected.size > 2 * 1024 * 1024
    ) {
      error.textContent = "Format non accepté ou fichier supérieur à 2 Mo.";
      file.value = "";
      return;
    }

    originalFile = selected;

    img.onload = () => {
      img.hidden = false;
      placeholder.hidden = true;
      if (saved) saved.hidden = true;
      zoom.disabled = false;
      reset.disabled = false;
      error.textContent = "Aperçu prêt. Ajustez puis enregistrez.";
    };

    img.onerror = () => {
      clear();
      file.value = "";
      error.textContent = "Impossible de lire cette image.";
    };

    const reader = new FileReader();
    reader.onload = () => { img.src = reader.result; };
    reader.onerror = () => {
      clear();
      file.value = "";
      error.textContent = "Impossible de lire cette image.";
    };
    reader.readAsDataURL(selected);
  });

  zoom.addEventListener("input", applyTransform);

  img.addEventListener("pointerdown", (event) => {
    if (img.hidden) return;
    drag = {
      x: event.clientX,
      y: event.clientY,
      startX: offsetX,
      startY: offsetY
    };
    img.setPointerCapture(event.pointerId);
    img.style.cursor = "grabbing";
  });

  img.addEventListener("pointermove", (event) => {
    if (!drag) return;
    offsetX = Math.max(-144, Math.min(
      144, drag.startX + event.clientX - drag.x
    ));
    offsetY = Math.max(-144, Math.min(
      144, drag.startY + event.clientY - drag.y
    ));
    applyTransform();
  });

  const endDrag = () => {
    drag = null;
    img.style.cursor = "grab";
  };

  img.addEventListener("pointerup", endDrag);
  img.addEventListener("pointercancel", endDrag);

  reset.addEventListener("click", () => {
    zoom.value = "100";
    offsetX = 0;
    offsetY = 0;
    applyTransform();
  });

  form.addEventListener("submit", async (event) => {
    if (submitting || !originalFile || img.hidden) return;

    event.preventDefault();

    try {
      const canvas = document.createElement("canvas");
      canvas.width = 288;
      canvas.height = 288;

      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas unavailable");

      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, 288, 288);

      const scale = Number(zoom.value) / 100;
      const baseScale = Math.min(
        144 / img.naturalWidth,
        144 / img.naturalHeight
      );

      const width = img.naturalWidth * baseScale * scale * 2;
      const height = img.naturalHeight * baseScale * scale * 2;

      ctx.drawImage(
        img,
        144 + offsetX * 2 - width / 2,
        144 + offsetY * 2 - height / 2,
        width,
        height
      );

      const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/png")
      );

      if (!blob) throw new Error("PNG generation failed");

      const processed = new File(
        [blob],
        "organization-logo.png",
        { type: "image/png" }
      );

      const transfer = new DataTransfer();
      transfer.items.add(processed);
      file.files = transfer.files;

      submitting = true;
      form.requestSubmit();
    } catch (e) {
      error.textContent = "Impossible de préparer le logo.";
    }
  });

  window.addEventListener("pagehide", clear, { once: true });
})();
