import Foundation
import Observation

/// Owns the user's list of gardens + currently-selected one. Persists the
/// selection so the user lands on the same garden between launches.
@MainActor
@Observable
final class GardenStore {
    private(set) var gardens: MyGardensPayload?
    private(set) var isLoading = false
    private(set) var lastError: String?

    var selectedGardenID: Int? {
        didSet { UserDefaults.standard.set(selectedGardenID, forKey: Self.selectedKey) }
    }

    private static let selectedKey = "yh.selectedGardenID"

    init() {
        let saved = UserDefaults.standard.integer(forKey: Self.selectedKey)
        self.selectedGardenID = saved == 0 ? nil : saved
    }

    func bootstrapIfNeeded() async {
        guard gardens == nil, !isLoading else { return }
        await reload()
    }

    func reload() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let payload = try await APIClient.shared.myGardens()
            self.gardens = payload
            if selectedGardenID == nil {
                selectedGardenID = payload.organized.first?.id ?? payload.all.first?.id
            } else if let id = selectedGardenID,
                      !payload.all.contains(where: { $0.id == id }) {
                selectedGardenID = payload.organized.first?.id ?? payload.all.first?.id
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    var selectedGarden: Garden? {
        guard let id = selectedGardenID else { return nil }
        return gardens?.all.first { $0.id == id }
    }

    /// True when the signed-in user holds ANY admin capability in the active
    /// garden — the organizer, or an assigned role (co-organizer, treasurer,
    /// volunteer lead). Which specific screens they get is a per-capability
    /// question; ask `can(_:)`.
    var hasAdminAccess: Bool {
        guard let id = selectedGardenID, let gardens else { return false }
        if gardens.organized.contains(where: { $0.id == id }) { return true }
        return !(selectedGarden?.userCapabilities ?? []).isEmpty
    }

    /// Capability check for the active garden — names from
    /// garden_permissions.py: "money", "content", "resources", "roles",
    /// "people", "events", "shifts", "reports", "garden", "billing".
    func can(_ capability: String) -> Bool {
        selectedGarden?.can(capability) ?? false
    }
}
