import Foundation

struct RemoteTtsResult {
    let wavURL: URL
    let srtURL: URL?
    let vttURL: URL?
    let units: [KaraokeUnit]
}

/// Gọi server Rust/Python qua `/api/tts`, trả WAV + phụ đề tạm để phát/chia sẻ.
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

    func synthesize(
        text: String,
        speed: Float = 1.0,
        alpha: Float = 1.5,
        maxChars: Int = 300,
        fixedPauses: Bool = false,
        peakNormalize: Bool = false,
        dialect: String = "north",
        resolveOov: Bool = true,
        dictionary: String = ""
    ) async throws -> RemoteTtsResult {
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
            "alpha": Double(alpha),
            "max_chars": maxChars,
            "fixed_pauses": fixedPauses,
            "peak_normalize": peakNormalize,
            "dialect": dialect,
            "resolve_oov": resolveOov,
            "dictionary": dictionary,
            "karaoke": true,
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

        let base = FileManager.default.temporaryDirectory
            .appendingPathComponent("vifasttts-remote-\(UUID().uuidString)")
        let contentType = http.value(forHTTPHeaderField: "Content-Type") ?? ""
        if contentType.contains("application/json") {
            struct Payload: Decodable {
                let audio_base64: String
                let srt: String?
                let vtt: String?
                let vtt_karaoke: String?
                let karaoke: KaraokeDoc?
            }
            let payload = try JSONDecoder().decode(Payload.self, from: data)
            guard let wav = Data(base64Encoded: payload.audio_base64) else {
                throw RemoteTtsError.message("audio_base64 hỏng")
            }
            let wavURL = base.appendingPathExtension("wav")
            try wav.write(to: wavURL, options: .atomic)
            var srtURL: URL?
            var vttURL: URL?
            if let srt = payload.srt, !srt.isEmpty {
                let url = base.appendingPathExtension("srt")
                try srt.write(to: url, atomically: true, encoding: .utf8)
                srtURL = url
            }
            let vttText = payload.vtt ?? payload.vtt_karaoke ?? ""
            if !vttText.isEmpty {
                let url = base.appendingPathExtension("vtt")
                try vttText.write(to: url, atomically: true, encoding: .utf8)
                vttURL = url
            }
            return RemoteTtsResult(
                wavURL: wavURL,
                srtURL: srtURL,
                vttURL: vttURL,
                units: payload.karaoke?.units ?? []
            )
        }

        // Server cũ trả WAV trực tiếp.
        guard !data.isEmpty else {
            throw RemoteTtsError.message("Server trả audio rỗng")
        }
        let wavURL = base.appendingPathExtension("wav")
        try data.write(to: wavURL, options: .atomic)
        return RemoteTtsResult(wavURL: wavURL, srtURL: nil, vttURL: nil, units: [])
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
