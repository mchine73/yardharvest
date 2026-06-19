import SwiftUI

/// Runtime override for the API base URL — for QA / local backend testing.
struct APIBaseURLEditorView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var urlString: String = AppEnvironment.baseURL.absoluteString

    var body: some View {
        NavigationStack {
            Form {
                Section("Base URL") {
                    TextField("https://www.yardharvest.app", text: $urlString)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                }
                Section {
                    Button("Use Production") { urlString = "https://www.yardharvest.app" }
                    Button("Use Localhost (Simulator)") { urlString = "http://localhost:5000" }
                }
                Section {
                    Button("Reset to Default", role: .destructive) {
                        AppEnvironment.setBaseURLOverride(nil)
                        urlString = AppEnvironment.defaultBaseURL.absoluteString
                    }
                } footer: {
                    Text("Default targets the Render-hosted backend. Override only for local backend testing.")
                }
            }
            .navigationTitle("Connection")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Save") {
                        AppEnvironment.setBaseURLOverride(urlString)
                        dismiss()
                    }
                    .fontWeight(.semibold)
                }
            }
        }
    }
}
