import SwiftUI

/// Calendar-style date tile (month label over big day number). Used on
/// event and shift rows. Lime when emphasized, surface gray when neutral.
struct YHDateChip: View {
    let date: Date
    var emphasis: Emphasis = .neutral
    var size: CGFloat = 50

    enum Emphasis { case neutral, lime }

    var body: some View {
        VStack(spacing: 0) {
            Text(date.formatted(.dateTime.month(.abbreviated)).uppercased())
                .font(.system(size: size * 0.20, weight: .bold))
                .tracking(0.6)
                .foregroundStyle(emphasis == .lime ? YH.ink : YH.muted)
            Text(date.formatted(.dateTime.day()))
                .font(.system(size: size * 0.40, weight: .bold))
                .foregroundStyle(YH.ink)
        }
        .frame(width: size, height: size)
        .background(emphasis == .lime ? YH.lime : YH.surface)
        .clipShape(RoundedRectangle(cornerRadius: size * 0.20, style: .continuous))
    }
}

#Preview {
    HStack(spacing: 12) {
        YHDateChip(date: Date(), emphasis: .lime)
        YHDateChip(date: Date(), emphasis: .neutral)
        YHDateChip(date: Date(), emphasis: .lime, size: 40)
    }
    .padding()
}
