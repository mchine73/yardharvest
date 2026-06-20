import SwiftUI

struct HarvestLogView: View {
    let garden: Garden

    @State private var logs: [HarvestLog] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingAdd = false

    var totalLbs: Double { logs.reduce(0) { $0 + $1.quantityLbs } }

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: logs.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() },
                   skeletonCards: 3) {
            YHEmpty(systemImage: "basket",
                    title: "No harvests yet",
                    message: "Log your first harvest to start tracking impact.",
                    actionTitle: "Log Harvest") { showingAdd = true }
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    totalBand
                    ForEach(logs) { log in
                        HarvestRow(log: log)
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Harvest Log")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Haptics.tap()
                    showingAdd = true
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
            }
        }
        .sheet(isPresented: $showingAdd) {
            HarvestQuickAddView(garden: garden) { newLog in
                logs.insert(newLog, at: 0)
            }
        }
        .task(id: garden.id) { await load() }
    }

    private var totalBand: some View {
        YHBand(tint: .lime) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("THIS SEASON")
                        .font(.yhCaptionMed).tracking(0.8)
                    Text("\(formatted(totalLbs)) lb")
                        .font(.system(size: 32, weight: .bold))
                        .tracking(-0.6)
                    Text("\(logs.count) logged")
                        .font(.yhCaption)
                        .foregroundStyle(YH.ink.opacity(0.7))
                }
                Spacer()
                Image(systemName: "basket.fill")
                    .font(.system(size: 48))
                    .foregroundStyle(YH.ink.opacity(0.18))
            }
        }
    }

    private func formatted(_ v: Double) -> String {
        let f = NumberFormatter()
        f.maximumFractionDigits = v < 10 ? 1 : 0
        return f.string(from: NSNumber(value: v)) ?? "0"
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { logs = try await APIClient.shared.listHarvests(gardenID: garden.id) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

private struct HarvestRow: View {
    let log: HarvestLog
    var body: some View {
        YHCard {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 4) {
                        Text(log.category.capitalized).font(.yhBodyMedium).foregroundStyle(YH.ink)
                        if let v = log.variety, !v.isEmpty {
                            Text("· \(v)").font(.yhSubheadline).foregroundStyle(YH.muted)
                        }
                    }
                    HStack(spacing: 6) {
                        if let name = log.userName {
                            Text(name).font(.yhCaption).foregroundStyle(YH.muted)
                        }
                        if let date = log.harvestDate {
                            Text("·").font(.yhCaption).foregroundStyle(YH.muted)
                            Text(date.formatted(date: .abbreviated, time: .omitted))
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                }
                Spacer()
                Text("\(format(log.quantityLbs)) lb")
                    .font(.yhTitle3)
                    .foregroundStyle(YH.ink)
            }
        }
    }
    private func format(_ v: Double) -> String {
        let f = NumberFormatter(); f.maximumFractionDigits = v < 10 ? 1 : 0
        return f.string(from: NSNumber(value: v)) ?? "0"
    }
}

struct HarvestQuickAddView: View {
    let garden: Garden
    let onCreate: (HarvestLog) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var category = ""
    @State private var variety = ""
    @State private var quantityText = ""
    @State private var harvestDate = Date()
    @State private var destination: HarvestDestination = .personal
    @State private var notes = ""
    @State private var isWorking = false
    @State private var errorMessage: String?

    private let suggested = ["Tomatoes", "Greens", "Squash", "Cucumbers",
                             "Beans", "Peppers", "Herbs", "Fruit"]

    var canSubmit: Bool { !category.isEmpty && (Double(quantityText) ?? 0) > 0 }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: YH.Space.md) {
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            Text("CROP").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                            TextField("Category (e.g. Tomatoes)", text: $category)
                                .textInputAutocapitalization(.words)
                                .padding(12).background(YH.surface).clipShape(RoundedRectangle(cornerRadius: 10))
                            if category.isEmpty {
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 6) {
                                        ForEach(suggested, id: \.self) { name in
                                            Button(name) { Haptics.selection(); category = name }
                                                .font(.system(size: 12, weight: .semibold))
                                                .foregroundStyle(YH.ink)
                                                .padding(.horizontal, 12).padding(.vertical, 6)
                                                .background(YH.surface)
                                                .clipShape(Capsule())
                                                .buttonStyle(.plain)
                                        }
                                    }
                                }
                            }
                            TextField("Variety (optional, e.g. Sungold)", text: $variety)
                                .textInputAutocapitalization(.words)
                                .padding(12).background(YH.surface).clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                    }
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            Text("AMOUNT").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                            HStack {
                                TextField("0.0", text: $quantityText)
                                    .keyboardType(.decimalPad)
                                    .font(.system(size: 28, weight: .bold))
                                Text("lb").font(.yhTitle3).foregroundStyle(YH.muted)
                            }
                            DatePicker("Date", selection: $harvestDate, displayedComponents: .date)
                        }
                    }
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            Text("DESTINATION").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                            Picker("Where it went", selection: $destination) {
                                ForEach(HarvestDestination.allCases) { d in
                                    Text(d.label).tag(d)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(YH.ink)
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
                    }
                    YHButton(title: "Log Harvest", systemImage: "checkmark",
                             style: .lime, isLoading: isWorking) {
                        Task { await submit() }
                    }
                    .disabled(!canSubmit)
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("Log Harvest")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarLeading) { Button("Cancel") { dismiss() } } }
        }
    }

    private func submit() async {
        guard let qty = Double(quantityText) else { return }
        isWorking = true; errorMessage = nil
        defer { isWorking = false }
        do {
            let newLog = try await APIClient.shared.logHarvest(
                gardenID: garden.id, category: category, variety: variety,
                quantityLbs: qty, harvestDate: harvestDate,
                destination: destination, notes: notes)
            onCreate(newLog)
            Haptics.success()
            dismiss()
        } catch let e as APIError { errorMessage = e.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }
}
