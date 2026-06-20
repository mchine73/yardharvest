import SwiftUI

/// Standard card section header — `YHIconTile + Title + (optional trailing)
/// + (optional chevron)`. Folds the four hand-rolled variants in
/// `DashboardCards`, `ManagerDashboardView`, `MoreTab`, `PaymentHubView`, etc.
struct YHSectionHeader: View {
    let title: String
    var systemImage: String? = nil
    /// Optional trailing string (e.g. an item count: "3" / "Today").
    var trailing: String? = nil
    /// When true, render the right-pointing chevron — for navigable rows.
    var showsChevron: Bool = false
    /// Font for the title; defaults to `.yhHeadline` for card headers but
    /// callers can drop to `.yhBodyMedium` for compact list rows.
    var titleFont: Font = .yhHeadline

    var body: some View {
        HStack(spacing: 10) {
            if let systemImage {
                YHIconTile(systemImage: systemImage)
            }
            Text(title)
                .font(titleFont)
                .foregroundStyle(YH.ink)
            Spacer()
            if let trailing {
                Text(trailing)
                    .font(.yhCaptionMed)
                    .foregroundStyle(YH.muted)
            }
            if showsChevron {
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(YH.muted)
            }
        }
    }
}
