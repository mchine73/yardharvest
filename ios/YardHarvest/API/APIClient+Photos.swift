import Foundation

extension APIClient {

    struct PhotoUploadResponse: Decodable {
        let id: Int?
        let url: String?
        let message: String?
    }

    /// `POST /api/photos/upload` — multipart with `photo` field.
    func uploadGardenPhoto(gardenID: Int, imageData: Data, caption: String?) async throws -> PhotoUploadResponse {
        var fields: [String: String] = [
            "garden_id": String(gardenID),
            "context": "garden",
        ]
        if let caption, !caption.isEmpty { fields["caption"] = caption }
        return try await uploadMultipart(
            "/api/photos/upload",
            fields: fields,
            fileField: "photo",
            fileName: "upload-\(Int(Date().timeIntervalSince1970)).jpg",
            mimeType: "image/jpeg",
            fileData: imageData
        )
    }
}
