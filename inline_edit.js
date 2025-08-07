// Sync editable anchors with their corresponding inputs
if (typeof document !== 'undefined') {
  document.addEventListener(
    'blur',
    (ev) => {
      const el = ev.target.closest('[contenteditable][data-target]');
      if (!el) return;
      const campo = document.getElementById(el.dataset.target);
      if (campo) campo.value = el.innerText.trim();
    },
    true,
  );
}
