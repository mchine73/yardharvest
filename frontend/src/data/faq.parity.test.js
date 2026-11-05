// The FAQ exists twice, once per language. Everything but the words must be
// identical, or a Spanish reader gets a different set of questions, a link to
// a page that is not there, or a price token printed literally.
import { describe, it, expect } from 'vitest';

import * as en from './faq';
import * as es from './faq.es';
import * as helpEn from './helpCenter';

const TOKEN = /\{\{[A-Z_]+\}\}/g;
const tokens = (s) => (String(s || '').match(TOKEN) || []).sort();
const TEXT = ['q', 'a', 'aFee', 'aNoPrice'];

describe('the two FAQ modules', () => {
  it('export the same names', () => {
    expect(Object.keys(es).sort()).toEqual(Object.keys(en).sort());
  });

  it('have the same topics in the same order', () => {
    const shape = (cats) => cats.map(({ key, icon }) => ({ key, icon }));
    expect(shape(es.CATEGORIES)).toEqual(shape(en.CATEGORIES));
  });

  it('ask the same questions in the same order, with the same flags and links', () => {
    const shape = (qs) => qs.map((q) => ({
      id: q.id, category: q.category, featured: !!q.featured,
      needsPricing: !!q.needsPricing, link: q.link?.to || null,
      variants: TEXT.filter((f) => q[f]),
    }));
    expect(shape(es.QUESTIONS)).toEqual(shape(en.QUESTIONS));
  });

  it('keep the same price tokens in every answer', () => {
    for (const [i, q] of en.QUESTIONS.entries()) {
      for (const f of TEXT) {
        expect([q.id, f, tokens(es.QUESTIONS[i][f])]).toEqual([q.id, f, tokens(q[f])]);
      }
    }
  });

  it('never leave Spanish identical to the English', () => {
    const same = en.QUESTIONS.flatMap((q, i) => [...TEXT, 'link']
      .filter((f) => q[f] && (f === 'link'
        ? q.link.label === es.QUESTIONS[i].link.label
        : q[f] === es.QUESTIONS[i][f]))
      .map((f) => `${q.id}.${f}`));
    expect(same).toEqual([]);
  });
});

describe('the FAQ content', () => {
  for (const [lang, mod] of [['en', en], ['es', es]]) {
    it(`${lang}: has unique ids and only known topics, each used`, () => {
      const ids = mod.QUESTIONS.map((q) => q.id);
      expect(new Set(ids).size).toBe(ids.length);
      const keys = mod.CATEGORIES.map((c) => c.key);
      expect(mod.QUESTIONS.filter((q) => !keys.includes(q.category))).toEqual([]);
      expect(keys.filter((k) => !mod.QUESTIONS.some((q) => q.category === k))).toEqual([]);
    });

    it(`${lang}: can always say something honest about a price`, () => {
      // An answer with a price in it needs words for when pricing failed to
      // load, or must be left out; printing "{{PRO_MONTHLY}}" is not an option.
      const stuck = mod.QUESTIONS.filter((q) => tokens(q.a).length && !q.aNoPrice && !q.needsPricing);
      expect(stuck.map((q) => q.id)).toEqual([]);
      expect(mod.QUESTIONS.filter((q) => tokens(q.aNoPrice).length).map((q) => q.id)).toEqual([]);
    });

    it(`${lang}: features only questions the home page can answer without pricing`, () => {
      const featured = mod.QUESTIONS.filter((q) => q.featured);
      expect(featured.length).toBeGreaterThanOrEqual(4);
      expect(featured.filter((q) => q.needsPricing || tokens(q.a).length).map((q) => q.id)).toEqual([]);
    });

    it(`${lang}: states the dues fee only in the answer for when there is one`, () => {
      const fee = mod.QUESTIONS.find((q) => q.id === 'platform-fee');
      expect(tokens(fee.aFee)).toContain('{{DUES_FEE}}');
      expect(tokens(fee.a)).not.toContain('{{DUES_FEE}}');
      expect(fee.needsPricing).toBe(true);
    });

    it(`${lang}: links only to help articles that exist`, () => {
      const slugs = helpEn.ARTICLES.map((a) => a.slug);
      const dead = mod.QUESTIONS.map((q) => q.link?.to).filter(Boolean)
        .filter((to) => to.startsWith('/help/') && !slugs.includes(to.slice('/help/'.length)));
      expect(dead).toEqual([]);
    });

    it(`${lang}: search ignores accents and case`, () => {
      const hit = mod.searchQuestions(lang === 'es' ? 'PARCELA' : 'PLOT');
      expect(hit.map((q) => q.id)).toContain('get-a-plot');
      if (lang === 'es') {
        expect(mod.searchQuestions('que es yardharvest').map((q) => q.id)).toContain('what-is-yardharvest');
      }
      expect(mod.searchQuestions('   ')).toEqual(mod.QUESTIONS);
    });
  }

  it('never calls a garden a jardín', () => {
    const text = JSON.stringify(es.QUESTIONS) + es.FAQ_INTRO + es.FAQ_DESCRIPTION;
    expect(text).not.toMatch(/jard[ií]n/i);
  });
});
