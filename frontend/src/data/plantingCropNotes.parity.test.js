// The Spanish crop notes must describe the notes the database actually holds.
//
// The English is seeded by init_planting_guide() in app/api/planting_api.py.
// cropProse() only swaps in Spanish when the stored English matches the text
// an entry was translated from, so a reworded seed would quietly fall back to
// English on every Spanish page. This fails first, naming the crop.
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

import { CROP_NOTES_ES, cropProse } from './plantingCropNotes.es';

const SEED = path.resolve(__dirname, '../../../app/api/planting_api.py');

function seededGuides() {
  const src = fs.readFileSync(SEED, 'utf8');
  const start = src.indexOf('guides = [');
  const block = src.slice(start, src.indexOf('\n    ]', start));
  return block.split(/\n {8}\{/).slice(1).map((entry) => {
    const field = (name) => {
      const m = entry.match(new RegExp(`'${name}': '([^'\\n]*)'`));
      return m ? m[1] : null;
    };
    return {
      category: field('category'),
      notes: field('notes'),
      companion_plants: field('companion_plants'),
      avoid_near: field('avoid_near'),
    };
  });
}

const seed = seededGuides();

describe('Spanish crop notes', () => {
  it('found the seed', () => {
    // A parser that finds nothing would make every check below pass.
    expect(seed.length).toBeGreaterThanOrEqual(17);
  });

  it('covers every seeded crop, and nothing else', () => {
    expect(Object.keys(CROP_NOTES_ES).sort()).toEqual(seed.map((g) => g.category).sort());
  });

  it.each(seed.map((g) => [g.category, g]))('%s was translated from the current English', (_c, g) => {
    const { from } = CROP_NOTES_ES[g.category];
    expect(from).toEqual({
      notes: g.notes, companion_plants: g.companion_plants, avoid_near: g.avoid_near,
    });
  });

  it('never leaves a Spanish field identical to its English', () => {
    const same = Object.entries(CROP_NOTES_ES).flatMap(([crop, e]) =>
      ['notes', 'companion_plants', 'avoid_near']
        .filter((f) => e[f] === e.from[f]).map((f) => `${crop}.${f}`));
    expect(same).toEqual([]);
  });

  it('keeps the numbers the English states', () => {
    // Dates, day counts and temperatures are facts, not words.
    const nums = (s) => (s.match(/\d+/g) || []).filter((n) => !['16', '18', '21'].includes(n));
    for (const [crop, e] of Object.entries(CROP_NOTES_ES)) {
      expect([crop, nums(e.notes)]).toEqual([crop, e.from.notes.match(/\d+/g) || []]);
    }
  });
});

describe('cropProse', () => {
  const guide = seed.find((g) => g.category === 'Tomatoes');

  it('swaps in Spanish on a Spanish page', () => {
    expect(cropProse('es', guide, 'notes')).toBe(CROP_NOTES_ES.Tomatoes.notes);
  });

  it('leaves English pages alone', () => {
    expect(cropProse('en', guide, 'notes')).toBe(guide.notes);
  });

  it('shows the stored words when they are not what was translated', () => {
    const edited = { ...guide, notes: 'Our own note about tomatoes.' };
    expect(cropProse('es', edited, 'notes')).toBe('Our own note about tomatoes.');
  });

  it('passes through crops and fields it does not know', () => {
    expect(cropProse('es', { category: 'Okra', notes: 'x' }, 'notes')).toBe('x');
    expect(cropProse('es', guide, 'category')).toBe('Tomatoes');
    expect(cropProse('es', null, 'notes')).toBeUndefined();
  });
});
