import { Link } from 'react-router-dom';

/**
 * SMS consent disclosure shown wherever a user opts into text messages
 * (profile edit, notification preferences, signup). The wording is shared so
 * the consent language is identical everywhere — required for TCPA / carrier
 * A2P 10DLC compliance (rates, frequency, and STOP/HELP must be disclosed at
 * the point of opt-in).
 */
export default function SmsConsentNote({ className = '' }) {
  return (
    <small
      className={`text-muted d-block ${className}`}
      style={{ fontSize: '0.78rem', lineHeight: 1.45 }}
    >
      By providing your phone number and opting in, you agree to receive account,
      order, and garden notification text messages from YardHarvest at the number
      provided. Consent is not a condition of any purchase. Message frequency
      varies. Message &amp; data rates may apply. Reply STOP to opt out, HELP for
      help. See our <Link to="/privacy">Privacy Policy</Link> and{' '}
      <Link to="/terms">Terms of Service</Link>.
    </small>
  );
}
