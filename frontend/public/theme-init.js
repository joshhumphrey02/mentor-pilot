// Applies the saved theme before first paint to avoid a light/dark flash.
// Kept as an external file (not inline) so the CSP can stay `script-src 'self'`.
;(function () {
  try {
    var theme = localStorage.getItem('mp-theme') || 'system'
    var dark =
      theme === 'dark' ||
      (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    document.documentElement.classList.toggle('dark', dark)
  } catch {
    /* storage blocked: fall back to the light theme */
  }
})()
