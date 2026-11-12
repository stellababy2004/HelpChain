(() => {
      const file = document.getElementById('hc-org-logo-file');
      const img = document.getElementById('hc-org-logo-preview');
      const placeholder = document.getElementById('hc-org-logo-placeholder');
      const saved = document.getElementById('hc-org-logo-saved');
      const zoom = document.getElementById('hc-org-logo-zoom');
      const reset = document.getElementById('hc-org-logo-reset');
      const error = document.getElementById('hc-org-logo-error');
      let offsetX = 0, offsetY = 0, drag = null;
      const applyTransform = () => { img.style.transform = 'translate(' + offsetX + 'px,' + offsetY + 'px) scale(' + Number(zoom.value)/100 + ')'; };
      function clear() {
        img.removeAttribute('src');
        img.hidden = true;
        placeholder.hidden = Boolean(saved);
        if (saved) saved.hidden = false;
        zoom.value = '100';
        zoom.disabled = true;
        reset.disabled = true;
        offsetX = 0; offsetY = 0; drag = null;
        img.style.transform = '';
      }
      file.addEventListener('change', () => {
        clear();
        const selected = file.files && file.files[0];
        if (!selected) return;
        if (!['image/png','image/jpeg','image/webp'].includes(selected.type) || selected.size > 2 * 1024 * 1024) {
          error.textContent = 'Format non accepté ou fichier supérieur à 2 Mo.';
          file.value = '';
          return;
        }
        img.onload = () => {
          img.hidden = false;
          placeholder.hidden = true;
          if (saved) saved.hidden = true;
          zoom.disabled = false;
          reset.disabled = false;
          error.textContent = 'Aperçu prêt. Cliquez sur Enregistrer le logo.';
        };
        img.onerror = () => {
          clear();
          file.value = '';
          error.textContent = 'Impossible de lire cette image.';
        };
        const reader = new FileReader();
        reader.onload = () => { img.src = reader.result; };
        reader.onerror = () => {
          clear();
          file.value = '';
          error.textContent = 'Impossible de lire cette image.';
        };
        reader.readAsDataURL(selected);
      });
      zoom.addEventListener('input', applyTransform);
      img.addEventListener('pointerdown', (event) => {
        if (img.hidden) return;
        drag = {x: event.clientX, y: event.clientY, startX: offsetX, startY: offsetY};
        img.setPointerCapture(event.pointerId);
        img.style.cursor = 'grabbing';
      });
      img.addEventListener('pointermove', (event) => {
        if (!drag) return;
        offsetX = Math.max(-144, Math.min(144, drag.startX + event.clientX - drag.x));
        offsetY = Math.max(-144, Math.min(144, drag.startY + event.clientY - drag.y));
        applyTransform();
      });
      const endDrag = () => { drag = null; img.style.cursor = 'grab'; };
      img.addEventListener('pointerup', endDrag);
      img.addEventListener('pointercancel', endDrag);
      reset.addEventListener('click', () => { zoom.value = '100'; offsetX = 0; offsetY = 0; applyTransform(); });
      window.addEventListener('pagehide', clear, {once:true});
    })();
