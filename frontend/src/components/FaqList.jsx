import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { publicAPI } from '../api';
import * as faqEn from '../data/faq';
import * as faqEs from '../data/faq.es';

/** The FAQ content in the page language; anything but Spanish reads English. */
export function useFaqContent() {
  const { i18n } = useTranslation();
  return (i18n.language || '').startsWith('es') ? faqEs : faqEn;
}

/** Live Garden Pro prices and the platform's dues fee, or null until loaded
 *  (and for good if the request fails). Never a hardcoded number. */
export function useFaqPricing() {
  const [pricing, setPricing] = useState(null);
  useEffect(() => {
    let live = true;
    publicAPI.pricing()
      .then((r) => {
        const pro = r.data?.garden_pro;
        if (!live || !pro) return;
        setPricing({
          monthly: pro.monthly,
          yearly: pro.yearly,
          trialDays: pro.trial_days,
          duesFeePercent: Number(r.data?.garden?.dues_fee_percent) || 0,
        });
      })
      .catch(() => { /* answers that need a price fall back or stay hidden */ });
    return () => { live = false; };
  }, []);
  return pricing;
}

const dollars = (n) => (Number.isInteger(n) ? `$${n}` : `$${Number(n).toFixed(2)}`);

/** The answer to show for `item`, or null when it cannot be stated honestly
 *  (it needs pricing that has not loaded). Picks the fee form when a platform
 *  fee is set, so "we take nothing" is never shown beside a fee. */
export function answerFor(item, pricing) {
  if (!pricing) {
    if (item.needsPricing) return null;
    return item.aNoPrice || item.a;
  }
  const text = pricing.duesFeePercent > 0 && item.aFee ? item.aFee : item.a;
  return text
    .replace(/\{\{PRO_MONTHLY\}\}/g, dollars(pricing.monthly))
    .replace(/\{\{PRO_YEARLY\}\}/g, dollars(pricing.yearly))
    .replace(/\{\{TRIAL_DAYS\}\}/g, String(pricing.trialDays))
    .replace(/\{\{DUES_FEE\}\}/g, String(+Number(pricing.duesFeePercent).toFixed(2)));
}

/** Questions with an answer that can be shown right now, each paired with it. */
export function answerable(items, pricing) {
  return items
    .map((item) => ({ item, answer: answerFor(item, pricing) }))
    .filter((row) => row.answer);
}

/**
 * An accordion of questions. Each is a real button (keyboard and screen
 * reader friendly) controlling its own region, and carries an id so a link to
 * /faq#<id> can open it.
 */
export default function FaqList({ rows, openId, onToggle, headingLevel = 3 }) {
  const Heading = `h${headingLevel}`;
  return (
    <div className="d-flex flex-column gap-2">
      {rows.map(({ item, answer }) => {
        const open = openId === item.id;
        return (
          <div key={item.id} id={item.id} className="card shadow-sm"
               style={{ borderRadius: 8, scrollMarginTop: 90 }}>
            <Heading className="h6 mb-0">
              <button
                type="button"
                className="btn w-100 d-flex justify-content-between align-items-center text-start p-3 fw-bold"
                aria-expanded={open}
                aria-controls={`${item.id}-answer`}
                id={`${item.id}-question`}
                onClick={() => onToggle(open ? null : item.id)}
              >
                <span>{item.q}</span>
                <i className={`bi bi-chevron-${open ? 'up' : 'down'} text-muted ms-3`} aria-hidden="true" />
              </button>
            </Heading>
            <div
              id={`${item.id}-answer`}
              role="region"
              aria-labelledby={`${item.id}-question`}
              hidden={!open}
              className="px-3 pb-3"
            >
              <p className="text-muted mb-0">{answer}</p>
              {item.link && (
                <Link to={item.link.to} className="d-inline-block mt-2 small fw-semibold">
                  {item.link.label} <i className="bi bi-arrow-right" aria-hidden="true" />
                </Link>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
