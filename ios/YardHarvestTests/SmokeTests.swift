import XCTest
@testable import YardHarvest

final class SmokeTests: XCTestCase {

    func testBaseURLPointsAtRender() {
        XCTAssertEqual(AppEnvironment.defaultBaseURL.host, "www.yardharvest.app")
    }

    func testParsesNaiveDatetime() {
        // The exact shape the Flask backend emits for `.isoformat()` on a
        // timezone-naive datetime (no offset).
        XCTAssertNotNil(APIClient.parseDate("2026-07-04T21:00:00"))
    }

    func testParsesDateOnly() {
        XCTAssertNotNil(APIClient.parseDate("2026-07-04"))
    }

    func testParsesISO8601WithOffset() {
        XCTAssertNotNil(APIClient.parseDate("2026-07-04T21:00:00+00:00"))
        XCTAssertNotNil(APIClient.parseDate("2026-07-04T21:00:00.123456+00:00"))
    }

    func testGardenPayloadDecodes() throws {
        let json = #"""
        {
          "organized": [],
          "plot_holder": [],
          "waitlisted": []
        }
        """#.data(using: .utf8)!
        let decoder = JSONDecoder()
        let payload = try decoder.decode(MyGardensPayload.self, from: json)
        XCTAssertEqual(payload.all.count, 0)
    }

    func testMediaURLHandlesRelativePath() {
        let url = AppEnvironment.mediaURL("/media/abc.jpg")
        XCTAssertEqual(url?.absoluteString, "https://www.yardharvest.app/media/abc.jpg")
    }

    func testMediaURLPassesAbsolute() {
        let url = AppEnvironment.mediaURL("https://res.cloudinary.com/foo/bar.jpg")
        XCTAssertEqual(url?.absoluteString, "https://res.cloudinary.com/foo/bar.jpg")
    }

    // MARK: - Manager money feed

    /// A decoder wired the same way `APIClient` wires its own, so these
    /// fixtures fail for the same reasons the live app would.
    private func apiDecoder() -> JSONDecoder {
        let dec = JSONDecoder()
        dec.dateDecodingStrategy = .custom { decoder in
            let value = try decoder.singleValueContainer().decode(String.self)
            guard let date = APIClient.parseDate(value) else {
                throw DecodingError.dataCorrupted(
                    .init(codingPath: [], debugDescription: "bad date \(value)"))
            }
            return date
        }
        return dec
    }

    /// The finance feed is the one screen whose contents come entirely from
    /// Stripe webhooks, so a silent key mismatch here would show an empty
    /// "no card activity yet" screen to a manager who has been paid.
    func testMoneyFeedDecodes() throws {
        let json = #"""
        {
          "events": [
            {"id": 3, "kind": "payout", "source": "stripe", "status": "paid",
             "scope": "account", "label": "$48.50 deposited to your bank",
             "amount": 48.5, "fee": 0.0, "stripe_fee": null, "net": 48.5,
             "currency": "usd", "description": null, "counterparty": null,
             "dues_id": null, "stripe_object_id": "po_1",
             "occurred_at": "2026-08-22T14:02:11"},
            {"id": 2, "kind": "payment", "source": "in_person_sale",
             "status": "succeeded", "scope": "garden",
             "label": "In-person sale $12.00", "amount": 12.0, "fee": 0.36,
             "stripe_fee": 0.30, "net": 11.34, "currency": "usd",
             "description": "Tomato starts", "counterparty": null,
             "dues_id": null, "stripe_object_id": "pi_2",
             "occurred_at": "2026-08-21T16:40:00"}
          ],
          "window_days": 90,
          "count": 2,
          "totals": {"collected": 12.0, "fees": 0.36, "stripe_fees": 0.30,
                     "net": 11.34, "refunded": 0.0, "disputed": 0.0,
                     "kept": 11.34, "payment_count": 1, "failed_count": 0,
                     "unknown_fee_count": 0, "fees_complete": true,
                     "by_source": {"dues_online": 0.0, "dues_in_person": 0.0,
                                   "in_person_sale": 12.0}},
          "stripe_status": {"state": "ok", "message": "Payments and payouts are both enabled.",
                            "ok": true, "charges_enabled": true, "payouts_enabled": true,
                            "disabled_reason": null, "requirements_due": [],
                            "account_id": "acct_1", "synced_at": "2026-08-22T14:00:00"}
        }
        """#.data(using: .utf8)!

        let feed = try apiDecoder().decode(GardenMoneyFeed.self, from: json)
        XCTAssertEqual(feed.events.count, 2)
        // Both cuts come out: 12.00 less 0.36 platform less 0.30 Stripe.
        XCTAssertEqual(feed.totals.kept, 11.34)
        XCTAssertEqual(feed.totals.stripeFees, 0.30)
        XCTAssertTrue(feed.totals.feesComplete)
        XCTAssertTrue(feed.stripeStatus.ok)
        // The payout is account-level and must not read as garden income,
        // and carries no Stripe fee of its own.
        XCTAssertEqual(feed.events.first?.scope, "account")
        XCTAssertNil(feed.events.first?.stripeFee)
        XCTAssertFalse(feed.events.first?.isOutgoing ?? true)
        XCTAssertNotNil(feed.events.first?.occurredAt)
    }

    /// A NULL stripe_fee is "not looked up yet", not zero — the screens report
    /// the kept figure as a ceiling while any payment is in that state.
    func testAnUnknownStripeFeeDecodesAsNil() throws {
        let json = #"""
        {"id": 9, "kind": "payment", "source": "dues_online", "status": "succeeded",
         "scope": "garden", "label": "Dues paid online $50.00", "amount": 50.0,
         "fee": 0.0, "stripe_fee": null, "net": 50.0, "currency": "usd",
         "description": null, "counterparty": "Rosa Lin", "dues_id": 4,
         "stripe_object_id": "pi_9", "occurred_at": "2026-08-20T10:00:00"}
        """#.data(using: .utf8)!
        let event = try apiDecoder().decode(GardenMoneyEvent.self, from: json)
        XCTAssertNil(event.stripeFee)
        XCTAssertEqual(event.net, 50.0)
    }

    func testStripeStatusDecodesWithoutASyncTimestamp() throws {
        // NULL synced_at is the "no Connect webhook has ever landed" case,
        // which the UI reports rather than treating as healthy.
        let json = #"""
        {"state": "action_needed", "message": "Stripe needs a few more details.",
         "ok": false, "charges_enabled": false, "payouts_enabled": false,
         "disabled_reason": null, "requirements_due": ["individual.verification.document"],
         "account_id": "acct_1", "synced_at": null, "dashboard_url": null,
         "billing_path": "/gardens/grd_x/billing", "stripe_configured": true}
        """#.data(using: .utf8)!

        let status = try apiDecoder().decode(GardenStripeStatus.self, from: json)
        XCTAssertNil(status.syncedAt)
        XCTAssertTrue(status.needsAttention)
        XCTAssertEqual(StripeStatusBanner.humanize("individual.verification.document"),
                       "Individual verification document")
    }
}
