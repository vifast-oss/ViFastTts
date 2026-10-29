import Foundation

/// Client catalog dùng chung với web/extension/Android: server `/api/models/*`.
/// Repo đã chuẩn hoá bởi Rust: id + số bundle (không cần tự lọc siblings).
struct CatalogModel: Decodable, Identifiable {
    let id: String
    let bundle_count: Int
    var bundleCount: Int { bundle_count }
}

struct CatalogFile: Decodable, Identifiable {
    let path: String
    let size: Int64

    var id: String { path }
}

/// Cầu nối catalog Rust: URL + lọc/dedupe response dùng chung Android/iOS.
enum SharedModelCatalog {
    static func take(_ pointer: UnsafeMutablePointer<CChar>?) -> String? {
        guard let pointer else { return nil }
        defer { vifasttts_string_free(pointer) }
        return String(cString: pointer)
    }

    static func urls(
        base: String,
        query: String,
        repo: String,
        path: String,
        direct: Bool
    ) -> [String: String]? {
        let raw = base.withCString { cBase in
            query.withCString { cQuery in
                repo.withCString { cRepo in
                    path.withCString { cPath in
                        take(vifasttts_model_urls_json(
                            cBase, cQuery, cRepo, cPath, 20, direct ? 1 : 0
                        ))
                    }
                }
            }
        }
        guard let raw, let data = raw.data(using: .utf8),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: String] else {
            return nil
        }
        return value
    }

    static func search(_ data: Data) -> [CatalogModel]? {
        guard let raw = String(data: data, encoding: .utf8) else { return nil }
        let normalized = raw.withCString { take(vifasttts_model_search_json($0)) }
        guard let normalized, let payload = normalized.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode([CatalogModel].self, from: payload)
    }

    static func files(_ data: Data, direct: Bool) -> [CatalogFile]? {
        guard let raw = String(data: data, encoding: .utf8) else { return nil }
        let normalized = raw.withCString {
            take(vifasttts_model_files_json($0, direct ? 1 : 0))
        }
        guard let normalized, let payload = normalized.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode([CatalogFile].self, from: payload)
    }
}

/// Tải model có progress; URLSessionDownloadDelegate chạy nền, UI nhận %.
private final class ModelDownloadDelegate: NSObject, URLSessionDownloadDelegate, @unchecked Sendable {
    private let progress: (@Sendable (Double) -> Void)?
    private let continuation: CheckedContinuation<Data, Error>
    private let lock = NSLock()
    private var finished = false
    var session: URLSession?

    init(progress: (@Sendable (Double) -> Void)?, continuation: CheckedContinuation<Data, Error>) {
        self.progress = progress
        self.continuation = continuation
    }

    private func finish(_ result: Result<Data, Error>) {
        lock.lock()
        guard !finished else {
            lock.unlock()
            return
        }
        finished = true
        lock.unlock()
        session?.invalidateAndCancel()
        continuation.resume(with: result)
    }

    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didWriteData bytesWritten: Int64,
        totalBytesWritten: Int64,
        totalBytesExpectedToWrite: Int64
    ) {
        guard totalBytesExpectedToWrite > 0 else { return }
        progress?(Double(totalBytesWritten) / Double(totalBytesExpectedToWrite))
    }

    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didFinishDownloadingTo location: URL
    ) {
        let status = (downloadTask.response as? HTTPURLResponse)?.statusCode ?? 0
        let data = (try? Data(contentsOf: location)) ?? Data()
        if !(200..<300).contains(status) {
            let detail = String(data: data, encoding: .utf8) ?? ""
            finish(.failure(CatalogError.message("HTTP \(status): \(detail)")))
            return
        }
        finish(.success(data))
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        if let error {
            finish(.failure(error))
        }
    }
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

    private func catalogURLs(
        query: String = "",
        repo: String = "",
        path: String = ""
    ) throws -> [String: String] {
        guard let urls = SharedModelCatalog.urls(
            base: direct ? "" : baseURL,
            query: query,
            repo: repo,
            path: path,
            direct: direct
        ) else {
            throw CatalogError.message("Không dựng được URL catalog")
        }
        return urls
    }

    private func legacyURL(_ path: String, query: [URLQueryItem]) throws -> URL {
        try endpoint(path, query: query)
    }

    func search(query: String) async throws -> [CatalogModel] {
        let urls = try catalogURLs(query: query.isEmpty ? "vifasttts" : query)
        guard let raw = urls["search"], let url = URL(string: raw) else {
            throw CatalogError.message("URL search không hợp lệ")
        }
        let data = try await get(url)
        if let models = SharedModelCatalog.search(data) {
            return models
        }
        // Fallback cho server cũ chưa có endpoint chuẩn hoá.
        let legacy = try legacyURL(direct ? "/api/models" : "/api/models/search", query: direct ? [
            URLQueryItem(name: "search", value: query),
            URLQueryItem(name: "limit", value: "20"),
            URLQueryItem(name: "full", value: "true"),
        ] : [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "limit", value: "20"),
        ])
        let payload = try await get(legacy)
        struct LegacyModel: Decodable {
            let id: String
            let siblings: [LegacySibling]?
        }
        struct LegacySibling: Decodable { let rfilename: String }
        let models = try JSONDecoder().decode([LegacyModel].self, from: payload)
        return models.map { model in
            var seen = Set<String>()
            let count = (model.siblings ?? []).filter {
                guard $0.rfilename.hasSuffix(".vfa") || $0.rfilename.hasSuffix(".vfts") else {
                    return false
                }
                let name = ($0.rfilename as NSString).lastPathComponent
                return seen.insert(name).inserted
            }.count
            return CatalogModel(id: model.id, bundle_count: count)
        }
    }

    func files(repo: String) async throws -> [CatalogFile] {
        let urls = try catalogURLs(repo: repo)
        guard let raw = urls["files"], let url = URL(string: raw) else {
            throw CatalogError.message("URL files không hợp lệ")
        }
        let data = try await get(url)
        if let files = SharedModelCatalog.files(data, direct: direct) {
            return files
        }
        let legacy = try legacyURL(
            direct ? "/api/models/\(repo)/tree/main" : "/api/models/files",
            query: direct ? [URLQueryItem(name: "recursive", value: "true")]
                : [URLQueryItem(name: "repo", value: repo)]
        )
        return try JSONDecoder().decode([CatalogFile].self, from: try await get(legacy))
    }

    func download(
        repo: String,
        path: String,
        progress: (@Sendable (Double) -> Void)? = nil
    ) async throws -> (Data, String) {
        let urls = try catalogURLs(repo: repo, path: path)
        guard let raw = urls["download"], let url = URL(string: raw) else {
            throw CatalogError.message("URL download không hợp lệ")
        }
        let data: Data
        if let progress {
            let request = self.request(url)
            data = try await withCheckedThrowingContinuation { continuation in
                let delegate = ModelDownloadDelegate(
                    progress: progress,
                    continuation: continuation
                )
                let session = URLSession(
                    configuration: .default,
                    delegate: delegate,
                    delegateQueue: nil
                )
                delegate.session = session
                session.downloadTask(with: request).resume()
            }
        } else {
            data = try await get(url)
        }
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
