import Foundation

/// Client catalog dùng chung với web/extension/Android: server `/api/models/*`.
struct CatalogModel: Decodable, Identifiable {
    let id: String
    let siblings: [Sibling]?

    struct Sibling: Decodable {
        let rfilename: String
    }

    var bundleCount: Int {
        var seen = Set<String>()
        return (siblings ?? []).filter {
            guard $0.rfilename.hasSuffix(".vfa") || $0.rfilename.hasSuffix(".vfts") else {
                return false
            }
            return seen.insert(($0.rfilename as NSString).lastPathComponent).inserted
        }.count
    }
}

struct CatalogFile: Decodable, Identifiable {
    let path: String
    let size: Int64

    var id: String { path }
}

struct ModelCatalogClient {
    let baseURL: String
    let token: String
    /// URL trống = gọi HuggingFace trực tiếp (native không bị CORS).
    let direct: Bool

    init(baseURL: String, token: String) {
        let trimmed = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        self.direct = trimmed.isEmpty
        self.baseURL = trimmed.isEmpty ? "https://huggingface.co" : trimmed
        self.token = token
    }

    private func endpoint(_ path: String, query: [URLQueryItem]) throws -> URL {
        guard var components = URLComponents(string: baseURL) else {
            throw CatalogError.message("Server URL không hợp lệ")
        }
        components.path += path
        components.queryItems = query
        guard let url = components.url else {
            throw CatalogError.message("URL không hợp lệ")
        }
        return url
    }

    private func request(_ url: URL) -> URLRequest {
        var request = URLRequest(url: url)
        request.timeoutInterval = 180
        if !token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    private func get(_ url: URL) async throws -> Data {
        let (data, response) = try await URLSession.shared.data(for: request(url))
        guard let http = response as? HTTPURLResponse else {
            throw CatalogError.message("Server không trả HTTP")
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = String(data: data, encoding: .utf8) ?? ""
            throw CatalogError.message("HTTP \(http.statusCode): \(detail)")
        }
        return data
    }

    func search(query: String) async throws -> [CatalogModel] {
        let url: URL
        if direct {
            url = try endpoint("/api/models", query: [
                URLQueryItem(name: "search", value: query),
                URLQueryItem(name: "limit", value: "20"),
                URLQueryItem(name: "full", value: "true"),
            ])
        } else {
            url = try endpoint("/api/models/search", query: [
                URLQueryItem(name: "q", value: query),
                URLQueryItem(name: "limit", value: "20"),
            ])
        }
        return try JSONDecoder().decode([CatalogModel].self, from: try await get(url))
    }

    func files(repo: String) async throws -> [CatalogFile] {
        let url = try endpoint(
            direct ? "/api/models/\(repo)/tree/main" : "/api/models/files",
            query: direct ? [URLQueryItem(name: "recursive", value: "true")]
                : [URLQueryItem(name: "repo", value: repo)]
        )
        let files = try JSONDecoder().decode([CatalogFile].self, from: try await get(url))
        guard direct else { return files }
        return files.filter {
            $0.path.hasSuffix(".vfa") || $0.path.hasSuffix(".vfts")
        }
    }

    func download(repo: String, path: String) async throws -> (Data, String) {
        let url = try endpoint(
            direct ? "/\(repo)/resolve/main/\(path)" : "/api/models/download",
            query: direct ? [] : [
                URLQueryItem(name: "repo", value: repo),
                URLQueryItem(name: "path", value: path),
            ]
        )
        let data = try await get(url)
        let name = path.split(separator: "/").last.map(String.init) ?? "model.vfa"
        guard name.hasSuffix(".vfa") || name.hasSuffix(".vfts") else {
            throw CatalogError.message("Server trả file không phải .vfa/.vfts")
        }
        return (data, name)
    }
}

enum CatalogError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message): return message
        }
    }
}
