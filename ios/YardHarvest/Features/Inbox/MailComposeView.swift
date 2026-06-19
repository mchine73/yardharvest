import SwiftUI
import MessageUI
import UIKit

/// SwiftUI bridge around `MFMailComposeViewController`. Use when the user
/// chooses an admin/system contact that should open in the Mail app rather
/// than the in-app messaging system. Falls back to a `mailto:` URL when Mail
/// isn't configured.
struct MailComposeView: UIViewControllerRepresentable {
    let recipients: [String]
    var subject: String = ""
    var body: String = ""
    let onFinish: () -> Void

    static var canSend: Bool { MFMailComposeViewController.canSendMail() }

    func makeUIViewController(context: Context) -> MFMailComposeViewController {
        let vc = MFMailComposeViewController()
        vc.setToRecipients(recipients)
        if !subject.isEmpty { vc.setSubject(subject) }
        if !body.isEmpty { vc.setMessageBody(body, isHTML: false) }
        vc.mailComposeDelegate = context.coordinator
        return vc
    }

    func updateUIViewController(_ uiViewController: MFMailComposeViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onFinish: onFinish) }

    final class Coordinator: NSObject, MFMailComposeViewControllerDelegate {
        let onFinish: () -> Void
        init(onFinish: @escaping () -> Void) { self.onFinish = onFinish }
        func mailComposeController(_ controller: MFMailComposeViewController,
                                   didFinishWith result: MFMailComposeResult,
                                   error: Error?) {
            controller.dismiss(animated: true) { self.onFinish() }
        }
    }
}

/// Build a `mailto:` URL for cases where Mail isn't configured (e.g. the
/// simulator) so the system can hand off to whatever email handler exists.
enum MailtoURL {
    static func make(to: String, subject: String = "", body: String = "") -> URL? {
        var components = URLComponents()
        components.scheme = "mailto"
        components.path = to
        var items: [URLQueryItem] = []
        if !subject.isEmpty { items.append(URLQueryItem(name: "subject", value: subject)) }
        if !body.isEmpty { items.append(URLQueryItem(name: "body", value: body)) }
        if !items.isEmpty { components.queryItems = items }
        return components.url
    }
}
