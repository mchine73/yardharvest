import Foundation

/// Paginated response from `GET /api/gardens` — the public browse endpoint.
struct BrowseGardensPage: Codable, Equatable {
    let gardens: [Garden]
    let total: Int
    let pages: Int
    let page: Int
    let hasNext: Bool
    let hasPrev: Bool

    enum CodingKeys: String, CodingKey {
        case gardens, total, pages, page
        case hasNext = "has_next"
        case hasPrev = "has_prev"
    }
}

/// `GET /api/gardens/{id}` — single garden with `include_stats=True` plus
/// member-context fields the public endpoint adds for the signed-in user.
struct GardenDetail: Codable, Equatable {
    let id: Int
    let publicId: String?
    let name: String
    let description: String?
    let address: String?
    let city: String?
    let state: String?
    let zipCode: String?
    let photoUrl: String?
    let totalPlots: Int?
    let plotFeeAnnual: Double?
    let operatingModel: String?
    let rules: String?
    let contactEmail: String?
    let organizerId: Int?
    let organizerName: String?
    let latitude: Double?
    let longitude: Double?

    // Stats (when include_stats=true)
    let availablePlots: Int?
    let assignedPlots: Int?
    let memberCount: Int?
    let waitlistCount: Int?
    let reservedPlots: Int?
    let upcomingEvents: Int?

    // Per-user context
    let userIsOrganizer: Bool
    let userHasPlot: Bool
    let userOnWaitlist: Bool
    let userHasReservation: Bool

    let upcomingEventsList: [GardenEvent]?

    enum CodingKeys: String, CodingKey {
        case id
        case publicId = "public_id"
        case name, description, address, city, state
        case zipCode = "zip_code"
        case photoUrl = "photo_url"
        case totalPlots = "total_plots"
        case plotFeeAnnual = "plot_fee_annual"
        case operatingModel = "operating_model"
        case rules
        case contactEmail = "contact_email"
        case organizerId = "organizer_id"
        case organizerName = "organizer_name"
        case latitude, longitude
        case availablePlots = "available_plots"
        case assignedPlots = "assigned_plots"
        case memberCount = "member_count"
        case waitlistCount = "waitlist_count"
        case reservedPlots = "reserved_plots"
        case upcomingEvents = "upcoming_events"
        case userIsOrganizer = "user_is_organizer"
        case userHasPlot = "user_has_plot"
        case userOnWaitlist = "user_on_waitlist"
        case userHasReservation = "user_has_reservation"
        case upcomingEventsList = "upcoming_events_list"
    }

    /// Adapter to a plain `Garden` for the banner card.
    var asGarden: Garden {
        Garden(
            id: id, publicId: publicId, name: name, slug: nil,
            description: description, address: address, city: city, state: state,
            zipCode: zipCode, photoUrl: photoUrl,
            totalPlots: totalPlots, plotFeeAnnual: plotFeeAnnual,
            operatingModel: operatingModel, isActive: true,
            maxCheckoutsPerMember: nil, latitude: latitude, longitude: longitude,
            weatherAlertsEnabled: nil, gridRows: nil, gridCols: nil,
            organizerId: organizerId, organizerName: organizerName,
            userGardenRole: nil, userCapabilities: nil
        )
    }
}
