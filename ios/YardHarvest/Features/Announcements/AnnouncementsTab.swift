import SwiftUI

struct AnnouncementsTab: View {
    @Environment(GardenStore.self) private var store
    @State private var showingPicker = false

    var body: some View {
        NavigationStack {
            Group {
                if let garden = store.selectedGarden {
                    AnnouncementsView(garden: garden)
                } else if store.isLoading {
                    YHSkeletonCard().padding()
                } else {
                    YHEmpty(systemImage: "megaphone",
                            title: "No garden selected",
                            message: "Pick a garden to view announcements.")
                }
            }
            .background(YH.canvas)
            .navigationTitle("Announcements")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Haptics.tap()
                        showingPicker = true
                    } label: {
                        Image(systemName: "arrow.up.arrow.down")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(YH.muted)
                    }
                }
            }
            .sheet(isPresented: $showingPicker) { GardenPickerSheet().environment(store) }
        }
    }
}
