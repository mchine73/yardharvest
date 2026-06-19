import AppIntents
import Foundation

/// "Log Harvest" App Intent — surfaces YardHarvest in Siri, Shortcuts, and
/// the iOS Action Button. Lets a member quickly log a harvest with their
/// voice or a tap from a custom shortcut.
///
/// Requires the user to already be signed in to the app (tokens in Keychain).
struct LogHarvestIntent: AppIntent {
    static let title: LocalizedStringResource = "Log Harvest"
    static let description = IntentDescription(
        "Log how much you harvested at your community garden today."
    )
    static let openAppWhenRun: Bool = false

    @Parameter(title: "Crop", description: "What you harvested (e.g. Tomatoes).")
    var category: String

    @Parameter(title: "Pounds", description: "How many pounds you picked.")
    var quantityLbs: Double

    @Parameter(title: "Destination", description: "Where the harvest went.",
               default: .personal)
    var destination: HarvestDestinationIntentEnum

    func perform() async throws -> some IntentResult & ProvidesDialog {
        // Find the user's currently-selected garden from the app's
        // persisted preference.
        let savedGardenID = UserDefaults.standard.integer(forKey: "yh.selectedGardenID")
        guard savedGardenID != 0 else {
            return .result(dialog: "Open the YardHarvest app first to pick which garden to log to.")
        }

        do {
            _ = try await APIClient.shared.logHarvest(
                gardenID: savedGardenID,
                category: category,
                variety: nil,
                quantityLbs: quantityLbs,
                harvestDate: Date(),
                destination: HarvestDestination(rawValue: destination.rawValue) ?? .personal,
                notes: nil
            )
            return .result(dialog: "Logged \(Int(quantityLbs)) lb of \(category). Nice work!")
        } catch {
            return .result(dialog: "Couldn't log that harvest — please open YardHarvest and try again.")
        }
    }
}

/// String-backed enum that App Intents can present as a picker. Mirrors
/// `HarvestDestination`.
enum HarvestDestinationIntentEnum: String, AppEnum {
    case personal, shared, foodBank = "food_bank", marketplace

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Destination"
    static let caseDisplayRepresentations: [HarvestDestinationIntentEnum: DisplayRepresentation] = [
        .personal: "Personal use",
        .shared: "Shared with members",
        .foodBank: "Food bank",
        .marketplace: "Sold at market",
    ]
}

/// Group the YardHarvest intents under one app shortcut surface so they show
/// up in the Shortcuts app's "Suggested" panel and on the Action Button.
struct YardHarvestShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: LogHarvestIntent(),
            phrases: [
                "Log a harvest in \(.applicationName)",
                "\(.applicationName), log harvest",
            ],
            shortTitle: "Log Harvest",
            systemImageName: "basket.fill"
        )
    }
}
