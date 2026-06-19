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
}
