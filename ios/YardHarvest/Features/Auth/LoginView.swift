import SwiftUI

/// Modern sign-in: lime hero band at the top with a "highlighted" verb, then
/// a clean form on canvas. Treats keyboard, errors, loading state with care.
struct LoginView: View {
    @Environment(AuthManager.self) private var auth
    @State private var email = ""
    @State private var password = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var showingSettings = false
    @State private var showingRegister = false
    @State private var showingForgotPassword = false
    @FocusState private var focused: Field?

    enum Field { case email, password }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: YH.Space.xl) {
                    hero
                    form
                    footer
                }
                .padding(.horizontal, YH.Space.lg)
                .padding(.top, YH.Space.lg)
                .padding(.bottom, YH.Space.xxl)
            }
            .background(YH.canvas)
            .scrollDismissesKeyboard(.interactively)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingSettings = true } label: {
                        Image(systemName: "gearshape")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundStyle(YH.muted)
                    }
                }
            }
            .sheet(isPresented: $showingSettings) {
                APIBaseURLEditorView()
            }
            .sheet(isPresented: $showingRegister) {
                RegisterView()
            }
            .sheet(isPresented: $showingForgotPassword) {
                ForgotPasswordView(
                    initialEmail: email.trimmingCharacters(in: .whitespacesAndNewlines))
            }
        }
    }

    private var hero: some View {
        YHBand(tint: .lime) {
            VStack(alignment: .leading, spacing: YH.Space.md) {
                HStack {
                    YHLogo(size: 56)
                    Spacer()
                }
                Text("Your garden,")
                    .font(.system(size: 30, weight: .semibold))
                    .tracking(-0.6)
                    .foregroundStyle(YH.ink)
                Text("in your pocket.")
                    .font(.system(size: 30, weight: .semibold))
                    .tracking(-0.6)
                    .foregroundStyle(YH.ink)
                Text("Sign up for shifts, log your harvests, scan tools, and keep up with the people you grow with.")
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.ink.opacity(0.75))
                    .padding(.top, 4)
            }
        }
    }

    private var form: some View {
        VStack(spacing: YH.Space.sm) {
            field(label: "Email", text: $email, isSecure: false, contentType: .emailAddress)
                .focused($focused, equals: .email)
                .submitLabel(.next)
                .onSubmit { focused = .password }
            field(label: "Password", text: $password, isSecure: true, contentType: .password)
                .focused($focused, equals: .password)
                .submitLabel(.go)
                .onSubmit { Task { await submit() } }

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

            YHButton(title: "Sign In", systemImage: "arrow.right",
                     style: .dark, isLoading: isSubmitting) {
                Task { await submit() }
            }
            .disabled(email.isEmpty || password.isEmpty)
            .padding(.top, YH.Space.xs)

            Button {
                Haptics.tap()
                focused = nil
                showingForgotPassword = true
            } label: {
                Text("Forgot password?")
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.muted)
                    .underline(true, color: YH.muted.opacity(0.35))
            }
            .padding(.top, YH.Space.xs)
        }
    }

    private var footer: some View {
        VStack(spacing: YH.Space.md) {
            // Gardener CTA — primary path from the login screen.
            VStack(spacing: 8) {
                Text("New here?")
                    .font(.yhCaption)
                    .foregroundStyle(YH.muted)
                Button {
                    Haptics.tap()
                    showingRegister = true
                } label: {
                    Text("Create an account")
                        .font(.yhBodyMedium)
                        .foregroundStyle(YH.ink)
                        .underline(true, color: YH.ink.opacity(0.4))
                }
            }

            // Manager note — distinct path to the website for organizers.
            HStack(spacing: 8) {
                Image(systemName: "info.circle")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(YH.muted)
                Text("Running a garden? Register your garden at ")
                    .font(.yhCaption).foregroundStyle(YH.muted)
                + Text("yardharvest.app")
                    .font(.yhCaptionMed).foregroundStyle(YH.ink)
            }
            .multilineTextAlignment(.center)
            .padding(.horizontal, YH.Space.md)
            .padding(.vertical, YH.Space.sm)
            .frame(maxWidth: .infinity)
            .background(YH.surface)
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))
        }
        .padding(.top, YH.Space.md)
    }

    private func field(label: String, text: Binding<String>, isSecure: Bool,
                       contentType: UITextContentType) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.yhCaptionMed)
                .foregroundStyle(YH.muted)
            Group {
                if isSecure {
                    SecureField("", text: text)
                } else {
                    TextField("", text: text)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.emailAddress)
                }
            }
            .textContentType(contentType)
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
    }

    private func submit() async {
        guard !isSubmitting else { return }
        isSubmitting = true
        errorMessage = nil
        defer { isSubmitting = false }
        do {
            try await auth.signIn(email: email.trimmingCharacters(in: .whitespacesAndNewlines),
                                  password: password)
        } catch let error as APIError {
            Haptics.error()
            errorMessage = error.errorDescription
        } catch {
            Haptics.error()
            errorMessage = error.localizedDescription
        }
    }
}
