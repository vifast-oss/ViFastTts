import SwiftUI

/// Model browser iOS: tìm/tải `.vfa`/`.vfts` qua API server dùng chung.
struct ModelBrowserView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("vifasttts.serverURL") private var serverURL = "http://127.0.0.1:8000"
    @AppStorage("vifasttts.token") private var token = ""
    @State private var query = "vifasttts"
    @State private var models: [CatalogModel] = []
    @State private var files: [CatalogFile] = []
    @State private var selectedRepo = ""
    @State private var status = "Nhập server URL rồi tìm model."
    @State private var busy = false
    @State private var error: String?

    private var client: ModelCatalogClient {
        ModelCatalogClient(baseURL: serverURL, token: token)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    TextField("http://127.0.0.1:8000", text: $serverURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
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
                                Task { await download(file) }
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
        busy = true
        error = nil
        status = "Đang tải \(file.path)…"
        do {
            let (data, name) = try await client.download(repo: selectedRepo, path: file.path)
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
            self.error = error.localizedDescription
            status = "Tải model lỗi."
        }
        busy = false
    }
}
