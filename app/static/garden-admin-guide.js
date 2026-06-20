/* Garden Admin Guide — feature numbering + gentle scroll-reveal.
   Loaded as an external file (not inline) because the site CSP for non-CRM
   pages is script-src 'self' (no 'unsafe-inline'), which blocks inline scripts. */
(function () {
  // Number each feature row (the "1, 2, 3 …" count) — chip pops in on reveal.
  document.querySelectorAll('.feature').forEach(function (f, i) {
    var t = f.querySelector('.ftext');
    if (!t) return;
    var n = document.createElement('div');
    n.className = 'fnum';
    n.setAttribute('aria-hidden', 'true');
    n.textContent = (i + 1);
    t.insertBefore(n, t.firstChild);
  });

  // Gentle reveal-on-scroll. Only arm it when supported + motion allowed, so the
  // page is never left hidden by the .reveal opacity:0 if the script can't run.
  if (!('IntersectionObserver' in window) ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // Light stagger within the card grids.
  ['.steps .step', '.tips .tip', '.plans .plan'].forEach(function (g) {
    document.querySelectorAll(g).forEach(function (el, i) {
      el.style.setProperty('--rd', (i * 0.08) + 's');
    });
  });

  var els = Array.prototype.slice.call(document.querySelectorAll(
    '.eyebrow, .hero h1, .hero p.lead, .hero-cta, .hero-figure, .section-head, ' +
    '.step, .feature, .tip, .plan, .cta, .faq details'));
  els.forEach(function (el) { el.classList.add('reveal'); });

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
  els.forEach(function (el) { io.observe(el); });
})();
