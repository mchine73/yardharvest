import SwiftUI

/// One plot: details, occupant, and every manager action the web admin
/// dashboard offers — confirm/decline a pending reservation, assign an
/// available plot to a member, release an assigned one, toggle maintenance,
/// and edit the details (name, size, soil, sun, renewal date, notes).
struct PlotDetailView: View {
    let garden: Garden
    let onChange: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var plot: Plot
    @State private var isWorking = false
    @State private var errorMessage: String?
    @State private var infoMessage: String?
    @State private var confirmingRelease = false
    @State private var confirmingDecline = false

    /// One presentation state for both sheets — stacked `.sheet(isPresented:)`
    /// modifiers cause per-frame navigation churn (see LoginView).
    enum ActiveSheet: Identifiable {
        case assign, edit
        var id: Self { self }
    }
    @State private var activeSheet: ActiveSheet?

    /// Seeded through State(initialValue:) — mutating state in onAppear
    /// drives updates mid-render (see ForgotPasswordView).
    init(garden: Garden, plot: Plot, onChange: @escaping () -> Void) {
        self.garden = garden
        self.onChange = onChange
        _plot = State(initialValue: plot)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                headerCard
                if plot.status == "reserved" { reservationCard }
                if plot.assignedToId != nil { occupantCard }
                detailsCard
                actions
                if let infoMessage {
                    Text(infoMessage).font(.yhSubheadline).foregroundStyle(YH.ink)
                }
                if let errorMessage {
                    Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
                }
            }
            .padding(YH.Space.md)
        }
        .background(YH.canvas)
        .navigationTitle(plot.displayLabel)
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $activeSheet) { sheet in
            switch sheet {
            case .assign:
                AssignMemberSheet(garden: garden) { member in
                    Task { await assign(to: member) }
                }
            case .edit:
                EditPlotSheet(plot: plot) { body in
                    Task { await saveEdits(body) }
                }
            }
        }
        .confirmationDialog("Release this plot?",
                            isPresented: $confirmingRelease,
                            titleVisibility: .visible) {
            Button("Release Plot", role: .destructive) { Task { await release() } }
        } message: {
            Text("\(plot.assignedToName ?? "The member") loses the plot and it becomes available. This doesn't notify them — tell them first.")
        }
        .confirmationDialog("Decline this reservation?",
                            isPresented: $confirmingDecline,
                            titleVisibility: .visible) {
            Button("Decline Reservation", role: .destructive) { Task { await decline() } }
        } message: {
            Text("\(plot.reservedByName ?? "The member")'s request is declined and the plot becomes available again.")
        }
    }

    // MARK: - Cards

    private var headerCard: some View {
        YHCard {
            HStack(spacing: 12) {
                Text("#\(plot.plotNumber)")
                    .font(.system(size: 20, weight: .bold))
                    .foregroundStyle(YH.ink)
                    .frame(width: 56, height: 56)
                    .background(plot.status == "assigned" ? YH.lime : YH.surface)
                    .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))
                VStack(alignment: .leading, spacing: 4) {
                    Text(plot.displayLabel)
                        .font(.yhTitle3)
                        .foregroundStyle(YH.ink)
                    PlotStatusPill(status: plot.status)
                }
                Spacer()
            }
        }
    }

    private var reservationCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("PENDING RESERVATION")
                    .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                HStack(spacing: 12) {
                    YHAvatar(name: plot.reservedByName ?? "?", size: 42)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(plot.reservedByName ?? "Member")
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        if let at = plot.reservedAt {
                            Text("Requested \(at.formatted(date: .abbreviated, time: .omitted))")
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                    Spacer()
                }
            }
        }
    }

    private var occupantCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("ASSIGNED TO")
                    .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                HStack(spacing: 12) {
                    YHAvatar(name: plot.assignedToName ?? "?", size: 42)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(plot.assignedToName ?? "Member")
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        if let since = plot.assignedDate {
                            Text("Since \(since.formatted(date: .abbreviated, time: .omitted))")
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                    Spacer()
                }
                if let lbs = plot.harvestTotalLbs, lbs > 0 {
                    Divider().overlay(YH.border)
                    HStack {
                        Label("\(String(format: "%.1f", lbs)) lb harvested",
                              systemImage: "basket")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                        Spacer()
                        Text("\(plot.harvestCount ?? 0) logs")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                }
            }
        }
    }

    private var detailsCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("DETAILS")
                    .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                detailRow("Size", plot.size)
                detailRow("Soil", soilLabel(plot.soilType))
                detailRow("Sun", sunLabel(plot.sunExposure))
                detailRow("Renews", plot.renewalDate?.formatted(date: .abbreviated, time: .omitted))
                if let notes = plot.locationNotes, !notes.isEmpty {
                    Divider().overlay(YH.border)
                    Text(notes).font(.yhSubheadline).foregroundStyle(YH.ink)
                }
            }
        }
    }

    @ViewBuilder
    private func detailRow(_ label: String, _ value: String?) -> some View {
        HStack {
            Text(label).font(.yhSubheadline).foregroundStyle(YH.muted)
            Spacer()
            Text(value?.isEmpty == false ? value! : "—")
                .font(.yhBodyMedium).foregroundStyle(YH.ink)
        }
    }

    // MARK: - Actions

    @ViewBuilder
    private var actions: some View {
        VStack(spacing: YH.Space.sm) {
            switch plot.status {
            case "reserved":
                YHButton(title: "Confirm Reservation", systemImage: "checkmark",
                         style: .lime, isLoading: isWorking) {
                    Task { await confirm() }
                }
                YHButton(title: "Decline", systemImage: "xmark", style: .ghost) {
                    confirmingDecline = true
                }
            case "available":
                YHButton(title: "Assign to Member", systemImage: "person.badge.plus",
                         style: .dark, isLoading: isWorking) {
                    activeSheet = .assign
                }
            case "assigned":
                YHButton(title: "Release Plot", systemImage: "xmark.circle",
                         style: .ghost, isLoading: isWorking) {
                    confirmingRelease = true
                }
            default:
                EmptyView()
            }

            YHButton(title: plot.status == "maintenance"
                        ? "End Maintenance" : "Mark Under Maintenance",
                     systemImage: "wrench.adjustable",
                     style: .ghost, isLoading: isWorking) {
                Task { await toggleMaintenance() }
            }

            YHButton(title: "Edit Details", systemImage: "pencil", style: .ghost) {
                activeSheet = .edit
            }
        }
    }

    // MARK: - Mutations

    private func run(_ label: String, _ work: () async throws -> Plot) async {
        guard !isWorking else { return }
        isWorking = true
        errorMessage = nil
        infoMessage = nil
        defer { isWorking = false }
        do {
            let updated = try await work()
            // Partial responses (edit) lack occupant fields — merge over the
            // existing plot rather than trusting every nil.
            plot = merged(updated, into: plot)
            infoMessage = label
            Haptics.success()
            onChange()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    private func confirm() async {
        await run("Reservation confirmed — the member has been notified.") {
            try await APIClient.shared.confirmReservation(gardenID: garden.id, plotID: plot.id)
        }
    }

    private func decline() async {
        await run("Reservation declined.") {
            try await APIClient.shared.declineReservation(gardenID: garden.id, plotID: plot.id)
        }
    }

    private func assign(to member: GardenMember) async {
        activeSheet = nil
        await run("\(plot.displayLabel) assigned to \(member.name).") {
            try await APIClient.shared.assignPlot(gardenID: garden.id, plotID: plot.id,
                                                  userID: member.userId)
        }
    }

    private func release() async {
        await run("Plot released — it's available again.") {
            try await APIClient.shared.releasePlot(gardenID: garden.id, plotID: plot.id)
        }
    }

    private func toggleMaintenance() async {
        guard !isWorking else { return }
        isWorking = true
        errorMessage = nil
        infoMessage = nil
        defer { isWorking = false }
        do {
            let resp = try await APIClient.shared.toggleMaintenance(gardenID: garden.id,
                                                                    plotID: plot.id)
            plot = plot.with(status: resp.status)
            infoMessage = resp.message
            Haptics.success()
            onChange()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    private func saveEdits(_ body: APIClient.EditPlotBody) async {
        activeSheet = nil
        await run("Plot updated.") {
            try await APIClient.shared.adminEditPlot(gardenID: garden.id, plotID: plot.id,
                                                     body: body)
        }
    }

    /// The edit endpoint returns a partial dict; keep fields the response
    /// doesn't carry rather than blanking them.
    private func merged(_ new: Plot, into old: Plot) -> Plot {
        Plot(id: new.id,
             gardenId: new.gardenId,
             plotNumber: new.plotNumber,
             size: new.size ?? old.size,
             locationNotes: new.locationNotes ?? old.locationNotes,
             status: new.status,
             assignedToId: new.assignedToId,
             assignedToName: new.assignedToName,
             assignedToEmail: new.assignedToEmail ?? old.assignedToEmail,
             assignedDate: new.assignedDate,
             renewalDate: new.renewalDate,
             reservedById: new.reservedById,
             reservedByName: new.reservedByName,
             reservedAt: new.reservedAt,
             harvestTotalLbs: new.harvestTotalLbs ?? old.harvestTotalLbs,
             harvestCount: new.harvestCount ?? old.harvestCount,
             gridRow: new.gridRow ?? old.gridRow,
             gridCol: new.gridCol ?? old.gridCol,
             customName: new.customName ?? old.customName,
             soilType: new.soilType ?? old.soilType,
             sunExposure: new.sunExposure ?? old.sunExposure)
    }

    // MARK: - Labels

    private func soilLabel(_ raw: String?) -> String? {
        guard let raw, !raw.isEmpty else { return nil }
        return raw.capitalized
    }

    private func sunLabel(_ raw: String?) -> String? {
        switch raw {
        case "full_sun":      return "Full Sun"
        case "partial_shade": return "Partial Shade"
        case "full_shade":    return "Full Shade"
        default:              return nil
        }
    }
}

private extension Plot {
    func with(status: String) -> Plot {
        Plot(id: id, gardenId: gardenId, plotNumber: plotNumber, size: size,
             locationNotes: locationNotes, status: status,
             assignedToId: assignedToId, assignedToName: assignedToName,
             assignedToEmail: assignedToEmail, assignedDate: assignedDate,
             renewalDate: renewalDate, reservedById: reservedById,
             reservedByName: reservedByName, reservedAt: reservedAt,
             harvestTotalLbs: harvestTotalLbs, harvestCount: harvestCount,
             gridRow: gridRow, gridCol: gridCol, customName: customName,
             soilType: soilType, sunExposure: sunExposure)
    }
}

// MARK: - Assign sheet

/// Member picker for assigning an available plot. Same candidate pool as the
/// web: the garden's current roster (organizer + plot holders).
private struct AssignMemberSheet: View {
    let garden: Garden
    let onPick: (GardenMember) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var members: [GardenMember] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            YHLoadable(isLoading: isLoading,
                       isEmpty: members.isEmpty,
                       errorMessage: errorMessage,
                       onRetry: { await load() }) {
                YHEmpty(systemImage: "person.2",
                        title: "No members yet",
                        message: "Members appear here once they join your garden.")
            } content: {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(members) { member in
                            Button {
                                Haptics.tap()
                                onPick(member)
                            } label: {
                                YHCard {
                                    HStack(spacing: 12) {
                                        YHAvatar(name: member.name, size: 42)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(member.name)
                                                .font(.yhBodyMedium).foregroundStyle(YH.ink)
                                            Text(member.isOrganizer
                                                 ? "Organizer"
                                                 : "Plot \(member.plotNumber ?? "—")")
                                                .font(.yhCaption).foregroundStyle(YH.muted)
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.system(size: 13, weight: .semibold))
                                            .foregroundStyle(YH.muted)
                                    }
                                }
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(YH.Space.md)
                }
            }
            .background(YH.canvas)
            .navigationTitle("Assign to Member")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }.foregroundStyle(YH.muted)
                }
            }
            .task { await load() }
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do { members = try await APIClient.shared.listGardenMembers(gardenID: garden.id) }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

// MARK: - Edit sheet

/// Field-for-field mirror of the web's inline plot editor.
private struct EditPlotSheet: View {
    let onSave: (APIClient.EditPlotBody) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var customName: String
    @State private var size: String
    @State private var soilType: String
    @State private var sunExposure: String
    @State private var hasRenewal: Bool
    @State private var renewalDate: Date
    @State private var locationNotes: String

    private static let soilOptions = ["", "clay", "loam", "sandy", "silt", "mixed"]
    private static let sunOptions = ["", "full_sun", "partial_shade", "full_shade"]

    init(plot: Plot, onSave: @escaping (APIClient.EditPlotBody) -> Void) {
        self.onSave = onSave
        _customName = State(initialValue: plot.customName ?? "")
        _size = State(initialValue: plot.size ?? "")
        _soilType = State(initialValue: plot.soilType ?? "")
        _sunExposure = State(initialValue: plot.sunExposure ?? "")
        _hasRenewal = State(initialValue: plot.renewalDate != nil)
        _renewalDate = State(initialValue: plot.renewalDate ?? Date())
        _locationNotes = State(initialValue: plot.locationNotes ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Name & size") {
                    TextField("Custom name (e.g. Sunny Corner)", text: $customName)
                    TextField("Size (e.g. 4x8 ft)", text: $size)
                }
                Section("Growing conditions") {
                    Picker("Soil type", selection: $soilType) {
                        ForEach(Self.soilOptions, id: \.self) { opt in
                            Text(opt.isEmpty ? "—" : opt.capitalized).tag(opt)
                        }
                    }
                    Picker("Sun exposure", selection: $sunExposure) {
                        ForEach(Self.sunOptions, id: \.self) { opt in
                            Text(sunLabel(opt)).tag(opt)
                        }
                    }
                }
                Section("Renewal") {
                    Toggle("Has renewal date", isOn: $hasRenewal.animation())
                    if hasRenewal {
                        DatePicker("Renews on", selection: $renewalDate, displayedComponents: .date)
                    }
                }
                Section("Location notes") {
                    TextField("e.g. NW corner, next to the shed",
                              text: $locationNotes, axis: .vertical)
                        .lineLimit(2...4)
                }
            }
            .navigationTitle("Edit Plot")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }.foregroundStyle(YH.muted)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Save") { save() }.fontWeight(.semibold)
                }
            }
        }
    }

    private func save() {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "UTC")
        onSave(APIClient.EditPlotBody(
            custom_name: customName.trimmingCharacters(in: .whitespaces),
            size: size.trimmingCharacters(in: .whitespaces),
            soil_type: soilType,
            sun_exposure: sunExposure,
            // Empty string clears the date server-side.
            renewal_date: hasRenewal ? formatter.string(from: renewalDate) : "",
            location_notes: locationNotes.trimmingCharacters(in: .whitespaces)))
    }

    private func sunLabel(_ raw: String) -> String {
        switch raw {
        case "full_sun":      return "Full Sun"
        case "partial_shade": return "Partial Shade"
        case "full_shade":    return "Full Shade"
        default:              return "—"
        }
    }
}
