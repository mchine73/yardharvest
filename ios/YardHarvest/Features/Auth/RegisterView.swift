import SwiftUI

/// Gardener registration. Garden managers register on yardharvest.app —
/// the iOS app only creates `gardener`-role accounts.
struct RegisterView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(\.dismiss) private var dismiss

    @State private var step: Step = .credentials
    @State private var displayName = ""
    @State private var email = ""
    @State private var password = ""
    @State private var address = ""
    @State private var city = ""
    @State private var stateRegion = ""
    @State private var zipCode = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    enum Step: Int, CaseIterable { case credentials, location }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: YH.Space.lg) {
                    hero
                    progressBar
                    switch step {
                    case .credentials: credentialsCard
                    case .location: locationCard
                    }
                    if let errorMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "exclamationmark.circle.fill")
                                .foregroundStyle(YH.danger)
                            Text(errorMessage)
                                .font(.yhSubheadline)
                                .foregroundStyle(YH.danger)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    actionButton
                    legalNote
                }
                .padding(.horizontal, YH.Space.lg)
                .padding(.vertical, YH.Space.lg)
            }
            .background(YH.canvas)
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("Create Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    // MARK: - Pieces

    private var hero: some View {
        YHBand(tint: .lime) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Welcome to YardHarvest")
                    .font(.yhCaptionMed).tracking(0.6)
                Text(step == .credentials ? "Let's set up your account." : "Where do you garden?")
                    .font(.system(size: 26, weight: .bold))
                    .tracking(-0.5)
            }
        }
    }

    private var progressBar: some View {
        HStack(spacing: 6) {
            ForEach(Step.allCases, id: \.self) { s in
                Capsule()
                    .fill(s.rawValue <= step.rawValue ? YH.ink : YH.surface)
                    .frame(height: 4)
            }
        }
    }

    private var credentialsCard: some View {
        VStack(spacing: YH.Space.sm) {
            field("Your name", text: $displayName,
                  placeholder: "What should we call you?",
                  capitalization: .words, contentType: .name)
            field("Email", text: $email,
                  placeholder: "you@example.com",
                  contentType: .emailAddress, isEmail: true)
            field("Password", text: $password,
                  placeholder: "At least 8 characters",
                  contentType: .newPassword, isSecure: true)
        }
    }

    private var locationCard: some View {
        VStack(spacing: YH.Space.sm) {
            field("Address", text: $address,
                  placeholder: "Street", capitalization: .words,
                  contentType: .streetAddressLine1)
            HStack(spacing: YH.Space.sm) {
                field("City", text: $city, placeholder: "",
                      capitalization: .words, contentType: .addressCity).frame(maxWidth: .infinity)
                field("State", text: $stateRegion, placeholder: "",
                      capitalization: .characters, contentType: .addressState).frame(width: 88)
            }
            field("ZIP", text: $zipCode, placeholder: "",
                  contentType: .postalCode, isNumeric: true)
        }
    }

    private var actionButton: some View {
        VStack(spacing: YH.Space.sm) {
            YHButton(
                title: step == .credentials ? "Continue" : "Create Account",
                systemImage: step == .credentials ? "arrow.right" : "checkmark",
                style: step == .credentials ? .dark : .lime,
                isLoading: isSubmitting
            ) {
                Task { await advance() }
            }
            .disabled(!canAdvance)

            if step == .location {
                Button("Back") {
                    Haptics.tap()
                    withAnimation(YH.Motion.snappy) { step = .credentials }
                }
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(YH.muted)
            }
        }
    }

    private var legalNote: some View {
        VStack(spacing: 4) {
            Text("By creating an account you agree to YardHarvest's terms.")
                .font(.yhCaption).foregroundStyle(YH.muted)
                .multilineTextAlignment(.center)
            HStack(spacing: 4) {
                Image(systemName: "info.circle")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(YH.muted)
                Text("Running a garden? Register it at yardharvest.app.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
        }
        .padding(.top, YH.Space.sm)
    }

    // MARK: - Validation

    private var canAdvance: Bool {
        switch step {
        case .credentials:
            return !displayName.isEmpty
                && email.contains("@")
                && password.count >= 8
        case .location:
            return !address.isEmpty && !city.isEmpty
                && stateRegion.count == 2 && zipCode.count == 5
        }
    }

    private func advance() async {
        guard canAdvance, !isSubmitting else { return }
        if step == .credentials {
            withAnimation(YH.Motion.snappy) {
                step = .location
                errorMessage = nil
            }
            Haptics.tap()
            return
        }
        await submit()
    }

    private func submit() async {
        isSubmitting = true
        errorMessage = nil
        defer { isSubmitting = false }
        let username = makeUsername()
        do {
            try await auth.signUp(
                email: email.trimmingCharacters(in: .whitespacesAndNewlines),
                password: password,
                displayName: displayName.trimmingCharacters(in: .whitespacesAndNewlines),
                username: username,
                address: address.trimmingCharacters(in: .whitespacesAndNewlines),
                city: city.trimmingCharacters(in: .whitespacesAndNewlines),
                state: stateRegion.uppercased(),
                zipCode: zipCode.trimmingCharacters(in: .whitespacesAndNewlines))
            // ContentView will switch to the home tab automatically once
            // `auth.state` becomes `.signedIn`.
            dismiss()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    /// Derive a username from email + a small random tag so two signups with
    /// similar names don't collide.
    private func makeUsername() -> String {
        let prefix = email.split(separator: "@").first.map { String($0) } ?? "gardener"
        let cleaned = prefix.lowercased().filter { $0.isLetter || $0.isNumber || $0 == "_" || $0 == "." }
        let suffix = String(Int.random(in: 100...999))
        return "\(cleaned.prefix(20))_\(suffix)"
    }

    // MARK: - Field helper

    @ViewBuilder
    private func field(_ label: String, text: Binding<String>,
                       placeholder: String,
                       capitalization: TextInputAutocapitalization = .never,
                       contentType: UITextContentType,
                       isSecure: Bool = false,
                       isEmail: Bool = false,
                       isNumeric: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.yhCaptionMed).foregroundStyle(YH.muted)
            Group {
                if isSecure {
                    SecureField(placeholder, text: text)
                } else {
                    TextField(placeholder, text: text)
                        .textInputAutocapitalization(capitalization)
                        .autocorrectionDisabled(isEmail || contentType == .username)
                }
            }
            .keyboardType(isEmail ? .emailAddress : (isNumeric ? .numberPad : .default))
            .textContentType(contentType)
            .font(.system(size: 17, weight: .medium))
            .foregroundStyle(YH.ink)
            .padding(14)
            .background(YH.surface)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
    }
}
