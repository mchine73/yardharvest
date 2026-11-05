// /faq in both languages: live prices filled in, the platform-fee answer
// matching whatever fee is actually set, nothing priced said when pricing is
// unavailable, and a Spanish reader meeting no English.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import Faq from './Faq';
import i18n from '../i18n';
import * as en from '../data/faq';
import * as es from '../data/faq.es';

let pricing;
vi.mock('../api', () => ({
  publicAPI: { pricing: vi.fn(() => pricing) },
}));
let seoProps;
vi.mock('../components/Seo', () => ({
  default: (props) => { seoProps = props; return <div data-testid="seo" data-title={props.title} />; },
}));

const live = (fee = 0) => Promise.resolve({
  data: { garden_pro: { monthly: 12, yearly: 60, trial_days: 14 }, garden: { dues_fee_percent: fee } },
});

const draw = (path = '/faq') => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes><Route path="/faq" element={<Faq />} /></Routes>
  </MemoryRouter>,
);

const answerTo = (id) => document.getElementById(`${id}-answer`);
const open = (id) => fireEvent.click(document.getElementById(`${id}-question`));

beforeEach(() => {
  pricing = live(0);
  seoProps = null;
  window.history.replaceState = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(async () => { await i18n.changeLanguage('en'); });

describe('FAQ page', () => {
  it('renders every question in English, with live prices', async () => {
    await i18n.changeLanguage('en');
    draw();
    await waitFor(() => expect(document.getElementById('platform-fee')).toBeInTheDocument());
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(en.FAQ_TITLE);
    for (const q of en.QUESTIONS) expect(screen.getByText(q.q)).toBeInTheDocument();
    open('garden-pro');
    expect(answerTo('garden-pro')).toHaveTextContent('$12 a month or $60 a year');
    expect(answerTo('garden-pro')).toHaveTextContent('free trial of 14 days');
    expect(answerTo('garden-pro').textContent).not.toMatch(/\{\{/);
  });

  it('says there is no cut only when the fee is zero', async () => {
    await i18n.changeLanguage('en');
    draw();
    await waitFor(() => expect(document.getElementById('platform-fee')).toBeInTheDocument());
    open('platform-fee');
    expect(answerTo('platform-fee')).toHaveTextContent('YardHarvest takes nothing');
  });

  it('states the fee when one is set', async () => {
    await i18n.changeLanguage('en');
    pricing = live(2.5);
    draw();
    await waitFor(() => expect(document.getElementById('platform-fee')).toBeInTheDocument());
    open('platform-fee');
    expect(answerTo('platform-fee')).toHaveTextContent('YardHarvest keeps 2.5% of each payment');
    expect(answerTo('platform-fee')).not.toHaveTextContent('takes nothing');
  });

  it('without pricing, leaves the fee out and words the price answer without numbers', async () => {
    await i18n.changeLanguage('en');
    pricing = Promise.reject(new Error('down'));
    draw();
    await new Promise((r) => setTimeout(r, 0));
    expect(document.getElementById('platform-fee')).toBeNull();
    open('garden-pro');
    expect(answerTo('garden-pro').textContent).not.toMatch(/\$|\{\{/);
    expect(answerTo('garden-pro')).toHaveTextContent('the pricing page has the current prices');
  });

  it('opens a question and reflects it in the address', async () => {
    await i18n.changeLanguage('en');
    draw();
    const button = document.getElementById('is-it-free-question');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(answerTo('is-it-free')).not.toBeVisible();
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(answerTo('is-it-free')).toBeVisible();
    expect(window.history.replaceState).toHaveBeenLastCalledWith(null, '', '#is-it-free');
  });

  it('opens the question a link points at', async () => {
    await i18n.changeLanguage('en');
    draw('/faq#where-does-the-money-go');
    await waitFor(() => expect(answerTo('where-does-the-money-go')).toBeVisible());
  });

  it('filters by search and says so when nothing matches', async () => {
    await i18n.changeLanguage('en');
    draw();
    const box = screen.getByRole('searchbox');
    fireEvent.change(box, { target: { value: 'waitlist plot' } });
    expect(screen.getByText('How do I find a garden and get a plot?')).toBeInTheDocument();
    expect(screen.queryByText('Do you sell my data?')).toBeNull();
    fireEvent.change(box, { target: { value: 'zzzz' } });
    expect(screen.getByText(/No question matches that/)).toBeInTheDocument();
  });

  it('gives search engines the questions it shows, prices filled', async () => {
    await i18n.changeLanguage('en');
    draw();
    await waitFor(() => expect(seoProps.jsonLd.mainEntity.length).toBe(en.QUESTIONS.length));
    expect(seoProps.path).toBe('/faq');
    expect(seoProps.jsonLd['@type']).toBe('FAQPage');
    expect(JSON.stringify(seoProps.jsonLd)).not.toMatch(/\{\{/);
  });

  it('renders Spanish questions, answers and chrome, with no English left', async () => {
    await i18n.changeLanguage('es');
    draw();
    await waitFor(() => expect(document.getElementById('platform-fee')).toBeInTheDocument());
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(es.FAQ_TITLE);
    for (const q of es.QUESTIONS) open(q.id);
    const text = document.body.textContent;
    for (const q of en.QUESTIONS) {
      expect(text).not.toContain(q.q);
      expect(text).not.toContain(q.a.slice(0, 40));
    }
    const enFaq = i18n.getResourceBundle('en', 'common').faq;
    for (const v of Object.values(enFaq).filter((s) => !s.includes('{{'))) {
      expect(text).not.toContain(v);
    }
    expect(text).not.toMatch(/\bfaq\.[a-zA-Z]/);
    expect(answerTo('garden-pro')).toHaveTextContent('$12 al mes o $60 al año');
    expect(answerTo('platform-fee')).toHaveTextContent('YardHarvest no se queda con nada');
    open('collect-online');   // one answer is open at a time
    expect(within(answerTo('collect-online')).getByRole('link')).toHaveTextContent('Configura las transferencias con Stripe');
    expect(seoProps.jsonLd.mainEntity[0].name).toBe(es.QUESTIONS[0].q);
  });
});
