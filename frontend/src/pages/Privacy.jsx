// NOTE FOR YARDHARVEST: This is a tailored starting template, not legal advice.
// Have a qualified attorney review and adapt it (entity name, governing law,
// CCPA/GDPR obligations, retention periods) before relying on it.
import Seo from '../components/Seo';

const UPDATED = 'June 19, 2026';

export default function Privacy() {
  return (
    <div className="container py-4" style={{ maxWidth: '800px' }}>
      <Seo
        title="Privacy Policy"
        path="/privacy"
        description="How YardHarvest collects, uses, shares, and protects your personal information."
      />
      <h1 className="fw-bold mb-1">Privacy Policy</h1>
      <p className="text-muted">Last updated: {UPDATED}</p>

      <p>
        This Privacy Policy explains how YardHarvest (“YardHarvest,” “we,” “us”)
        collects, uses, shares, and protects information when you use our
        community‑garden management platform, websites, and related services
        (the “Service”). By using the Service you agree to this Policy.
      </p>

      <h2 className="h5 fw-bold mt-4">1. Information we collect</h2>
      <ul>
        <li><strong>Account information:</strong> name, username, display name, email address, a hashed password, and optional profile photo.</li>
        <li><strong>Garden &amp; contact details:</strong> garden name, address, city/state/ZIP, contact email, and—if you use the planting calendar—your approximate location.</li>
        <li><strong>Garden activity:</strong> plots, memberships and waitlists, events and RSVPs, volunteer hours, resources, dues records, photos, and comments you post.</li>
        <li><strong>Payment information:</strong> payments are processed by Stripe. We do <em>not</em> collect or store full card numbers. Garden organizers who receive payouts provide identity and bank details directly to Stripe.</li>
        <li><strong>Communications:</strong> announcements, messages, and support requests you send or receive through the Service.</li>
        <li><strong>Usage &amp; device data:</strong> log data, IP address, browser/device type, and first‑party analytics collected via cookies (see Section 5).</li>
      </ul>

      <h2 className="h5 fw-bold mt-4">2. How we use information</h2>
      <ul>
        <li>Operate, maintain, and improve the Service.</li>
        <li>Process dues and payments and route payouts to garden organizers.</li>
        <li>Send transactional messages (e.g., account, receipts, password resets) and—where you have opted in—garden announcements and reminders by email or SMS.</li>
        <li>Screen community content for safety using automated moderation (see Section 4).</li>
        <li>Provide support, prevent fraud and abuse, and maintain security.</li>
        <li>Comply with legal obligations and enforce our Terms of Service.</li>
      </ul>

      <h2 className="h5 fw-bold mt-4">3. How we share information</h2>
      <p>We do not sell your personal information. We share it only as needed to run the Service:</p>
      <ul>
        <li><strong>Facebook/Meta:</strong> only if a garden or our CRM connects a Facebook Page, in which case posts and messages flow through Meta’s platform under Meta’s terms.</li>
        <li><strong>Other members and the public:</strong> your display name, profile photo, and any photos or comments you post may be visible on public garden pages and to other members.</li>
        <li><strong>Legal &amp; safety:</strong> to comply with law, enforce our Terms, or protect rights, safety, and property.</li>
        <li><strong>Business transfers:</strong> in connection with a merger, acquisition, or sale of assets, subject to this Policy.</li>
      </ul>

      <h2 className="h5 fw-bold mt-4">4. Automated moderation &amp; AI features</h2>
      <p>
        Comments posted to community walls are screened by an automated (AI)
        moderator before they appear, and some tools (e.g., draft announcements
        or outreach) use AI to generate text. These features process the
        relevant content to function, may make mistakes, and are subject to
        human review by garden administrators.
      </p>

      <h2 className="h5 fw-bold mt-4">5. Cookies &amp; analytics</h2>
      <p>
        We use first‑party cookies for essential functionality and basic,
        privacy‑respecting analytics. You can accept or decline non‑essential
        cookies via our consent banner and can change your choice at any time in
        your settings or browser.
      </p>

      <h2 className="h5 fw-bold mt-4">6. Payments &amp; financial data</h2>
      <p>
        Stripe is our payment processor and handles cardholder data in
        accordance with PCI‑DSS; we never receive your full card number. Garden
        organizers who accept payments agree to Stripe’s Connected Account
        Agreement and Services Agreement, and are responsible for the
        transactions they initiate.
      </p>

      <h2 className="h5 fw-bold mt-4">7. Data retention</h2>
      <p>
        We retain personal information for as long as your account is active and
        as needed to provide the Service, and thereafter as required for legal,
        accounting, tax, or dispute‑resolution purposes. You may request
        deletion as described below.
      </p>

      <h2 className="h5 fw-bold mt-4">8. Your rights &amp; choices</h2>
      <ul>
        <li><strong>Access &amp; update:</strong> view and edit your profile and garden details in the app.</li>
        <li><strong>Email opt‑out:</strong> unsubscribe from non‑transactional emails at any time; transactional messages may still be sent.</li>
        <li><strong>SMS:</strong> reply STOP to opt out of text messages.</li>
        <li><strong>Deletion &amp; other rights:</strong> depending on where you live, you may have rights to access, correct, delete, or port your data, or to opt out of certain processing. Contact us to exercise them.</li>
      </ul>

      <h2 className="h5 fw-bold mt-4">9. Security</h2>
      <p>
        We protect information using encryption in transit, hashed passwords,
        access controls, and reputable infrastructure providers; card data is
        handled by Stripe. No method of transmission or storage is 100% secure,
        and we cannot guarantee absolute security.
      </p>

      <h2 className="h5 fw-bold mt-4">10. Children’s privacy</h2>
      <p>
        The Service is not directed to children under 13, and we do not
        knowingly collect personal information from them. If you believe a child
        has provided us information, please contact us and we will delete it.
      </p>

      <h2 className="h5 fw-bold mt-4">11. International users</h2>
      <p>
        The Service is operated from the United States. If you access it from
        elsewhere, you understand your information is processed in the U.S.
      </p>

      <h2 className="h5 fw-bold mt-4">12. Changes to this Policy</h2>
      <p>
        We may update this Policy from time to time. We will revise the “Last
        updated” date above and, for material changes, provide additional notice.
      </p>

      <h2 className="h5 fw-bold mt-4">13. Contact us</h2>
      <p>
        Questions about this Policy or your data? Email{' '}
        <a href="mailto:james@yardharvest.app">james@yardharvest.app</a>.
      </p>
    </div>
  );
}
