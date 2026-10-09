import Foundation
import Combine
import Security

private enum RBTKeychain {
    static var query: [String: Any] { [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "Bawk.rbt", kSecAttrAccount as String: "token"] }
    static func read() -> String? {
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    static func save(_ token: String) throws {
        SecItemDelete(query as CFDictionary)
        var q = query; q[kSecValueData as String] = Data(token.utf8); q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(q as CFDictionary, nil) == errSecSuccess else { throw BridgeError(message: "Could not securely save the RBT connection.") }
    }
}

@MainActor final class RBTStore: ObservableObject {
    @Published var paired = RBTKeychain.read() != nil
    @Published var clients: [RBTClient] = []
    @Published var history: [RBTSession] = []
    @Published var active: RBTSession?
    @Published var provider = RBTProvider(name: "", credentials: "", title: "RBT")
    @Published var busy = false
    @Published var error = ""
    @Published var savedAt: Date?
    private var token = RBTKeychain.read()
    private var startRequest: (client: String, id: String)?
    var address: String { UserDefaults.standard.string(forKey: "bawkRBTServerAddress") ?? "http://127.0.0.1:8765" }
    var activeClient: RBTClient? { clients.first { $0.id == active?.clientId } }

    private func request<T: Decodable>(_ path: String, body: [String: Any]? = nil, address: String? = nil, auth: Bool = true) async throws -> T {
        guard let root = URL(string: (address ?? self.address).trimmingCharacters(in: .whitespacesAndNewlines)), ["http", "https"].contains(root.scheme ?? ""), root.host != nil, root.user == nil, root.password == nil else { throw BridgeError(message: "Enter the full server address from your supervisor.") }
        var req = URLRequest(url: root.appendingPathComponent(path)); req.timeoutInterval = 20
        if auth, let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body { req.httpMethod = "POST"; req.setValue("application/json", forHTTPHeaderField: "Content-Type"); req.httpBody = try JSONSerialization.data(withJSONObject: body) }
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let payload = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            throw BridgeError(message: payload?["error"] as? String ?? "Connection failed. Your session remains open; try again.")
        }
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(T.self, from: data)
    }
    func pair(address: String, code: String) async {
        guard !busy else { return }; busy = true; error = ""
        do {
            let result: PairResponse = try await request("api/rbt/pair", body: ["code": code], address: address, auth: false)
            try RBTKeychain.save(result.token); token = result.token
            UserDefaults.standard.set(address.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "bawkRBTServerAddress"); paired = true
        } catch { self.error = error.localizedDescription }
        busy = false
        if paired { await refresh() }
    }
    func refresh() async {
        guard paired, !busy else { return }; busy = true; error = ""
        do {
            let result: RBTWorkspace = try await request("api/rbt/workspace")
            clients = result.clients; provider = result.provider
            history = result.sessions.filter { $0.endedAt != nil }.sorted { $0.startedAt > $1.startedAt }
            if active == nil { active = result.sessions.first { $0.endedAt == nil } }
        } catch { self.error = error.localizedDescription }
        busy = false
    }
    func start(_ client: RBTClient) async {
        guard !busy, active == nil else { return }; busy = true; error = ""
        if startRequest?.client != client.id { startRequest = (client.id, UUID().uuidString) }
        do {
            var session: RBTSession = try await request("api/rbt/start", body: ["client_id": client.id, "request_id": startRequest!.id])
            session.fields["provider_name"] = provider.name; session.fields["credentials"] = provider.credentials; session.fields["provider_title"] = provider.title
            session.fields["service_type"] = "direct ABA services"
            active = session; startRequest = nil
        } catch { self.error = error.localizedDescription }
        busy = false
        if active != nil { await save() }
    }
    func count(for goal: String) -> RBTCount { active?.counts.first { $0.goalId == goal } ?? RBTCount(goalId: goal) }
    func change(_ goal: String, key: WritableKeyPath<RBTCount, Int>, delta: Int) {
        guard !busy, var session = active else { return }
        var count = count(for: goal); count[keyPath: key] = max(0, count[keyPath: key] + delta)
        session.counts.removeAll { $0.goalId == goal }; session.counts.append(count); active = session
    }
    func setField(_ key: String, _ value: String) { active?.fields[key] = value }
    private func body(_ session: RBTSession) -> [String: Any] {
        ["session_id": session.id, "counts": session.counts.map { ["goal_id": $0.goalId, "independent": $0.independent, "prompted": $0.prompted, "no_response": $0.noResponse] as [String: Any] }, "fields": session.fields]
    }
    func save() async {
        guard !busy, let session = active else { return }; busy = true; error = ""
        do { let _: RBTSession = try await request("api/rbt/save", body: body(session)); savedAt = Date() }
        catch { self.error = error.localizedDescription }; busy = false
    }
    func submit(note: String) async {
        guard !busy, let session = active else { return }; busy = true; error = ""
        do {
            var payload = body(session); payload["note_text"] = note
            let result: RBTSession = try await request("api/rbt/submit", body: payload)
            history.insert(result, at: 0); active = nil; savedAt = nil
        } catch { self.error = error.localizedDescription }; busy = false
    }
}
