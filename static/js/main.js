// MyFuture — main.js
// Piccole utility generali usate in tutte le pagine

document.addEventListener('DOMContentLoaded', () => {
  syncViewportHeight();

  // Auto-rimuovi flash messages dopo 4 secondi
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => el.remove(), 4000);
  });

  // Animazione anelli match (dashboard)
  animateMatchRings();
});

window.addEventListener('resize', syncViewportHeight);
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', syncViewportHeight);
  window.visualViewport.addEventListener('scroll', syncViewportHeight);
}

function syncViewportHeight() {
  const viewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
  document.documentElement.style.setProperty('--app-height', `${viewportHeight}px`);
}

function animateMatchRings() {
  const rings = document.querySelectorAll('.ring-fill');
  rings.forEach((ring, i) => {
    const target = parseFloat(ring.style.strokeDasharray);
    if (!target) return;
    ring.style.strokeDasharray = '0 175.9';
    setTimeout(() => {
      ring.style.transition = 'stroke-dasharray 1s ease';
      // valore già impostato inline nel template
    }, 300 + i * 150);
  });
}
