import Foundation

/// Gọi server Rust/Python qua `/api/tts`, trả WAV tạm để AVAudioPlayer phát.
struct RemoteTtsClient {
    let baseURL: URL
    let token: String

    init(server: String, token: String) throws {
        let trimmed = server.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: trimmed), !trimmed.isEmpty else {
            throw RemoteTtsError.message("Server URL không hợp lệ")
        }
        self.baseURL = url
        self.token = token.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var endpoint: URL {
        if baseURL.path.hasSuffix("/api/tts") {
            return baseURL
        }
        return baseURL.appendingPathComponent("api").appendingPathComponent("tts")
    }

    func synthesize(text: String, speed: Float = 1.0) async throws -> URL {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let body: [String: Any] = [
            "text": text,
            "speed": Double(speed),
            "fixed_pauses": false,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw RemoteTtsError.message("Server không trả HTTP")
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = String(data: data, encoding: .utf8) ?? ""
            throw RemoteTtsError.message("HTTP \(http.statusCode): \(detail)")
        }

        // Server mặc định trả WAV; nếu trả JSON karaoke thì lấy audio_base64.
        let wav: Data
        let contentType = http.value(forHTTPHeaderField: "Content-Type") ?? ""
        if contentType.contains("application/json") {
            struct Payload: Decodable { let audio_base64: String }
            let payload = try JSONDecoder().decode(Payload.self, from: data)
            guard let decoded = Data(base64Encoded: payload.audio_base64) else {
                throw RemoteTtsError.message("audio_base64 hỏng")
            }
            wav = decoded
        } else {
            wav = data
        }
        guard !wav.isEmpty else {
            throw RemoteTtsError.message("Server trả audio rỗng")
        }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("vifasttts-remote-\(UUID().uuidString).wav")
        try wav.write(to: url, options: .atomic)
        return url
    }
}

enum RemoteTtsError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message): return message
        }
    }
}
