// Sync editable anchors with their corresponding inputs
if (typeof document !== 'undefined') {
  document.querySelectorAll('[contenteditable][data-target]').forEach(el => {
    el.addEventListener('blur', () => {
      const campo = document.getElementById(el.dataset.target);
      if (campo) campo.value = el.innerText.trim();
    });
  });
}
