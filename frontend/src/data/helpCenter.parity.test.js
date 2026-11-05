// The Help Center ships in two files: helpCenter.js (English) and
// helpCenter.es.js (Spanish). Help.jsx picks one by page language, so the two
// must stay the same SHAPE — same exports, categories, slugs, order, sections,
// paragraph/step/list counts, `pro` flags, price tokens and link targets. An
// edit to one file that forgets the other is exactly what this catches:
//   * an article added in English only would 404 → redirect on /es/help/<slug>;
//   * a paragraph added in English only would silently be missing in Spanish;
//   * a translated or dropped {{TOKEN}} renders literally, or loses the price;
//   * a Spanish string left identical to the English is an untranslated one.
import { describe, it, expect } from 'vitest';

import * as en from './helpCenter';
import * as es from './helpCenter.es';
import enCatalog from '../i18n/locales/en/common.json';
import esCatalog from '../i18n/locales/es/common.json';

const ALLOWED_TOKENS = ['PRO_MONTHLY', 'PRO_YEARLY', 'TRIAL_DAYS'];

// Strings that are legitimately the same in both languages: product names.
const SAME_IN_BOTH = new Set(['Garden Pro']);

// Section fields that hold prose; anything else (`pro`) is structural.
const TEXT_FIELDS = ['h', 'warn', 'tip'];
const LIST_FIELDS = ['p', 'steps', 'list'];
const ARTICLE_TEXT = ['title', 'tagline', 'description', 'keywords'];

const tokensIn = (s) => (s.match(/\{\{\s*[^}]*\}\}/g) || [])
  .map((t) => t.replace(/[{}\s]/g, '')).sort();

// Anything that would become a link if the renderer ever grew one: absolute
// URLs, and in-app paths written as /something.
const linksIn = (s) => [
  ...(s.match(/https?:\/\/[^\s)»"”']+/g) || []),
  ...(s.match(/(?:^|[\s(«"“])(\/[a-z][\w\-/]*)/g) || []).map((m) => m.trim().replace(/^[(«"“]/, '')),
].sort();

/** Every prose string of an article, labelled by where it lives. */
function strings(article) {
  const out = ARTICLE_TEXT.map((k) => [k, article[k]]);
  article.sections.forEach((s, i) => {
    for (const k of TEXT_FIELDS) if (s[k] !== undefined) out.push([`s${i}.${k}`, s[k]]);
    for (const k of LIST_FIELDS) {
      (s[k] || []).forEach((v, j) => out.push([`s${i}.${k}[${j}]`, v]));
    }
  });
  return out;
}

const pairs = en.ARTICLES.map((a, i) => [a, es.ARTICLES[i]]);

describe('help center: Spanish mirrors English', () => {
  it('exports the same names, of the same kinds', () => {
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort());
    for (const name of Object.keys(en)) {
      expect(typeof es[name], name).toBe(typeof en[name]);
    }
  });

  it('has the same price-fallback tokens', () => {
    expect(Object.keys(es.PRICE_FALLBACKS).sort()).toEqual(ALLOWED_TOKENS.slice().sort());
    expect(Object.keys(en.PRICE_FALLBACKS).sort()).toEqual(ALLOWED_TOKENS.slice().sort());
  });

  it('has the same categories, in order, with the same icons', () => {
    expect(es.CATEGORIES.map((c) => [c.key, c.icon]))
      .toEqual(en.CATEGORIES.map((c) => [c.key, c.icon]));
    for (const c of es.CATEGORIES) {
      expect(c.title, c.key).toBeTruthy();
      expect(c.blurb, c.key).toBeTruthy();
    }
  });

  it('has the same articles, in order, in the same categories', () => {
    expect(es.ARTICLES.map((a) => [a.slug, a.category]))
      .toEqual(en.ARTICLES.map((a) => [a.slug, a.category]));
  });

  it('gives every article a Spanish title, tagline, description and keywords', () => {
    // title + description feed <Seo> and the server's HELP_META mirror.
    for (const a of es.ARTICLES) {
      for (const k of ARTICLE_TEXT) {
        expect(typeof a[k] === 'string' && a[k].trim().length > 0, `${a.slug}.${k}`).toBe(true);
      }
    }
  });

  it('has the same sections, field shapes, counts and Pro flags', () => {
    for (const [a, b] of pairs) {
      expect(b.sections.length, a.slug).toBe(a.sections.length);
      a.sections.forEach((s, i) => {
        const t = b.sections[i];
        const where = `${a.slug} section ${i}`;
        expect(Object.keys(t).sort(), where).toEqual(Object.keys(s).sort());
        expect(Boolean(t.pro), where).toBe(Boolean(s.pro));
        for (const k of LIST_FIELDS) {
          expect((t[k] || []).length, `${where} ${k}`).toBe((s[k] || []).length);
        }
      });
    }
  });

  it('keeps every {{TOKEN}} exactly, string by string', () => {
    for (const [a, b] of pairs) {
      const esStrings = Object.fromEntries(strings(b));
      for (const [where, text] of strings(a)) {
        expect(tokensIn(esStrings[where]), `${a.slug} ${where}`).toEqual(tokensIn(text));
      }
    }
  });

  it('uses no token outside the three the page knows how to fill', () => {
    const all = [en, es].flatMap((mod) => mod.ARTICLES.flatMap((a) => strings(a)))
      .flatMap(([, text]) => tokensIn(text));
    expect(all.filter((t) => !ALLOWED_TOKENS.includes(t))).toEqual([]);
  });

  it('keeps the same link targets', () => {
    for (const [a, b] of pairs) {
      const target = (art) => strings(art).flatMap(([, text]) => linksIn(text)).sort();
      expect(target(b), a.slug).toEqual(target(a));
    }
  });

  it('leaves no Spanish string identical to its English counterpart', () => {
    const same = [];
    const check = (where, x, y) => {
      if (x === y && !SAME_IN_BOTH.has(x)) same.push(`${where}: ${x}`);
    };
    for (const k of ['HELP_TITLE', 'HELP_DESCRIPTION', 'HELP_INTRO']) check(k, en[k], es[k]);
    en.CATEGORIES.forEach((c, i) => {
      check(`${c.key}.title`, c.title, es.CATEGORIES[i].title);
      check(`${c.key}.blurb`, c.blurb, es.CATEGORIES[i].blurb);
    });
    for (const [a, b] of pairs) {
      const esStrings = Object.fromEntries(strings(b));
      for (const [where, text] of strings(a)) check(`${a.slug} ${where}`, text, esStrings[where]);
    }
    expect(same).toEqual([]);
  });

  it('keeps the helpers working on each language\'s own articles', () => {
    for (const mod of [en, es]) {
      for (const a of mod.ARTICLES) expect(mod.findArticle(a.slug)).toBe(a);
      expect(mod.findArticle('no-such-article')).toBeNull();
      expect(mod.CATEGORIES.flatMap((c) => mod.articlesIn(c.key)))
        .toHaveLength(mod.ARTICLES.length);
      expect(mod.searchArticles('   ')).toEqual([]);
    }
  });

  it('finds something for every search the placeholder suggests', () => {
    // The search box tells people what to try; each suggestion must work in
    // its own language. English quotes “x”, Spanish «x».
    const suggestions = (text) => [...text.matchAll(/[“«]([^”»]+)[”»]/g)].map((m) => m[1]);
    const enHints = suggestions(enCatalog.help.searchPlaceholder);
    const esHints = suggestions(esCatalog.help.searchPlaceholder);
    expect(enHints.length).toBeGreaterThan(0);
    expect(esHints.length).toBe(enHints.length);
    for (const q of enHints) expect(en.searchArticles(q).length, q).toBeGreaterThan(0);
    for (const q of esHints) expect(es.searchArticles(q).length, q).toBeGreaterThan(0);
  });

  it('ignores accents in Spanish search', () => {
    expect(es.searchArticles('deposito').map((a) => a.slug))
      .toEqual(es.searchArticles('depósito').map((a) => a.slug));
    expect(es.searchArticles('diseñador').length).toBeGreaterThan(0);
    expect(es.searchArticles('disenador').length).toBeGreaterThan(0);
  });
});
