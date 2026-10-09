import Foundation

@main struct RBTNoteChecks {
    static func main() {
        let count = RBTCount(goalId: "g1", independent: 2, prompted: 1, noResponse: 1)
        precondition(count.total == 4)
        precondition(count.percentage.contains("50.0% independent"))
        precondition(count.percentage.contains("25.0% prompted"))
        precondition(RBTCount(goalId: "empty").percentage == "No trials")
        let client = RBTClient(id: "c1", name: "Test Client", goals: [RBTGoal(id: "g1", title: "Request help", description: nil, masteryCriteria: nil)])
        let start = 1_700_000_000.0
        let session = RBTSession(id: "s1", clientId: "c1", clientName: "Test Client", startedAt: start, endedAt: nil, counts: [count], fields: ["provider_name": "Test Provider", "category_g1": "Acquisition"], noteText: nil)
        let note = RBTNote.render(session, client: client, at: Date(timeIntervalSince1970: start + 2300))
        precondition(note.contains("0.75 hours"))
        precondition(note.contains("3 15-minute units"))
        precondition(note.contains("Request help: 2 independent, 1 prompted, 1 no response"))
        precondition(note.contains("Behavior observations: Not documented"))
        precondition(!note.contains("No maladaptive behaviors were exhibited"))
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        let json = #"{"id":"s1","client_id":"c1","started_at":1700000000,"ended_at":null,"counts":[{"goal_id":"g1","independent":2,"prompted":1,"no_response":1}],"fields":{"provider_name":"Test Provider"}}"#
        let decoded = try! decoder.decode(RBTSession.self, from: Data(json.utf8))
        precondition(decoded.fields["provider_name"] == "Test Provider")
        precondition(decoded.counts[0].noResponse == 1)
        print("RBT note checks passed")
    }
}
