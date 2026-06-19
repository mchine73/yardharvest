import SwiftUI

/// Sheet shown after scanning or tapping a tool: adapts to its state and
/// offers the right action (check out / return / show info).
struct ResourceActionSheet: View {
    let lookup: ResourceLookup
    let onDismiss: (Bool) -> Void

    @State private var resource: GardenResource
    @State private var duration: Int = 3
    @State private var conditionAtReturn: String = "good"
    @State private var isWorking = false
    @State private var errorMessage: String?
    @State private var didChange = false
    @Environment(\.dismiss) private var dismiss

    init(lookup: ResourceLookup, onDismiss: @escaping (Bool) -> Void) {
        self.lookup = lookup
        self.onDismiss = onDismiss
        _resource = State(initialValue: lookup.resource)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: YH.Space.md) {
                    header
                    if resource.outOfService {
                        outOfServiceCard
                    } else if resource.isAvailable {
                        checkoutCard
                    } else if resource.isCheckedOut {
                        returnCard
                    }
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.yhSubheadline)
                            .foregroundStyle(YH.danger)
                    }
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle(resource.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Close") {
                        onDismiss(didChange)
                        dismiss()
                    }
                }
            }
        }
        .interactiveDismissDisabled(isWorking)
    }

    private var header: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 8) {
                Text(lookup.gardenName.uppercased())
                    .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                HStack {
                    Text(resource.name).font(.yhTitle2).foregroundStyle(YH.ink)
                    Spacer()
                    statusPill
                }
                if let type = resource.resourceType {
                    Text(type.capitalized).font(.yhSubheadline).foregroundStyle(YH.muted)
                }
                if let condition = resource.condition {
                    Label("Condition: \(condition.replacingOccurrences(of: "_", with: " ").capitalized)",
                          systemImage: "checkmark.seal")
                    .font(.yhCaption).foregroundStyle(YH.muted)
                }
            }
        }
    }

    private var outOfServiceCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 6) {
                Label("Out of service", systemImage: "wrench.adjustable")
                    .font(.yhHeadline).foregroundStyle(YH.warning)
                if let note = resource.serviceNote, !note.isEmpty {
                    Text(note).font(.yhSubheadline).foregroundStyle(YH.muted)
                } else {
                    Text("This tool isn't available right now.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                }
            }
        }
    }

    private var checkoutCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("Check Out").font(.yhHeadline).foregroundStyle(YH.ink)
                Picker("Duration", selection: $duration) {
                    Text("1 day").tag(1)
                    Text("3 days").tag(3)
                    Text("7 days").tag(7)
                }
                .pickerStyle(.segmented)
                YHButton(title: "Check Out", systemImage: "arrow.down.circle",
                         style: .lime, isLoading: isWorking) {
                    Task { await checkOut() }
                }
            }
        }
    }

    private var returnCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                if let due = resource.dueDate {
                    HStack {
                        Text("Due \(due.formatted(date: .abbreviated, time: .shortened))")
                            .font(.yhSubheadline).foregroundStyle(YH.muted)
                        Spacer()
                        if resource.isOverdue {
                            YHPill(text: "Overdue", tint: .white, background: YH.danger)
                        }
                    }
                }
                Text("Condition on return").font(.yhCaptionMed).foregroundStyle(YH.muted)
                Picker("Condition", selection: $conditionAtReturn) {
                    Text("Good").tag("good")
                    Text("Fair").tag("fair")
                    Text("Needs repair").tag("needs_repair")
                }
                .pickerStyle(.segmented)
                YHButton(title: "Return", systemImage: "arrow.up.circle",
                         style: .dark, isLoading: isWorking) {
                    Task { await returnItem() }
                }
            }
        }
    }

    @ViewBuilder
    private var statusPill: some View {
        switch resource.status {
        case "available": YHPill(text: "Available", tint: YH.ink, background: YH.lime)
        case "checked_out": YHPill(text: "Out", tint: YH.muted, background: YH.surface)
        case "overdue": YHPill(text: "Overdue", tint: .white, background: YH.danger)
        case "out_of_service": YHPill(text: "Service", tint: .white, background: YH.warning)
        default: YHPill(text: resource.status.capitalized, tint: YH.muted, background: YH.surface)
        }
    }

    private func checkOut() async {
        isWorking = true; errorMessage = nil
        defer { isWorking = false }
        do {
            resource = try await APIClient.shared.checkoutResource(
                gardenID: lookup.gardenId, resourceID: resource.id, durationDays: duration)
            didChange = true
            Haptics.success()
        } catch let e as APIError { errorMessage = e.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }

    private func returnItem() async {
        isWorking = true; errorMessage = nil
        defer { isWorking = false }
        do {
            resource = try await APIClient.shared.returnResource(
                gardenID: lookup.gardenId, resourceID: resource.id,
                condition: conditionAtReturn)
            didChange = true
            Haptics.success()
        } catch let e as APIError { errorMessage = e.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }
}
