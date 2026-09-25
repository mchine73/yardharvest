// The URL is the only thing that decides the language on the client, so these
// cover the three functions that read and write it. Getting basenameFor wrong
// is what would break all 74 routes at once.
import { describe, it, expect } from 'vitest';
import { languageFromPath, basenameFor, buildLanguageHref } from './index';

describe('languageFromPath', () => {
  it('reads the leading segment', () => {
    expect(languageFromPath('/es/gardens')).toBe('es');
    expect(languageFromPath('/es')).toBe('es');
    expect(languageFromPath('/es/')).toBe('es');
  });

  it('needs a segment boundary, not a prefix match', () => {
    // '/estuary' and '/english-garden' start with a language code but are not
    // in one. A substring check here would silently reroute real pages.
    expect(languageFromPath('/estuary')).toBeNull();
    expect(languageFromPath('/english-garden')).toBeNull();
    expect(languageFromPath('/gardens')).toBeNull();
  });

  it('survives nonsense', () => {
    expect(languageFromPath('')).toBeNull();
    expect(languageFromPath(undefined)).toBeNull();
  });
});

describe('basenameFor', () => {
  it('is empty for English so existing URLs are untouched', () => {
    // English keeps today's URLs: the site is indexed, and moving it to /en/
    // would break every existing link for no gain.
    expect(basenameFor('/gardens')).toBe('');
    expect(basenameFor('/')).toBe('');
  });

  it('is /es inside a Spanish session', () => {
    expect(basenameFor('/es/gardens')).toBe('/es');
    expect(basenameFor('/es')).toBe('/es');
  });
});

describe('buildLanguageHref', () => {
  const at = (pathname, search = '', hash = '') => ({ pathname, search, hash });

  it('switches into Spanish on the same page', () => {
    expect(buildLanguageHref('es', at('/pricing'))).toBe('/es/pricing');
  });

  it('switches back out', () => {
    expect(buildLanguageHref('en', at('/es/pricing'))).toBe('/pricing');
  });

  it('handles the root in both directions', () => {
    expect(buildLanguageHref('es', at('/'))).toBe('/es');
    expect(buildLanguageHref('en', at('/es'))).toBe('/');
    expect(buildLanguageHref('en', at('/es/'))).toBe('/');
  });

  it('keeps query and hash', () => {
    // Switching language mid-search must not throw the search away.
    expect(buildLanguageHref('es', at('/search', '?q=tomato', '#results')))
      .toBe('/es/search?q=tomato#results');
  });

  it('is idempotent', () => {
    expect(buildLanguageHref('es', at('/es/pricing'))).toBe('/es/pricing');
    expect(buildLanguageHref('en', at('/pricing'))).toBe('/pricing');
  });

  it('does not mistake a path that merely starts with a code', () => {
    expect(buildLanguageHref('es', at('/estuary'))).toBe('/es/estuary');
  });
});
