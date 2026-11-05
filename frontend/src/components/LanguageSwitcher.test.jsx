// The picker is how a reader who landed on the wrong language gets to theirs,
// so it must show only when Spanish is offered, name each language in itself,
// and link to the same page in the other language.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import LanguageSwitcher from './LanguageSwitcher';

let languages = ['en', 'es'];
vi.mock('../SiteConfigContext', () => ({
  useSiteConfig: () => ({ languages }),
}));
// The page under test is English: currentLanguage comes from the URL.
vi.mock('../i18n', () => ({
  currentLanguage: 'en',
  buildLanguageHref: (code) => (code === 'en' ? '/faq' : `/${code}/faq`),
}));

describe('LanguageSwitcher', () => {
  it('renders nothing while only English is offered', () => {
    languages = ['en'];
    const { container } = render(<LanguageSwitcher />);
    expect(container).toBeEmptyDOMElement();
    languages = ['en', 'es'];
  });

  it('lists every language, marking the current one', () => {
    render(<LanguageSwitcher />);
    expect(screen.getByText('English')).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('link', { name: 'Español' })).toHaveAttribute('href', '/es/faq');
  });

  it('compact: offers only the other language, named in itself', () => {
    render(<LanguageSwitcher compact />);
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute('href', '/es/faq');
    expect(links[0]).toHaveAttribute('hreflang', 'es');
    // The visible text shortens on narrower screens; the name never does.
    expect(links[0]).toHaveAccessibleName('Español');
    expect(links[0]).toHaveAttribute('title', 'Español');
  });
});
