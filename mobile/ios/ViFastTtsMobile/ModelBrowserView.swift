import SwiftUI

/// Model browser iOS: tìm/tải `.vfa`/`.vfts` qua API server dùng chung.
struct ModelBrowserView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("vifasttts.serverURL") private var serverURL = ""
    @AppStorage("vifasttts.token") private var token = ""
    @State private var query = "vifasttts"
    @State private var models: [CatalogModel] = []
    @State private var files: [CatalogFile] = []
    @State private var selectedRepo = ""
    @State private var status = "Để trống Server URL để tải HuggingFace trực tiếp."
    @State private var busy = false
    @State private var downloadProgress: Double?
    @State private var downloadSize: Int64 = 0
    @State private var downloadController: ModelDownloadController?
    @State private var downloadTask: Task<Void, Never>?
    @State private var error: String?

    private var client: ModelCatalogClient {
        ModelCatalogClient(baseURL: serverURL, token: token)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    TextField("http://192.168.1.100:8000", text: $serverURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textContentType(.URL)
                    SecureField("Bearer token (tuỳ chọn)", text: $token)
                }

                Section("Tìm trên HuggingFace") {
                    HStack {
                        TextField("Từ khoá", text: $query)
                            .autocorrectionDisabled()
                        Button("Tìm") {
                            Task { await search() }
                        }
                        .disabled(busy)
                    }
                    if busy { ProgressView() }
                    if let downloadProgress {
                        ProgressView(value: downloadProgress) {
                            Text(String(
                                format: "Đang tải model… %d%% · %.1f MB",
                                Int(downloadProgress * 100),
                                Double(downloadSize) / 1_000_000
                            ))
                            .font(.caption)
                        }
                        .tint(VFTheme.accent)
                        Button("Huỷ tải", role: .destructive) {
                            downloadController?.cancel()
                            downloadTask?.cancel()
                        }
                        .font(.caption)
                    }
                    Text(status)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    if let error {
                        Text(error)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }
                }

                if !models.isEmpty {
                    Section("Repo") {
                        ForEach(models) { model in
                            Button {
                                Task { await loadFiles(model.id) }
                            } label: {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(model.id).font(.callout.bold())
                                        Text("\(model.bundleCount) bundle")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    if selectedRepo == model.id {
                                        Image(systemName: "checkmark")
                                    }
                                }
                            }
                        }
                    }
                }

                if !files.isEmpty {
                    Section("Bundle trong \(selectedRepo)") {
                        ForEach(files) { file in
                            Button {
                                downloadTask = Task { await download(file) }
                            } label: {
                                VStack(alignment: .leading) {
                                    Text(file.path).font(.callout)
                                    Text("\(file.size / 1_000_000) MB")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(VFTheme.background.ignoresSafeArea())
            .tint(VFTheme.accent)
            .font(VFTheme.body)
            .navigationTitle("Model")
            .onAppear {
                if serverURL == "http://127.0.0.1:8000" || serverURL == "http://localhost:8000" {
                    serverURL = ""
                }
            }
            .onDisappear {
                downloadController?.cancel()
                downloadTask?.cancel()
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Đóng") { dismiss() }
                }
            }
        }
    }

    private func search() async {
        busy = true
        error = nil
        status = "Đang tìm…"
        do {
            models = try await client.search(query: query.isEmpty ? "vifasttts" : query)
            files = []
            selectedRepo = ""
            status = "Thấy \(models.count) repo."
        } catch {
            self.error = error.localizedDescription
            status = "Tìm lỗi."
        }
        busy = false
    }

    private func loadFiles(_ repo: String) async {
        busy = true
        error = nil
        selectedRepo = repo
        status = "Đang xem \(repo)…"
        do {
            files = try await client.files(repo: repo)
            status = files.isEmpty ? "Repo chưa có .vfa/.vfts." : "Thấy \(files.count) bundle."
        } catch {
            self.error = error.localizedDescription
            status = "Xem repo lỗi."
        }
        busy = false
    }

    private func download(_ file: CatalogFile) async {
        let controller = ModelDownloadController()
        downloadController = controller
        downloadSize = file.size
        busy = true
        error = nil
        downloadProgress = 0
        status = "Đang tải \(file.path)…"
        defer {
            downloadProgress = nil
            downloadSize = 0
            downloadController = nil
            downloadTask = nil
            busy = false
        }
        do {
            let (data, name) = try await client.download(
                repo: selectedRepo,
                path: file.path,
                progress: { value in
                    Task { @MainActor in
                        downloadProgress = value
                    }
                },
                cancellation: controller
            )
            if controller.isCancelled {
                status = "Đã huỷ tải model."
                return
            }
            let directory = FileManager.default.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
            )[0].appendingPathComponent("models", isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let destination = directory.appendingPathComponent(name)
            try data.write(to: destination, options: .atomic)
            try await TtsEngine.shared.loadModel(at: destination)
            status = "Đã nạp \(name) (\(data.count) B)."
        } catch {
            if controller.isCancelled {
                status = "Đã huỷ tải model."
            } else {
                self.error = error.localizedDescription
                status = "Tải model lỗi."
            }
        }
    }
}
