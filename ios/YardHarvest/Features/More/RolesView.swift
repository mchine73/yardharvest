import SwiftUI

/// Organizer-only role management — the iOS face of PR #37's garden
/// permissions. Assign co-organizer, treasurer, or volunteer lead to any
/// member of the roster; each role's description states exactly what the
/// capability map grants, mirroring the backend's own copy.
///
/// 'Organizer' is deliberately not assignable: it follows garden ownership,
/// and the backend refuses it here.
struct RolesView: View {
    let garden: Garden

    @State private var members: [GardenMember] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var picking: GardenMember?
    @State private var workingId: Int?
    @State private var assigned: [Int: String] = [:]  // userId → role set this session
    @State private var infoMessage: String?

    /// Assignable roles + the backend's honest descriptions of each.
    private static let roles: [(id: String, label: String, blurb: String)] = [
        ("co_organizer", "Co-organizer",
         "Can run the garden: plots, members, events, shifts, resources, dues and reports. Cannot change roles, billing or where payouts go."),
        ("treasurer", "Treasurer",
         "Can manage dues, expenses and reports — including taking Tap to Pay payments. No access to plots, members or settings."),
        ("volunteer_lead", "Volunteer lead",
         "Can manage events and volunteer shifts. No access to money or members."),
        ("member", "Member",
         "No administrative access."),
    ]

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: members.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() }) {
            YHEmpty(systemImage: "person.2",
                    title: "No members yet",
                    message: "Roles can be assigned once people join your garden.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    explainer
                    ForEach(members) { member in
                        memberRow(member)
                    }
                    if let infoMessage {
                        Text(infoMessage).font(.yhSubheadline).foregroundStyle(YH.ink)
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Roles")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: garden.id) { await load() }
        .confirmationDialog(
            picking.map { "Role for \($0.name)" } ?? "",
            isPresented: Binding(get: { picking != nil },
                                 set: { if !$0 { picking = nil } }),
            titleVisibility: .visible
        ) {
            ForEach(Self.roles, id: \.id) { role in
                Button(role.label) {
                    if let member = picking { Task { await assign(role.id, to: member) } }
                }
            }
        } message: {
            Text(Self.roles.map { "\($0.label): \($0.blurb)" }.joined(separator: "\n\n"))
        }
    }

    private var explainer: some View {
        YHBand(tint: .lime) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Share the load")
                    .font(.yhTitle3).foregroundStyle(YH.ink)
                Text("A co-organizer runs the day-to-day, a treasurer takes the money — including Tap to Pay — and a volunteer lead owns events and shifts. Roles grant only what they say.")
                    .font(.yhSubheadline).foregroundStyle(YH.ink.opacity(0.75))
            }
        }
    }

    private func memberRow(_ member: GardenMember) -> some View {
        YHCard {
            HStack(spacing: 12) {
                YHAvatar(name: member.name, size: 42)
                VStack(alignment: .leading, spacing: 2) {
                    Text(member.name).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    Text(subtitle(for: member))
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
                Spacer()
                if member.isOrganizer {
                    YHPill(text: "Organizer", tint: YH.ink, background: YH.lime)
                } else if workingId == member.userId {
                    ProgressView().scaleEffect(0.8)
                } else {
                    Button {
                        Haptics.tap()
                        picking = member
                    } label: {
                        HStack(spacing: 4) {
                            Text(roleLabel(for: member))
                            Image(systemName: "chevron.up.chevron.down")
                                .font(.system(size: 10, weight: .semibold))
                        }
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(YH.ink)
                        .padding(.horizontal, 12).padding(.vertical, 6)
                        .background(YH.surface)
                        .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func subtitle(for member: GardenMember) -> String {
        if member.isOrganizer { return "Owns the garden" }
        if let plot = member.plotNumber { return "Plot \(plot)" }
        return "Member"
    }

    private func roleLabel(for member: GardenMember) -> String {
        // The public roster doesn't carry admin roles; show what was set in
        // this session, else offer the change without claiming to know.
        if let set = assigned[member.userId] {
            return Self.roles.first { $0.id == set }?.label ?? set.capitalized
        }
        return "Set role"
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { members = try await APIClient.shared.listGardenMembers(gardenID: garden.id) }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func assign(_ role: String, to member: GardenMember) async {
        picking = nil
        workingId = member.userId
        defer { workingId = nil }
        do {
            let set = try await APIClient.shared.changeMemberRole(
                gardenID: garden.id, userID: member.userId, role: role)
            assigned[member.userId] = set
            let label = Self.roles.first { $0.id == set }?.label ?? set
            infoMessage = "\(member.name) is now \(label.lowercased() == "member" ? "a member" : label.lowercased())."
            Haptics.success()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }
}
