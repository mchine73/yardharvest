import SwiftUI

/// Shown on the Dashboard tab when the signed-in user isn't in any garden
/// yet. Drives them into the discover flow.
struct NoGardenWelcome: View {
    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.lg) {
                YHBand(tint: .lime) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Welcome!").font(.yhCaptionMed).tracking(0.6)
                        Text("Let's get you")
                            .font(.system(size: 28, weight: .bold)).tracking(-0.5)
                        Text("a plot to grow on.")
                            .font(.system(size: 28, weight: .bold)).tracking(-0.5)
                        Text("Browse community gardens nearby and reserve a plot or join a waitlist — it only takes a minute.")
                            .font(.yhSubheadline)
                            .foregroundStyle(YH.ink.opacity(0.75))
                            .padding(.top, 4)
                    }
                }
                NavigationLink {
                    BrowseGardensView()
                } label: {
                    YHButton(title: "Find a Garden",
                             systemImage: "magnifyingglass", style: .dark) {}
                        .allowsHitTesting(false)
                }
                .buttonStyle(.plain)

                YHCard {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "info.circle")
                            .foregroundStyle(YH.muted)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Running a garden yourself?")
                                .font(.yhBodyMedium).foregroundStyle(YH.ink)
                            Text("Garden organizers register their garden at yardharvest.app.")
                                .font(.yhSubheadline).foregroundStyle(YH.muted)
                        }
                    }
                }
            }
            .padding(YH.Space.md)
        }
        .background(YH.canvas)
    }
}
