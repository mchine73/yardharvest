// Catalog hygiene.
//
// A missing Spanish key is invisible at runtime: fallbackLng renders the
// English string, which is the right behaviour for a reader mid-rollout and
// exactly the wrong behaviour for us — nothing on screen says "this was never
// translated". These tests are what notices instead.
import { describe, it, expect } from 'vitest';
import en from './locales/en/common.json';
import es from './locales/es/common.json';

/** Every leaf key, flattened to dotted paths. */
function keys(obj, prefix = '') {
  return Object.entries(obj).flatMap(([k, v]) => {
    const path = prefix ? `${prefix}.${k}` : k;
    return v && typeof v === 'object' ? keys(v, path) : [path];
  });
}

function get(obj, path) {
  return path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj);
}

const enKeys = keys(en);
const esKeys = keys(es);

describe('the two catalogs describe the same product', () => {
  it('has a Spanish string for every English one', () => {
    expect(enKeys.filter((k) => !esKeys.includes(k))).toEqual([]);
  });

  it('has no Spanish key without an English source', () => {
    // A stray Spanish key is a rename that only got applied on one side.
    expect(esKeys.filter((k) => !enKeys.includes(k))).toEqual([]);
  });
});

describe('every string is actually translated', () => {
  it('has no empty Spanish values', () => {
    expect(esKeys.filter((k) => !String(get(es, k) ?? '').trim())).toEqual([]);
  });

  it('has no Spanish value left identical to the English', () => {
    // Allowed where the word genuinely does not change; listed explicitly so
    // adding to it is a decision rather than an oversight.
    const SAME_IN_BOTH = [
      'garden.destPersonal',   // "Personal" is the same word in Spanish
    ];
    const untranslated = enKeys.filter(
      (k) => get(en, k) === get(es, k) && !SAME_IN_BOTH.includes(k));
    expect(untranslated).toEqual([]);
  });
});

describe('interpolation and markup survive translation', () => {
  it('keeps the same {{placeholders}} on both sides', () => {
    const vars = (s) => (String(s).match(/\{\{\s*\w+\s*\}\}/g) || [])
      .map((v) => v.replace(/\s/g, '')).sort();
    const broken = enKeys.filter(
      (k) => JSON.stringify(vars(get(en, k))) !== JSON.stringify(vars(get(es, k))));
    // A dropped or renamed placeholder renders the literal {{email}} to the
    // reader - the single most visible way a translation goes wrong.
    expect(broken).toEqual([]);
  });

  it('keeps the same <1>markup</1> indices on both sides', () => {
    const tags = (s) => (String(s).match(/<\/?\d+>/g) || []).sort();
    const broken = enKeys.filter(
      (k) => JSON.stringify(tags(get(en, k))) !== JSON.stringify(tags(get(es, k))));
    // <Trans> maps these onto real elements; a mismatch drops a link.
    expect(broken).toEqual([]);
  });
});
