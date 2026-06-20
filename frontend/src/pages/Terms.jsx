// NOTE FOR YARDHARVEST: This is a tailored starting template, not legal advice.
// Have a qualified attorney review and adapt it (operating entity, governing
// law/venue, fee terms, refund and arbitration choices) before relying on it.
import Seo from '../components/Seo';

const UPDATED = 'June 19, 2026';

export default function Terms() {
  return (
    <div className="container py-4" style={{ maxWidth: '800px' }}>
      <Seo
        title="Terms of Service"
        path="/terms"
        description="The terms that govern your use of the YardHarvest community-garden platform."
      />
      <h1 className="fw-bold mb-1">Terms of Service</h1>
      <p className="text-muted">Last updated: {UPDATED}</p>

      <p>
        These Terms of Service (“Terms”) govern your access to and use of the
        YardHarvest platform and services (the “Service”), operated from Omaha,
        Nebraska, United States (“YardHarvest,” “we,” “us”). By creating an
        account or using the Service, you agree to these Terms and to our{' '}
        <a href="/privacy">Privacy Policy</a>. If you do not agree, do not use
        the Service.
      </p>

      <h2 className="h5 fw-bold mt-4">1. Eligibility &amp; accounts</h2>
      <p>
        You must be at least 18 years old (or the age of majority where you
        live) and able to form a binding contract. You are responsible for the
        accuracy of your account information, for keeping your credentials
        secure, and for all activity under your account.
      </p>

      <h2 className="h5 fw-bold mt-4">2. The Service</h2>
      <p>
        YardHarvest provides tools for organizing and managing community
        gardens—including plots, members, events, volunteers, resources,
        announcements, community walls, and the collection of dues and fees—and,
        where enabled, an optional produce marketplace. We may add, change, or
        discontinue features at any time.
      </p>

      <h2 className="h5 fw-bold mt-4">3. Garden organizers &amp; payments</h2>
      <ul>
        <li>
          Payments (e.g., dues and plot fees) are processed through{' '}
          <strong>Stripe</strong> using Stripe Connect. The garden organizer is
          the merchant of record for payments they collect and is responsible
          for the underlying goods or services, for refunds and chargebacks, and
          for any applicable taxes.
        </li>
        <li>
          By enabling payouts, organizers agree to the{' '}
          <strong>Stripe Connected Account Agreement</strong> and Stripe Services
          Agreement, and must provide accurate information to Stripe.
        </li>
        <li>
          YardHarvest is a technology platform that facilitates these payments.
          Except as the provider of the Garden Pro subscription, we are not a
          party to transactions between organizers and their members and make no
          warranties about them.
        </li>
        <li>
          <strong>Fees:</strong> we may charge a platform fee on payments
          processed through the Service and/or a subscription fee for paid
          tiers. Stripe’s processing fees also apply. Fees are disclosed before
          you incur them.
        </li>
      </ul>

      <h2 className="h5 fw-bold mt-4">4. Garden Pro subscriptions</h2>
      <p>
        Paid “Garden Pro” features are billed on a recurring basis through
        Stripe. Free trials, if offered, convert to paid unless cancelled before
        the trial ends. Subscriptions renew automatically until cancelled; you
        may cancel at any time and will retain access through the end of the
        current billing period. Except where required by law, fees are
        non‑refundable. We may change pricing with prior notice.
      </p>

      <h2 className="h5 fw-bold mt-4">5. Marketplace (where enabled)</h2>
      <p>
        Where a produce marketplace is available, sellers are solely responsible
        for their listings, pricing, fulfillment, food safety, and compliance
        with applicable laws. YardHarvest provides the venue and is not the
        seller or a party to buyer–seller transactions.
      </p>

      <h2 className="h5 fw-bold mt-4">6. Your content</h2>
      <p>
        You retain ownership of content you submit (comments, photos, listings,
        garden information). You grant YardHarvest a non‑exclusive, worldwide,
        royalty‑free license to host, store, display, and distribute that
        content as needed to operate the Service. You are responsible for your
        content and represent that you have the rights to share it. We may
        screen, moderate, or remove content (including via automated
        moderation) at our discretion.
      </p>

      <h2 className="h5 fw-bold mt-4">7. Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>break the law or infringe others’ rights;</li>
        <li>post harassing, hateful, deceptive, or harmful content, or spam;</li>
        <li>misuse payments, commit fraud, or circumvent fees;</li>
        <li>attempt to disrupt, reverse‑engineer, scrape, or gain unauthorized access to the Service;</li>
        <li>impersonate others or misrepresent your affiliation.</li>
      </ul>

      <h2 className="h5 fw-bold mt-4">8. Automated &amp; AI features</h2>
      <p>
        Some features use automated systems and AI (e.g., content moderation and
        draft generation). These are provided “as is,” may produce errors, and
        do not replace human judgment; administrators are responsible for
        reviewing automated output before relying on it.
      </p>

      <h2 className="h5 fw-bold mt-4">9. Intellectual property</h2>
      <p>
        The Service, including its software, design, and trademarks, is owned by
        YardHarvest and its licensors. We grant you a limited, revocable,
        non‑transferable license to use the Service in accordance with these
        Terms.
      </p>

      <h2 className="h5 fw-bold mt-4">10. Third‑party services</h2>
      <p>
        The Service relies on third parties (including Stripe, email/SMS,
        image, AI, and hosting providers). Your use of those services may be
        governed by their own terms, and we are not responsible for them.
      </p>

      <h2 className="h5 fw-bold mt-4">11. Disclaimers</h2>
      <p>
        THE SERVICE IS PROVIDED “AS IS” AND “AS AVAILABLE,” WITHOUT WARRANTIES OF
        ANY KIND, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A
        PARTICULAR PURPOSE, AND NON‑INFRINGEMENT. We do not warrant that the
        Service will be uninterrupted, secure, or error‑free.
      </p>

      <h2 className="h5 fw-bold mt-4">12. Limitation of liability</h2>
      <p>
        TO THE MAXIMUM EXTENT PERMITTED BY LAW, YARDHARVEST WILL NOT BE LIABLE
        FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE
        DAMAGES, OR FOR LOST PROFITS OR DATA. OUR TOTAL LIABILITY FOR ANY CLAIM
        RELATING TO THE SERVICE WILL NOT EXCEED THE GREATER OF THE AMOUNTS YOU
        PAID US IN THE 12 MONTHS BEFORE THE CLAIM OR USD $100.
      </p>

      <h2 className="h5 fw-bold mt-4">13. Indemnification</h2>
      <p>
        You agree to indemnify and hold YardHarvest harmless from claims,
        damages, and expenses arising out of your content, your use of the
        Service, or your violation of these Terms or applicable law.
      </p>

      <h2 className="h5 fw-bold mt-4">14. Termination</h2>
      <p>
        You may stop using the Service at any time. We may suspend or terminate
        access if you violate these Terms or to protect the Service or others.
        Provisions that by their nature should survive termination will survive.
      </p>

      <h2 className="h5 fw-bold mt-4">15. Governing law &amp; disputes</h2>
      <p>
        These Terms are governed by the laws of the State of Nebraska, USA,
        without regard to conflict‑of‑laws rules. The parties will first try to
        resolve disputes informally; unresolved disputes are subject to the
        courts located in Nebraska, unless otherwise required by applicable law.
      </p>

      <h2 className="h5 fw-bold mt-4">16. Changes to these Terms</h2>
      <p>
        We may update these Terms from time to time. We will revise the “Last
        updated” date and, for material changes, provide additional notice.
        Continued use after changes take effect constitutes acceptance.
      </p>

      <h2 className="h5 fw-bold mt-4">17. Contact</h2>
      <p>
        Questions about these Terms? Email{' '}
        <a href="mailto:james@yardharvest.app">james@yardharvest.app</a>.
      </p>
    </div>
  );
}
