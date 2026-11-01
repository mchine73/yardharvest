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

// A module-scope array cannot call t(), so its entries hold a KEY and the
// render site translates it. Rename the property and forget one reader and
// nothing complains: `{tab.label}` on an object that only has `labelKey` is
// undefined, React renders undefined as nothing, the build is clean and the
// tests pass. The garden admin sidebar shipped to production that way — all
// fourteen nav items became bare icons and the four section headings
// vanished — and no existing guard could see it, because the bug is the
// ABSENCE of a t() call rather than a wrong one.
// Deliberately a named list rather than a clever inference. The first attempt
// flagged any file that defined `labelKey:` anywhere and read `.label`
// anywhere — which fires on GardenDetail, where a component-scope `tabs`
// array holds a real translated `label` and an unrelated module-scope legend
// map holds `labelKey`. Both are correct. A guard with false positives is one
// people switch off, so this one names the arrays it actually knows about.
describe('module-scope label keys', () => {
  const KEYED_ARRAYS = [
    {
      file: 'pages/gardens/GardenAdminDashboard.jsx',
      array: 'SIDEBAR_TABS',
      keys: ['labelKey', 'sectionKey'],
      // What a missed render site looks like in this file.
      forbidden: ['tab.label}', 'tab.label ', 'tab.section}', 'tab.section '],
    },
    {
      file: 'components/GardenLayoutEditor.jsx',
      array: 'FEATURE_TYPES',
      keys: ['labelKey'],
      // f.label here is the organizer's own text for a placed feature, which
      // is legitimate; reading it where the TYPE's name belongs is not.
      forbidden: ['toolBtn(f.key, f.label'],
    },
  ];

  for (const spec of KEYED_ARRAYS) {
    const src = fs.readFileSync(path.join(SRC, spec.file), 'utf8');

    it(`${spec.array} still holds keys, not text`, () => {
      // If the array stopped using keys the forbidden-read check below would
      // pass vacuously, so assert the premise too.
      for (const key of spec.keys) {
        expect(src.includes(key + ':')).toBe(true);
      }
    });

    it(`${spec.array} has no render site reading the pre-rename property`, () => {
      expect(spec.forbidden.filter((f) => src.includes(f))).toEqual([]);
    });
  }
});

// Importing react-i18next is not the same as calling the hook. The extractor
// rewrote App.jsx's footer to t('app.about'), added the import, and could not
// find the component to put `const { t }` in — so the file imported the
// library, called t(), and would have thrown on every page. The build passed:
// an undefined identifier is a runtime error, not a compile one.
//
// A file that calls t('key') must either call useTranslation() or take t as a
// parameter (module-scope helpers in GardenAdminDashboard do the latter).
// Checked per COMPONENT, not per file. App.jsx defines three; the extractor
// put the hook in one of them, so a file-level check saw useTranslation and
// passed while AppContent — the footer, on every page — still had no t.
// That is the same shape as the sidebar bug: the file was fine, the render
// site was not.
describe('t() has something to resolve it', () => {
  const offenders = [];
  for (const file of sourceFiles(SRC)) {
    const src = fs.readFileSync(file, 'utf8');
    if (!/(?<![\w.])t\('/.test(src)) continue;
    // Split on top-level function declarations; the slice that follows each
    // one is that component's body (near enough for this check).
    const starts = [...src.matchAll(/^(?:export default )?function (\w+)\s*\(/gm)];
    const blocks = starts.length
      ? starts.map((m, i) => ({
        name: m[1],
        body: src.slice(m.index, i + 1 < starts.length ? starts[i + 1].index : src.length),
      }))
      : [{ name: '(module)', body: src }];

    for (const b of blocks) {
      if (!/(?<![\w.])t\('/.test(b.body)) continue;
      const hasHook = /useTranslation\(/.test(b.body);
      // Module-scope helpers legitimately take t as a parameter.
      const takesT = /\(\s*[\w$]+\s*,\s*t\s*\)|\(\s*t\s*\)/.test(b.body);
      if (!hasHook && !takesT) {
        offenders.push(`${path.relative(SRC, file)}: ${b.name}`);
      }
    }
  }

  it('never calls t() with no t in scope', () => {
    expect(offenders).toEqual([]);
  });
});
