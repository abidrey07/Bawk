import Foundation

struct RBTGoal: Codable, Identifiable { let id: String; let title: String; let description: String?; let masteryCriteria: String? }
struct RBTClient: Codable, Identifiable { let id: String; let name: String; let goals: [RBTGoal] }
struct RBTProvider: Codable { let name: String; let credentials: String; let title: String }
struct RBTCount: Codable, Identifiable {
    var goalId: String
    var independent = 0
    var prompted = 0
    var noResponse = 0
    var id: String { goalId }
    var total: Int { independent + prompted + noResponse }
    var percentage: String {
        guard total > 0 else { return "No trials" }
        return String(format: "%.1f%% independent · %.1f%% prompted · %.1f%% no response", Double(independent) / Double(total) * 100, Double(prompted) / Double(total) * 100, Double(noResponse) / Double(total) * 100)
    }
}
struct RBTSession: Codable, Identifiable {
    let id: String
    let clientId: String
    let clientName: String?
    let startedAt: Double
    let endedAt: Double?
    var counts: [RBTCount]
    var fields: [String: String]
    let noteText: String?
}
struct RBTWorkspace: Decodable { let provider: RBTProvider; let clients: [RBTClient]; let sessions: [RBTSession] }

enum RBTNote {
    static func render(_ session: RBTSession, client: RBTClient?, at end: Date) -> String {
        func field(_ key: String) -> String { let text = (session.fields[key] ?? "").trimmingCharacters(in: .whitespacesAndNewlines); return text.isEmpty ? "Not documented" : text }
        let start = Date(timeIntervalSince1970: session.startedAt)
        let actualEnd = session.endedAt.map(Date.init(timeIntervalSince1970:)) ?? end
        let units = max(0, Int((actualEnd.timeIntervalSince(start) / 900).rounded()))
        let hours = String(format: "%.2f", Double(units) / 4)
        func goalLines(_ category: String) -> String {
            let lines = session.counts.filter { $0.total > 0 && (session.fields["category_" + $0.goalId] ?? "Unclassified") == category }.map { count in
            let name = client?.goals.first { $0.id == count.goalId }?.title ?? count.goalId
            return "\(name): \(count.independent) independent, \(count.prompted) prompted, \(count.noResponse) no response; \(count.percentage) across \(count.total) opportunities."
        }.joined(separator: "\n")
            return lines.isEmpty ? "No opportunities recorded." : lines
        }
        return """
        On \(start.formatted(.dateTime.weekday(.wide).month(.wide).day().year())) at \(start.formatted(date: .omitted, time: .shortened)) to \(actualEnd.formatted(date: .omitted, time: .shortened)) (\(hours) hours rounded to the nearest quarter hour; \(units) 15-minute units), \(field("provider_name")), \(field("credentials")), \(field("provider_title")) provided \(field("service_type")) to \(client?.name ?? session.clientName ?? "Client") at \(field("location")).

        Others present: \(field("present")).
        Client preparedness / presentation: \(field("preparedness")). Caregiver report: \(field("caregiver_report")).
        Treatment changes reviewed on arrival: \(field("treatment_changes")).
        Preference / reinforcer assessment: \(field("assessment_method")). Client motivators: \(field("motivators")).
        Pairing and treatment implementation: \(field("pairing_statement")).

        Acquisition goals targeted:
        \(goalLines("Acquisition"))
        Behavior goals targeted:
        \(goalLines("Behavior"))
        Unclassified goals targeted:
        \(goalLines("Unclassified"))
        Phase changes: \(field("phase_changes")). Generalization: \(field("generalization")). Maintenance: \(field("maintenance")).
        Caregiver participation: \(field("caregiver_participation")).
        Behavior observations: \(field("behaviors")). Reactive / reduction strategies and effectiveness: \(field("strategies")).
        Treatment barriers: \(field("barriers")). Response to barriers: \(field("barrier_response")). BIP implementation, replacement behaviors and reinforcement: \(field("bip")).
        Supervisor / BCBA oversight: \(field("oversight")).
        Health and safety concerns / actions: \(field("safety")).
        Incident report: \(field("incident")). Schedule changes: \(field("schedule_changes")).

        Next session: \(field("next_session")). Continuation plan: \(field("continuation_plan")).
        """
    }
}
