import SwiftUI

struct EventsView: View {
    let garden: Garden

    @State private var events: [GardenEvent] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var filter: Filter = .upcoming

    enum Filter: String, CaseIterable, Identifiable {
        case upcoming, past, all
        var id: String { rawValue }
        var label: String { rawValue.capitalized }
    }

    var body: some View {
        Group {
            if events.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<3, id: \.self) { _ in YHSkeletonCard(rows: 2) }
                    }.padding()
                }
            } else if events.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await load() } }
            } else if events.isEmpty {
                YHEmpty(systemImage: "calendar",
                        title: "No events yet",
                        message: "Volunteer workdays and meetings will show up here.")
            } else {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        filterBar
                        ForEach(events) { e in
                            EventCard(event: e) { newStatus in
                                Task { await rsvp(e, status: newStatus) }
                            } onCancel: {
                                Task { await cancel(e) }
                            }
                        }
                    }
                    .padding(YH.Space.md)
                }
                .refreshable { await load(showSpinner: false) }
            }
        }
        .background(YH.canvas)
        .navigationTitle("Events")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: "\(garden.id)-\(filter.rawValue)") { await load() }
    }

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(Filter.allCases) { f in
                    Button {
                        Haptics.selection()
                        filter = f
                    } label: {
                        Text(f.label)
                            .font(.system(size: 13, weight: .semibold))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .foregroundStyle(filter == f ? .white : YH.ink)
                            .background(filter == f ? YH.ink : YH.surface)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { events = try await APIClient.shared.listEvents(gardenID: garden.id, show: filter.rawValue) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func rsvp(_ e: GardenEvent, status: RSVPStatus) async {
        do {
            let updated = try await APIClient.shared.rsvpEvent(gardenID: garden.id, eventID: e.id, status: status)
            if let idx = events.firstIndex(where: { $0.id == updated.id }) {
                events[idx] = updated
            }
            Haptics.success()
        } catch let err as APIError { errorMessage = err.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }

    private func cancel(_ e: GardenEvent) async {
        do {
            let updated = try await APIClient.shared.cancelRSVP(gardenID: garden.id, eventID: e.id)
            if let idx = events.firstIndex(where: { $0.id == updated.id }) {
                events[idx] = updated
            }
        } catch { errorMessage = (error as? APIError)?.errorDescription ?? error.localizedDescription }
    }
}

private struct EventCard: View {
    let event: GardenEvent
    let onRSVP: (RSVPStatus) -> Void
    let onCancel: () -> Void

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 12) {
                    if let date = event.eventDate {
                        VStack(spacing: 0) {
                            Text(date.formatted(.dateTime.month(.abbreviated)).uppercased())
                                .font(.system(size: 10, weight: .bold))
                                .tracking(0.6)
                                .foregroundStyle(YH.muted)
                            Text(date.formatted(.dateTime.day()))
                                .font(.system(size: 20, weight: .bold))
                                .foregroundStyle(YH.ink)
                        }
                        .frame(width: 50, height: 50)
                        .background(YH.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(event.title).font(.yhBodyMedium).foregroundStyle(YH.ink)
                        if let date = event.eventDate {
                            Text(date.formatted(date: .omitted, time: .shortened))
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                    Spacer()
                }
                if let desc = event.description, !desc.isEmpty {
                    Text(desc).font(.yhSubheadline).foregroundStyle(YH.muted).lineLimit(2)
                }
                HStack(spacing: 8) {
                    Label("\(event.rsvpGoing) going", systemImage: "person.2.fill")
                        .font(.yhCaption).foregroundStyle(YH.ink)
                    Spacer()
                    RSVPButton(label: "Going", isSelected: event.userRsvp == "going") { onRSVP(.going) }
                    RSVPButton(label: "Maybe", isSelected: event.userRsvp == "maybe") { onRSVP(.maybe) }
                    if event.userRsvp != nil {
                        Button { onCancel() } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 22))
                                .foregroundStyle(YH.muted)
                        }
                    }
                }
            }
        }
    }
}

private struct RSVPButton: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            Text(label)
                .font(.system(size: 12, weight: .semibold))
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .foregroundStyle(isSelected ? YH.ink : YH.muted)
                .background(isSelected ? YH.lime : YH.surface)
                .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }
}
