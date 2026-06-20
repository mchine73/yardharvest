import SwiftUI

/// Form sheet for adding a new tool to the garden's shared inventory.
/// On success, hands the freshly-created `GardenResource` (which includes
/// the just-minted `qrCodeURL`) back to `AdminToolsView`, which
/// auto-opens the QR label sheet for immediate printing.
struct AdminAddToolView: View {
    let garden: Garden
    let onCreate: (GardenResource) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name: String = ""
    @State private var resourceType: ResourceKind = .tool
    @State private var description: String = ""
    @State private var quantityText: String = "1"
    @State private var condition: Condition = .good
    @State private var isSaving = false
    @State private var errorMessage: String?

    enum ResourceKind: String, CaseIterable, Identifiable {
        case tool, equipment, supply, seed
        var id: String { rawValue }
        var label: String { rawValue.capitalized }
    }

    enum Condition: String, CaseIterable, Identifiable {
        case new, good, fair, needs_repair
        var id: String { rawValue }
        var label: String {
            switch self {
            case .new: return "New"
            case .good: return "Good"
            case .fair: return "Fair"
            case .needs_repair: return "Needs repair"
            }
        }
    }

    private var canSave: Bool {
        !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isSaving
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: YH.Space.md) {
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            label("Name")
                            TextField("e.g. Cordless drill", text: $name)
                                .textInputAutocapitalization(.words)
                                .padding(12)
                                .background(YH.surface)
                                .overlay(RoundedRectangle(cornerRadius: YH.Radius.md)
                                            .strokeBorder(YH.border))
                                .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
                        }
                    }
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            label("Type")
                            Picker("Type", selection: $resourceType) {
                                ForEach(ResourceKind.allCases) { kind in
                                    Text(kind.label).tag(kind)
                                }
                            }
                            .pickerStyle(.segmented)
                            label("Condition")
                            Picker("Condition", selection: $condition) {
                                ForEach(Condition.allCases) { c in
                                    Text(c.label).tag(c)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(YH.ink)
                            label("Quantity")
                            TextField("1", text: $quantityText)
                                .keyboardType(.numberPad)
                                .padding(12)
                                .background(YH.surface)
                                .overlay(RoundedRectangle(cornerRadius: YH.Radius.md)
                                            .strokeBorder(YH.border))
                                .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
                        }
                    }
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            label("Description (optional)")
                            TextField("Brief notes that show up on the tool's detail page",
                                      text: $description, axis: .vertical)
                                .lineLimit(1...4)
                                .padding(12)
                                .background(YH.surface)
                                .overlay(RoundedRectangle(cornerRadius: YH.Radius.md)
                                            .strokeBorder(YH.border))
                                .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
                    }
                    YHButton(title: "Add Tool & Print QR",
                             systemImage: "plus.circle.fill",
                             style: .lime, isLoading: isSaving) {
                        Task { await save() }
                    }
                    .disabled(!canSave)
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("New Tool")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    private func label(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
    }

    private func save() async {
        guard canSave else { return }
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        let quantity = max(1, Int(quantityText) ?? 1)
        do {
            let created = try await APIClient.shared.createResource(
                gardenID: garden.id,
                name: name.trimmingCharacters(in: .whitespacesAndNewlines),
                resourceType: resourceType.rawValue,
                description: description.trimmingCharacters(in: .whitespacesAndNewlines),
                quantity: quantity,
                condition: condition.rawValue)
            Haptics.success()
            onCreate(created)
            dismiss()
        } catch let e as APIError {
            errorMessage = e.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }
}
