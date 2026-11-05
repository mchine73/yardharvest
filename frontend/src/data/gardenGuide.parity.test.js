// The garden guide ships in two languages as two hand-written modules.
// Nothing at runtime notices when they drift: a chapter added to the English
// only is simply missing on /es/about/guide, a slug typo in the Spanish
// redirects that chapter to the hub, and a paragraph left in English reads as
// finished to anyone reviewing in an English browser. These tests notice.
import { describe, it, expect } from 'vitest';
import * as en from './gardenGuide';
import * as es from './gardenGuide.es';

// Fields that are identifiers or markup, not prose: identical in both.
const SAME_FIELDS = new Set(['slug', 'icon']);

// Spanish strings allowed to equal their English source. Keep it short, and
// say why — anything else identical is an untranslated string.
const ALLOWED_SAME = new Set([
]);

/** Walk both modules in step, yielding [path, enValue, esValue] leaves. */
function* pairs(a, b, path) {
  if (typeof a === 'string' || typeof b === 'string') {
    yield [path, a, b];
    return;
  }
  if (Array.isArray(a)) {
    for (let i = 0; i < Math.max(a.length, b?.length ?? 0); i += 1) {
      yield* pairs(a[i], b?.[i], `${path}[${i}]`);
    }
    return;
  }
  if (a && typeof a === 'object') {
    for (const k of new Set([...Object.keys(a), ...Object.keys(b ?? {})])) {
      yield* pairs(a[k], b?.[k], `${path}.${k}`);
    }
    return;
  }
  yield [path, a, b];
}

const allPairs = [...pairs({ ...en }, { ...es }, 'guide')];
const fieldOf = (path) => path.match(/\.(\w+)(?:\[\d+\])?$/)[1];

describe('the Spanish guide mirrors the English one', () => {
  it('exports exactly the same names', () => {
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort());
  });

  it('has the same chapters, in the same order, with the same slugs and icons', () => {
    expect(es.CHAPTERS.map((c) => c.slug)).toEqual(en.CHAPTERS.map((c) => c.slug));
    expect(es.CHAPTERS.map((c) => c.icon)).toEqual(en.CHAPTERS.map((c) => c.icon));
  });

  it('has the same fields on every chapter and section', () => {
    en.CHAPTERS.forEach((c, i) => {
      expect(Object.keys(es.CHAPTERS[i]).sort()).toEqual(Object.keys(c).sort());
      c.sections.forEach((s, j) => {
        expect(Object.keys(es.CHAPTERS[i].sections[j] ?? {}).sort(),
          `${c.slug} section ${j}`).toEqual(Object.keys(s).sort());
      });
    });
  });

  it('has the same number of sections, paragraphs and list items per chapter', () => {
    const shape = (mod) => mod.CHAPTERS.map((c) => ({
      slug: c.slug,
      sections: c.sections.map((s) => ({ p: s.p.length, list: s.list ? s.list.length : 0 })),
    }));
    expect(shape(es)).toEqual(shape(en));
  });

  it('keeps every non-prose field identical', () => {
    const diffs = allPairs
      .filter(([path]) => SAME_FIELDS.has(fieldOf(path)))
      .filter(([, a, b]) => a !== b);
    expect(diffs).toEqual([]);
  });

  it('keeps every link target identical', () => {
    // Chapters link to each other by slug (checked above); any URL written
    // into the prose must survive translation untouched.
    const urls = (s) => (s.match(/https?:\/\/[^\s)”"]+/g) || []);
    const diffs = allPairs
      .filter(([, a, b]) => typeof a === 'string' && typeof b === 'string')
      .filter(([, a, b]) => urls(a).join(' ') !== urls(b).join(' '))
      .map(([path]) => path);
    expect(diffs).toEqual([]);
  });

  it('leaves no prose untranslated or empty', () => {
    const bad = allPairs
      .filter(([path]) => !SAME_FIELDS.has(fieldOf(path)))
      .filter(([path, a, b]) => typeof b !== 'string' || !b.trim()
        || (b === a && !ALLOWED_SAME.has(path)))
      .map(([path]) => path);
    expect(bad).toEqual([]);
  });
});

describe('the Spanish guide reads right', () => {
  const spanish = allPairs.map(([, , b]) => b).filter((b) => typeof b === 'string');

  it('says huerto, never jardín', () => {
    // The product's fixed term for a community garden; "jardín" is a flower
    // garden and reads as the wrong thing entirely.
    expect(spanish.filter((s) => /jard[ií]n/i.test(s))).toEqual([]);
  });

  it('gives the server everything it mirrors for crawler meta', () => {
    // app/seo.py mirrors GUIDE_TITLE + GUIDE_DESCRIPTION (hub) and each
    // chapter's title + description; Seo trims descriptions at 300 chars.
    for (const mod of [en, es]) {
      expect(mod.GUIDE_TITLE.trim()).not.toBe('');
      expect(mod.GUIDE_DESCRIPTION.length).toBeLessThanOrEqual(300);
      for (const c of mod.CHAPTERS) {
        expect(c.title.trim(), c.slug).not.toBe('');
        expect(c.description.trim(), c.slug).not.toBe('');
        expect(c.description.length, c.slug).toBeLessThanOrEqual(300);
      }
    }
  });

  it('has unique section headings within each chapter', () => {
    // Guide.jsx keys sections by heading; a duplicate drops one silently.
    for (const mod of [en, es]) {
      for (const c of mod.CHAPTERS) {
        const hs = c.sections.map((s) => s.h);
        expect(new Set(hs).size, c.slug).toBe(hs.length);
      }
    }
  });
});
