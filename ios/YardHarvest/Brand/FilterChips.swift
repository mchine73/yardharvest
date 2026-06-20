import SwiftUI

/// Horizontal segmented pill row. Generic over any `Hashable` selection so
/// it replaces the ~5 hand-rolled `ScrollView(.horizontal) { ForEach { Button { } } }`
/// blocks that were scattered across the feature views.
///
/// Usage:
/// ```
/// YHFilterChips(selection: $filter,
///               options: ToolFilter.allCases,
///               label: { $0.label })
/// ```
struct YHFilterChips<T: Hashable & Identifiable>: View {
    @Binding var selection: T
    let options: [T]
    let label: (T) -> String

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(options) { option in
                    Button {
                        Haptics.selection()
                        selection = option
                    } label: {
                        Text(label(option))
                            .font(.system(size: 13, weight: .semibold))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .foregroundStyle(selection == option ? .white : YH.ink)
                            .background(selection == option ? YH.ink : YH.surface)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}
