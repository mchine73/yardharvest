import SwiftUI

/// Garden picker presented as a sheet — bento cards instead of a flat list,
/// each showing the garden photo with the name overlaid in white.
struct GardenPickerSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(GardenStore.self) private var store

    var body: some View {
        NavigationStack {
            Group {
                if store.isLoading && store.gardens == nil {
                    YHSkeletonCard().padding()
                } else if let error = store.lastError, store.gardens == nil {
                    YHErrorState(message: error) { Task { await store.reload() } }
                } else if let payload = store.gardens {
                    content(payload)
                }
            }
            .background(YH.canvas)
            .navigationTitle("Switch Garden")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }.fontWeight(.semibold)
                }
            }
        }
    }

    @ViewBuilder
    private func content(_ payload: MyGardensPayload) -> some View {
        if payload.all.isEmpty {
            YHEmpty(systemImage: "leaf",
                    title: "No gardens yet",
                    message: "Join or create a garden on yardharvest.app to get started.")
        } else {
            ScrollView {
                LazyVStack(spacing: YH.Space.md) {
                    section("Organize", gardens: payload.organized, role: "Admin", roleColor: YH.ink)
                    section("Plot Holder", gardens: payload.plotHolder, role: "Member", roleColor: YH.lime)
                    section("Waitlist", gardens: payload.waitlisted, role: "Waitlist", roleColor: YH.muted)
                }
                .padding(YH.Space.md)
            }
            .refreshable { await store.reload() }
        }
    }

    @ViewBuilder
    private func section(_ title: String, gardens: [Garden], role: String, roleColor: Color) -> some View {
        if !gardens.isEmpty {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text(title.uppercased())
                    .font(.yhCaptionMed)
                    .tracking(0.6)
                    .foregroundStyle(YH.muted)
                ForEach(gardens) { garden in
                    Button {
                        Haptics.selection()
                        store.selectedGardenID = garden.id
                        dismiss()
                    } label: {
                        GardenCard(garden: garden, role: role, roleColor: roleColor,
                                   selected: store.selectedGardenID == garden.id,
                                   compact: true)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

/// Photo-forward garden card with the name overlaid in white. Used in the
/// picker (compact) and as a hero on the dashboard (full). Long garden
/// names get up to three lines plus aggressive auto-shrink so nothing
/// truncates.
struct GardenCard: View {
    let garden: Garden
    var role: String? = nil
    var roleColor: Color = YH.lime
    var selected: Bool = false
    /// When true, smaller hero text and a shorter card for use as a list row.
    var compact: Bool = false
    /// Optional explicit height override.
    var height: CGFloat? = nil

    private var resolvedHeight: CGFloat {
        height ?? (compact ? 132 : 220)
    }

    private var titleFont: Font {
        compact ? .system(size: 18, weight: .bold) : .system(size: 26, weight: .bold)
    }

    private var locationFont: Font {
        compact ? .system(size: 12, weight: .medium) : .system(size: 14, weight: .medium)
    }

    /// Reserve space at the top-right so the title never sits underneath the
    /// role pill / selection check on long-name gardens.
    private var titleTrailingPad: CGFloat { role != nil || selected ? 96 : YH.Space.md }

    /// Vertical room for the title block — keeps content well clear of the
    /// rounded bottom corner so text never crowds the curve.
    private var bottomTextInset: CGFloat { compact ? 16 : 22 }

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            backdrop

            // Two-stop dark scrim concentrated in the bottom 55% of the card —
            // strong enough to keep white text legible against any photo
            // (sunny skies, snow, washed-out walls), but light enough at the
            // top to let the image breathe.
            LinearGradient(
                stops: [
                    .init(color: .black.opacity(0.00), location: 0.00),
                    .init(color: .black.opacity(0.10), location: 0.45),
                    .init(color: .black.opacity(0.72), location: 1.00),
                ],
                startPoint: .top, endPoint: .bottom
            )

            // GeometryReader lets the title know exactly how much horizontal
            // room it has, so `minimumScaleFactor` can engage cleanly instead
            // of clipping. The VStack hugs the bottom — the `Spacer` only
            // grows when there's slack, otherwise content keeps its natural
            // height bounded by lineLimit + minScale.
            GeometryReader { proxy in
                VStack(alignment: .leading, spacing: 4) {
                    Spacer(minLength: 0)
                    Text(garden.name)
                        .font(titleFont)
                        .tracking(-0.5)
                        .foregroundStyle(.white)
                        .lineLimit(2)
                        .minimumScaleFactor(0.4)
                        .multilineTextAlignment(.leading)
                        .frame(
                            maxWidth: max(0, proxy.size.width
                                          - YH.Space.md   // leading inset
                                          - max(titleTrailingPad, YH.Space.md)),
                            alignment: .leading
                        )
                        .shadow(color: .black.opacity(0.55), radius: 3, y: 1)
                    let location = [garden.city, garden.state]
                        .compactMap { $0 }
                        .filter { !$0.isEmpty }
                        .joined(separator: ", ")
                    if !location.isEmpty {
                        Label(location, systemImage: "mappin.and.ellipse")
                            .font(locationFont)
                            .foregroundStyle(.white.opacity(0.95))
                            .lineLimit(1)
                            .truncationMode(.tail)
                            .shadow(color: .black.opacity(0.55), radius: 3, y: 1)
                    }
                }
                // Asymmetric padding: extra room at the bottom keeps text well
                // clear of the rounded corner. Trailing pad only reserves
                // space when there's an overlay pill so single-name cards
                // can use the full width.
                .padding(.leading, YH.Space.md)
                .padding(.trailing, max(titleTrailingPad, YH.Space.md))
                .padding(.top, YH.Space.md)
                .padding(.bottom, bottomTextInset)
            }
        }
        .overlay(alignment: .topTrailing) {
            HStack(spacing: 6) {
                if selected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(.white)
                        .shadow(color: .black.opacity(0.3), radius: 3)
                }
                if let role {
                    Text(role)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(roleColor == .white ? YH.ink : .white)
                        .padding(.horizontal, 9)
                        .padding(.vertical, 4)
                        .background(.ultraThinMaterial)
                        .clipShape(Capsule())
                }
            }
            .padding(YH.Space.sm)
        }
        .overlay {
            RoundedRectangle(cornerRadius: YH.Radius.lg, style: .continuous)
                .strokeBorder(selected ? YH.lime : .clear, lineWidth: 3)
        }
        .frame(maxWidth: .infinity)
        .frame(height: resolvedHeight)
        // Single rounded clip — drop `.clipped()` so the title's auto-shrink
        // never has its top rectangularly sliced before the rounded clip runs.
        .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg, style: .continuous))
    }

    @ViewBuilder private var backdrop: some View {
        if let url = AppEnvironment.mediaURL(garden.photoUrl) {
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let img): img.resizable().scaledToFill()
                case .empty: ZStack { brandGradient; ProgressView().tint(.white) }
                default: brandGradient
                }
            }
        } else {
            brandGradient
        }
    }

    private var brandGradient: some View {
        LinearGradient(colors: [YH.forest, YH.forest.opacity(0.7)],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
        .overlay(
            Image(systemName: "leaf.fill")
                .font(.system(size: 64))
                .foregroundStyle(.white.opacity(0.12))
        )
    }
}
