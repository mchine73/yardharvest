import SwiftUI

/// Password recovery, reached from the sign-in screen.
///
/// The reset itself happens on the web: the backend emails a one-hour link to
/// `/reset-password?token=…`. This screen's job is just to request that email
/// and then tell the user to go check it.
///
/// The server always reports success for a well-formed address so it can't be
/// used to probe which emails have accounts — so the confirmation copy is
/// deliberately non-committal ("if an account exists").
struct ForgotPasswordView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var email: String
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var didSend = false
    @FocusState private var emailFocused: Bool

    /// `initialEmail` is prefilled from the sign-in form so the user doesn't
    /// retype it. Seeded through `State(initialValue:)` rather than assigned
    /// in `onAppear` — mutating state during the appear pass makes SwiftUI
    /// process the change mid-update.
    init(initialEmail: String = "") {
        _email = State(initialValue: initialEmail)
    }

    private var canSubmit: Bool {
        !isSubmitting && email.contains("@") && !email.hasPrefix("@")
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: YH.Space.xl) {
                    hero
                    if didSend { confirmation } else { form }
                }
                .padding(.horizontal, YH.Space.lg)
                .padding(.top, YH.Space.lg)
                .padding(.bottom, YH.Space.xxl)
            }
            .background(YH.canvas)
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle(didSend ? "" : "Reset Password")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(YH.muted)
                }
            }
            .task {
                // Take focus only after the sheet presentation has settled.
                // Setting @FocusState during the appear pass drives a
                // navigation update from inside a view update.
                guard email.isEmpty, !didSend else { return }
                try? await Task.sleep(for: .milliseconds(400))
                emailFocused = true
            }
        }
    }

    private var hero: some View {
        YHBand(tint: .lime) {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Image(systemName: didSend ? "envelope.badge.fill" : "key.horizontal.fill")
                    .font(.system(size: 26, weight: .semibold))
                    .foregroundStyle(YH.ink)
                    .padding(.bottom, 2)
                Text(didSend ? "Check your email." : "Forgot your password?")
                    .font(.system(size: 26, weight: .semibold))
                    .tracking(-0.5)
                    .foregroundStyle(YH.ink)
                Text(didSend
                     ? "If an account exists for that address, we've sent a link to choose a new password. It expires in an hour."
                     : "Enter the email you signed up with and we'll send you a link to set a new one.")
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.ink.opacity(0.75))
            }
        }
    }

    private var form: some View {
        VStack(spacing: YH.Space.sm) {
            VStack(alignment: .leading, spacing: 6) {
                Text("Email")
                    .font(.yhCaptionMed)
                    .foregroundStyle(YH.muted)
                TextField("", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .focused($emailFocused)
                    .submitLabel(.go)
                    .onSubmit { if canSubmit { Task { await submit() } } }
                    .font(.system(size: 17, weight: .medium))
                    .foregroundStyle(YH.ink)
                    .padding(14)
                    .background(YH.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous)
                            .strokeBorder(YH.border, lineWidth: 1)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))
            }

            if let errorMessage {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundStyle(YH.danger)
                    Text(errorMessage)
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.danger)
                        .multilineTextAlignment(.leading)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 4)
                .transition(.opacity.combined(with: .scale))
            }

            YHButton(title: "Send Reset Link", systemImage: "paperplane.fill",
                     style: .dark, isLoading: isSubmitting) {
                Task { await submit() }
            }
            .disabled(!canSubmit)
            .padding(.top, YH.Space.xs)
        }
    }

    private var confirmation: some View {
        VStack(spacing: YH.Space.md) {
            HStack(spacing: 8) {
                Image(systemName: "info.circle")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(YH.muted)
                Text("Didn't get it? Check your spam folder, or try again in a few minutes.")
                    .font(.yhCaption)
                    .foregroundStyle(YH.muted)
            }
            .multilineTextAlignment(.center)
            .padding(.horizontal, YH.Space.md)
            .padding(.vertical, YH.Space.sm)
            .frame(maxWidth: .infinity)
            .background(YH.surface)
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))

            YHButton(title: "Back to Sign In", style: .dark) { dismiss() }
        }
    }

    private func submit() async {
        guard !isSubmitting else { return }
        isSubmitting = true
        errorMessage = nil
        defer { isSubmitting = false }
        emailFocused = false
        do {
            try await APIClient.shared.forgotPassword(
                email: email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())
            Haptics.success()
            withAnimation { didSend = true }
        } catch APIError.rateLimited {
            Haptics.error()
            errorMessage = "Too many reset requests. Please wait a while before trying again."
        } catch let error as APIError {
            Haptics.error()
            errorMessage = error.errorDescription
        } catch {
            Haptics.error()
            errorMessage = error.localizedDescription
        }
    }
}
