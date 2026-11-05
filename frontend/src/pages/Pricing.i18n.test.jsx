// /pricing is advertised to Google as Spanish. Its headline used to be a
// translated fragment followed by a hardcoded English "pricing".
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Pricing from './Pricing';
import i18n from '../i18n';

window.matchMedia = window.matchMedia || (() => ({ matches: true }));

globalThis.__mkt = true;
vi.mock('../SiteConfigContext', () => ({
  useSiteConfig: () => ({ marketplaceEnabled: globalThis.__mkt, languages: ['en', 'es'] }),
}));
vi.mock('../AuthContext', () => ({ useAuth: () => ({ user: null }) }));
vi.mock('../api', () => ({
  publicAPI: {
    pricing: vi.fn().mockResolvedValue({
      data: {
        garden_pro: { enabled: true, monthly: 12, yearly: 60, trial_days: 14 },
        marketplace: {
          smart_pricing_enabled: true, price_floor_pct: 0.8, price_ceiling_pct: 1.2,
          commission_enabled: true, commission_rate: 0.1,
          delivery_fees_enabled: true, delivery_fee_flat: 5,
          free_delivery_enabled: true, free_delivery_threshold: 30, doordash_enabled: true,
        },
      },
    }),
  },
}));
vi.mock('../components/Seo', () => ({
  default: ({ description }) => <span data-testid="seo" data-content={description} />,
}));

const draw = () => render(<MemoryRouter><Pricing /></MemoryRouter>);
const bundle = (lang) => i18n.getResourceBundle(lang, 'common').pricing;
const plain = (s) => s.replace(/<[^>]+>/g, '');
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const appears = (text, needle) => new RegExp(`(^|[^\\p{L}])${esc(needle)}($|[^\\p{L}])`, 'u').test(text);

afterEach(async () => { globalThis.__mkt = true; await i18n.changeLanguage('en'); });

describe.each([['marketplace on', true], ['garden mode', false]])('pricing page, %s', (_label, mkt) => {
  it('renders the headline as one sentence with the highlight inside it', async () => {
    globalThis.__mkt = mkt;
    await i18n.changeLanguage('es');
    const { findByRole } = draw();
    const h1 = await findByRole('heading', { level: 1 });
    expect(h1.textContent).toBe('Precios simples y transparentes');
    expect(h1.querySelector('.yh-highlight').textContent).toBe('Precios');
  });

  it('leaves no English pricing string on the Spanish page, FAQ answers included', async () => {
    globalThis.__mkt = mkt;
    await i18n.changeLanguage('es');
    const { container, findByRole } = draw();
    await findByRole('heading', { level: 1 });
    // Answers render only when opened; open each in turn and collect the text.
    let text = container.textContent;
    container.querySelectorAll('.card[style*="cursor"]').forEach((card) => {
      fireEvent.click(card);
      text += container.textContent;
    });
    const en = bundle('en');
    const es = bundle('es');
    const survivors = Object.keys(en).filter(
      (k) => en[k] !== es[k] && plain(en[k]).length > 3 && appears(text, plain(en[k])));
    expect(survivors).toEqual([]);
    expect(text).not.toMatch(/\bpricing\.[a-zA-Z]/);
    expect(text).not.toMatch(/Learn more|Talk to Us|Get Started|per transaction|flat delivery|\/mo\b|\/yr\b/);
  });
});

describe('pricing in English', () => {
  it('keeps the English headline, values and the exact description', async () => {
    await i18n.changeLanguage('en');
    const { findByRole, getByTestId, container } = draw();
    const h1 = await findByRole('heading', { level: 1 });
    expect(h1.textContent).toBe('Simple, transparent pricing');
    expect(container.textContent).toContain('10% per transaction');
    expect(container.textContent).toContain('$5.00 flat delivery fee');
    expect(getByTestId('seo').getAttribute('data-content')).toBe(
      'Simple, transparent pricing for community gardens. Start free, upgrade to Garden Pro for messaging, finance, photos and more.');
  });
});
