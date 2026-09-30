import { Link } from 'react-router-dom';
import { Trans } from 'react-i18next';

/**
 * SMS consent disclosure shown wherever a user opts into text messages
 * (profile edit, notification preferences, signup). The wording is shared so
 * the consent language is identical everywhere — required for TCPA / carrier
 * A2P 10DLC compliance (rates, frequency, and STOP/HELP must be disclosed at
 * the point of opt-in).
 *
 * Translated, because consent obtained in a language the reader does not speak
 * is not informed consent — which is the entire thing this disclosure exists
 * to establish. Two rules for whoever edits the Spanish:
 *
 *   * STOP and HELP stay in English. They are literal keywords the carrier
 *     matches on, not words. Translating them would tell a Spanish speaker to
 *     text something that does not unsubscribe them, which is worse than not
 *     translating the sentence at all.
 *   * The English remains the version the 10DLC campaign was registered
 *     against. The Spanish has to say the same things — sender, purpose,
 *     "consent is not a condition of purchase", frequency varies, rates may
 *     apply, how to stop — not a looser paraphrase of them.
 */
export default function SmsConsentNote({ className = '' }) {
  return (
    <small
      className={`text-muted d-block ${className}`}
      style={{ fontSize: '0.78rem', lineHeight: 1.45 }}
    >
      <Trans i18nKey="smsConsent.note">
        By providing your phone number and opting in, you agree to receive account,
        order, and garden notification text messages from YardHarvest at the number
        provided. Consent is not a condition of any purchase. Message frequency
        varies. Message &amp; data rates may apply. Reply STOP to opt out, HELP for
        help. See our <Link to="/privacy">Privacy Policy</Link> and <Link to="/terms">Terms of Service</Link>.
      </Trans>
    </small>
  );
}
