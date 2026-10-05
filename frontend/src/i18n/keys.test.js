// Every t() key in the app must exist in the catalog.
//
// This is the gap the other i18n tests leave. catalogs.test.js proves English
// and Spanish agree with each other; it cannot know whether a key the code
// asks for exists at all. A typo renders the KEY to the reader — a literal
// "organizer.billingTitle" on the page — and `fallbackLng` cannot save it,
// because there is nothing to fall back to.
//
// It also catches the reverse of the bulk-conversion mistake: pointing a
// replacement at a key that was never added to the catalog.
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import en from './locales/en/common.json';

const SRC = path.resolve(__dirname, '..');

function leaves(obj, prefix = '') {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    return v && typeof v === 'object' ? leaves(v, key) : [key];
  });
}

function sourceFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      return entry.name === 'i18n' ? [] : sourceFiles(full);
    }
    if (!/\.jsx?$/.test(entry.name) || /\.test\.jsx?$/.test(entry.name)) return [];
    return [full];
  });
}

const known = new Set(leaves(en));

// i18next stores a plural as key_one / key_other, so the base key the code
// calls is never itself a leaf. Treat it as present when either form exists —
// otherwise every correctly-pluralised string reads as a missing key.
const PLURAL_SUFFIXES = ['_one', '_other', '_zero', '_two', '_few', '_many'];
const resolves = (key) =>
  known.has(key) || PLURAL_SUFFIXES.some((suffix) => known.has(key + suffix));

// t('some.key') and <Trans i18nKey="some.key">. Deliberately only literal
// keys — a computed key (t(`garden.model${x}`)) cannot be checked statically,
// and those all pass a fallback as the second argument.
const T_CALL = /\bt\(\s*'([a-zA-Z][\w.]*)'/g;
const TRANS = /i18nKey="([\w.]+)"/g;

describe('t() keys resolve', () => {
  const offenders = [];
  for (const file of sourceFiles(SRC)) {
    const src = fs.readFileSync(file, 'utf8');
    const used = new Set();
    for (const re of [T_CALL, TRANS]) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(src)) !== null) used.add(m[1]);
    }
    const bad = [...used].filter((k) => !resolves(k));
    if (bad.length) {
      offenders.push(`${path.relative(SRC, file)}: ${bad.join(', ')}`);
    }
  }

  it('has a catalog entry for every literal key the app asks for', () => {
    // A missing entry renders the key itself to the reader.
    expect(offenders).toEqual([]);
  });
});

// A file that calls useTranslation() or renders <Trans> without importing
// from react-i18next throws at RUNTIME — "useTranslation is not defined" —
// and the build passes clean, because a missing import is not a compile
// error in JS. A bulk conversion that inserts the hook but misses the import
// therefore ships a page that dies on load. This is the cheap static guard.
describe('i18n imports', () => {
  const offenders = [];
  for (const file of sourceFiles(SRC)) {
    const src = fs.readFileSync(file, 'utf8');
    const uses = /useTranslation\(/.test(src) || /<Trans[\s>]/.test(src);
    if (uses && !src.includes('react-i18next')) {
      offenders.push(path.relative(SRC, file));
    }
  }

  it('imports react-i18next wherever it is used', () => {
    expect(offenders).toEqual([]);
  });
});
