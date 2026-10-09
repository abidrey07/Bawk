import Foundation
import Combine
import Security

struct ClientProfile: Codable { let id: String; let name: String }
struct PracticeChoice: Codable, Identifiable { let id: String; let text: String }
struct PracticeProblem: Codable, Identifiable {
    let id: String
    let scenario: String
    let question: String
    let mode: String
    let choices: [PracticeChoice]
    let traceTemplate: String?
}
struct PracticeSet: Codable, Identifiable {
    let id: String
    let goal: String
    let title: String
    let problems: [PracticeProblem]
}
struct ClientSnapshot: Decodable { let client: ClientProfile; let sets: [PracticeSet]; let completedSets: Int; let earnedSeeds: Int?; let hunger: HungerSnapshot }
struct PairResponse: Decodable { let token: String }
struct AnswerResult: Decodable, Identifiable {
    let problemId: String
    let correct: Bool?
    let independent: Bool?
    let prompted: Bool?
    let hintChoiceId: String?
    let selectedChoiceId: String?
    let feedback: String
    var id: String { problemId }
}
struct SubmitResponse: Decodable { let results: [AnswerResult]; let runId: String?; let completedSets: Int?; let hunger: HungerSnapshot?; let earnedSeeds: Int?; let awardedSeeds: Int?; let setAttempt: Int? }
struct BridgeError: LocalizedError { let message: String; var errorDescription: String? { message } }

struct HungerSnapshot: Decodable { let level: Double; let updatedAt: Double }

// A persisted timestamp lets the bar continue declining while the app is closed.
// The server returns the current level; local elapsed time animates between refreshes.
struct HungerAnchor: Codable {
    let level: Double
    let recordedAt: Date
    func value(at date: Date) -> Double {
        max(0, min(100, level - max(0, date.timeIntervalSince(recordedAt)) * 5 / 1800))
    }
}

private enum DeviceKeychain {
    static let service = "Bawk.localPracticeDevice"
    static func read() -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: "device",
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    static func save(_ token: String) throws {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: "device"]
        SecItemDelete(query as CFDictionary)
        var attributes = query
        attributes[kSecValueData as String] = Data(token.utf8)
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(attributes as CFDictionary, nil) == errSecSuccess else {
            throw BridgeError(message: "Could not securely save the device connection.")
        }
    }
}

@MainActor final class PracticeStore: ObservableObject {
    @Published private(set) var hunger = HungerAnchor(level: 0, recordedAt: Date())
    @Published var clientName = ""
    @Published var clientID = ""
    @Published var sets: [PracticeSet] = []
    @Published var completedSets = 0
    @Published var earnedSeeds = 0
    @Published var awardedSeeds = 0
    @Published var loading = false
    @Published var error = ""
    @Published var paired = DeviceKeychain.read() != nil
    private var token = DeviceKeychain.read()
    var serverAddress: String { UserDefaults.standard.string(forKey: "bawkServerAddress") ?? "http://127.0.0.1:8765" }

    init() {
        if let key = UserDefaults.standard.string(forKey: "bawkLastHungerKey"),
           let data = UserDefaults.standard.data(forKey: key),
           let saved = try? JSONDecoder().decode(HungerAnchor.self, from: data) {
            hunger = saved
        }
    }

    private func updateHunger(_ snapshot: HungerSnapshot, clientID: String) {
        let anchor = HungerAnchor(level: snapshot.level, recordedAt: Date())
        hunger = anchor
        let key = "bawkHunger.\(clientID)"
        if let data = try? JSONEncoder().encode(anchor) {
            UserDefaults.standard.set(data, forKey: key)
            UserDefaults.standard.set(key, forKey: "bawkLastHungerKey")
        }
    }

    private func request<T: Decodable>(_ path: String, body: [String: Any]? = nil, address: String? = nil, authenticated: Bool = true) async throws -> T {
        let base = (address ?? serverAddress).trimmingCharacters(in: .whitespacesAndNewlines)
        guard let root = URL(string: base), let scheme = root.scheme, ["http", "https"].contains(scheme), root.host != nil,
              root.user == nil, root.password == nil else {
            throw BridgeError(message: "Enter the server address shown by your supervisor, including http:// or https://.")
        }
        var req = URLRequest(url: root.appendingPathComponent(path))
        req.timeoutInterval = 15
        if authenticated, let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw BridgeError(message: "No response from the server.") }
        guard (200...299).contains(http.statusCode) else {
            let payload = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            throw BridgeError(message: payload?["error"] as? String ?? "Could not connect to your practice sets.")
        }
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(T.self, from: data)
    }

    func pair(address: String, code: String) async {
        guard !loading else { return }
        loading = true; error = ""
        do {
            let result: PairResponse = try await request("api/pair", body: ["code": code], address: address, authenticated: false)
            try DeviceKeychain.save(result.token)
            token = result.token
            UserDefaults.standard.set(address.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "bawkServerAddress")
            paired = true
        } catch { self.error = error.localizedDescription }
        loading = false
        if paired { await refresh() }
    }

    func refresh() async {
        guard paired, !loading else { return }
        loading = true
        do {
            let snapshot: ClientSnapshot = try await request("api/client")
            clientName = snapshot.client.name
            clientID = snapshot.client.id
            sets = snapshot.sets.filter { !$0.problems.isEmpty }
            completedSets = snapshot.completedSets
            earnedSeeds = snapshot.earnedSeeds ?? 0
            updateHunger(snapshot.hunger, clientID: snapshot.client.id)
            error = ""
        } catch {
            sets = [] // Do not launch stale or inaccessible assignments.
            self.error = "Could not load practice. Check the connection and tap Refresh."
        }
        loading = false
    }

    func check(set: PracticeSet, problem: PracticeProblem, choice: String, requestId: String, runID: String) async throws -> AnswerResult {
        try await request("api/attempt", body: ["set_id": set.id, "problem_id": problem.id, "choice_id": choice, "request_id": requestId, "run_id": runID])
    }
    func progress(set: PracticeSet) async throws -> SubmitResponse {
        let response: SubmitResponse = try await request("api/practice", body: ["set_id": set.id])
        return response
    }

    func submit(set: PracticeSet, answers: [String: String], traces: [String: TraceDrawing], runID: String) async throws -> [AnswerResult] {
        let rows: [[String: Any]] = set.problems.map { p in
            var row: [String: Any] = ["problem_id": p.id]
            if p.mode == "tracing", let drawing = traces[p.id] {
                row["trace"] = ["strokes": drawing.strokes.map { $0.map { ["x": $0.x, "y": $0.y] } }, "coverage": drawing.coverage(template: p.traceTemplate ?? "school")]
            } else {
                row[p.mode == "multiple_choice" ? "choice_id" : "text"] = answers[p.id] ?? ""
            }
            return row
        }
        let result: SubmitResponse = try await request("api/submit", body: ["set_id": set.id, "answers": rows, "run_id": runID])
        earnedSeeds = result.earnedSeeds ?? earnedSeeds
        awardedSeeds = result.awardedSeeds ?? 0
        if let total = result.completedSets { completedSets = total }
        if let snapshot = result.hunger { updateHunger(snapshot, clientID: clientID) }
        return result.results
    }
}
