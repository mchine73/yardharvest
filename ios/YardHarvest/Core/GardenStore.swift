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

    /// True when the signed-in user organizes the active garden.
    var hasAdminAccess: Bool {
        guard let id = selectedGardenID, let gardens else { return false }
        return gardens.organized.contains { $0.id == id }
    }
}
