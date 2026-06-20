import { useEffect } from 'react';

/**
 * Gentle reveal-on-scroll for any elements carrying the `.yh-reveal` class
 * (styling lives in App.css under `.yh-animate .yh-reveal`).
 *
 * Adds `body.yh-animate` — which arms the hidden pre-reveal state — only when
 * IntersectionObserver is available and the user hasn't requested reduced
 * motion, so content is never left hidden if this can't run. Pass a deps array
 * to re-scan after async content renders.
 */
export default function useScrollReveal(deps = []) {
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !('IntersectionObserver' in window)) return;
    document.body.classList.add('yh-animate');
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0, rootMargin: '0px 0px -12% 0px' });
    document.querySelectorAll('.yh-reveal').forEach((el) => io.observe(el));
    return () => { io.disconnect(); document.body.classList.remove('yh-animate'); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
