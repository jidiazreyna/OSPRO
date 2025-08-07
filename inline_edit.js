// Sync editable anchors with their corresponding inputs
if (typeof document !== 'undefined') {
  const sync = (el) => {
    const campo = document.getElementById(el.dataset.target);
    if (campo) campo.value = el.innerText.trim();
  };

  // Update when the element loses focus
  document.addEventListener(
    'blur',
    (ev) => {
      const el = ev.target.closest('[contenteditable][data-target]');
      if (el) sync(el);
    },
    true,
  );

  // Commit edits with Ctrl+Enter (or Cmd+Enter)
  document.addEventListener(
    'keydown',
    (ev) => {
      const el = ev.target.closest('[contenteditable][data-target]');
      if (!el) return;
      if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
        ev.preventDefault();
        sync(el);
        el.blur();
      }
    },
    true,
  );
}
