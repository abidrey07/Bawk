import SwiftUI

struct BawkRoleView: View {
    @State private var role: String?
    var body: some View {
        Group {
            if role == "client" { ContentView(onSwitchView: { role = nil }) }
            else if role == "rbt" { RBTView(onExit: { role = nil }) }
            else {
                VStack(spacing: 26) {
                    Text("🐔").font(.system(size: 84))
                    Text("Welcome to Bawk").font(.largeTitle.bold())
                    Text("Choose your space").foregroundStyle(.secondary)
                    Button("Client practice") { role = "client" }.buttonStyle(.borderedProminent)
                    Button("RBT sessions") { role = "rbt" }.buttonStyle(.bordered)
                }.frame(maxWidth: .infinity, maxHeight: .infinity).background(BawkPalette.cream).tint(BawkPalette.orange)
            }
        }
    }
}

struct RBTView: View {
    let onExit: () -> Void
    @StateObject private var store = RBTStore()
    @State private var address = ""
    @State private var code = ""
    @State private var selectedClient: RBTClient?
    @State private var showingNotes = false
    @State private var showingHistory = false
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if !store.error.isEmpty { Text(store.error).foregroundStyle(.red).accessibilityLabel("Error: \(store.error)") }
                    if !store.paired { pairing }
                    else if let session = store.active { sessionView(session) }
                    else { clientList }
                }.padding()
            }.background(BawkPalette.cream).navigationTitle(store.active == nil ? "RBT sessions" : (store.activeClient?.name ?? "Session"))
                .toolbar {
                    if store.active == nil { ToolbarItem(placement: .topBarLeading) { Button("Switch role", action: onExit) } }
                    ToolbarItem(placement: .topBarTrailing) { if store.paired { Button { showingHistory = true } label: { Image(systemName: "clock.arrow.circlepath") }.accessibilityLabel("Session history") } }
                }
                .sheet(isPresented: $showingNotes) { RBTNotesView(store: store) }
                .sheet(isPresented: $showingHistory) { RBTHistoryView(sessions: store.history) }
                .sheet(item: $selectedClient) { client in
                    VStack(spacing: 20) {
                        Text(client.name).font(.title.bold()); Text("\(client.goals.count) active goals")
                        Button("Start session") { selectedClient = nil; Task { await store.start(client) } }.buttonStyle(.borderedProminent).disabled(store.busy)
                        Button("Cancel") { selectedClient = nil }
                    }.padding().presentationDetents([.medium]).tint(BawkPalette.orange)
                }
                .task { address = store.address; await store.refresh() }
                .task(id: store.active?.id) {
                    guard store.active != nil else { return }
                    while !Task.isCancelled {
                        try? await Task.sleep(for: .seconds(20))
                        if Task.isCancelled { return }
                        await store.save()
                    }
                }
                .onChange(of: scenePhase) { _, phase in if phase != .active { Task { await store.save() } } }
        }.tint(BawkPalette.orange)
    }
    private var pairing: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Connect your RBT device").font(.title2.bold())
            Text("Use the RBT pairing code created by your supervisor. Your connection includes only your assigned clients.")
            TextField("Server address", text: $address).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
            TextField("RBT pairing code", text: $code).textInputAutocapitalization(.characters).autocorrectionDisabled()
            Button("Connect") { Task { await store.pair(address: address, code: code) } }.buttonStyle(.borderedProminent).disabled(store.busy || code.isEmpty)
        }.textFieldStyle(.roundedBorder)
    }
    private var clientList: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Hello, \(store.provider.name)").font(.title2.bold())
            Text("Choose an assigned client to begin a timed session.")
            if store.clients.isEmpty { ContentUnavailableView("No assigned clients", systemImage: "person.2", description: Text("Ask your supervisor to assign clients to this RBT connection.")) }
            ForEach(store.clients) { client in
                Button { selectedClient = client } label: {
                    HStack { Image(systemName: "person.crop.circle.fill").font(.largeTitle); VStack(alignment: .leading) { Text(client.name).font(.headline); Text("\(client.goals.count) active goals").font(.subheadline) }; Spacer(); Image(systemName: "chevron.right") }.padding().background(BawkPalette.card, in: RoundedRectangle(cornerRadius: 18))
                }.disabled(store.busy)
            }
            Button("Refresh assignments") { Task { await store.refresh() } }.disabled(store.busy)
        }
    }
    private func sessionView(_ session: RBTSession) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack { Image(systemName: "timer"); Text(Date(timeIntervalSince1970: session.startedAt), style: .timer).font(.title2.monospacedDigit()); Spacer(); Text("Session in progress").font(.caption) }
            Text("Record each opportunity once. Counts cannot go below zero.").font(.subheadline).foregroundStyle(.secondary)
            ForEach(store.activeClient?.goals ?? []) { goal in
                VStack(alignment: .leading, spacing: 12) {
                    Text(goal.title).font(.headline)
                    if let criteria = goal.masteryCriteria, !criteria.isEmpty { Text("Mastery: \(criteria)").font(.caption).foregroundStyle(.secondary) }
                    HStack(alignment: .top, spacing: 6) {
                        counter("Independent", goal: goal.id, key: \.independent)
                        counter("Prompted", goal: goal.id, key: \.prompted)
                        counter("No response", goal: goal.id, key: \.noResponse)
                    }
                    Text(store.count(for: goal.id).percentage).font(.caption)
                }.padding(12).background(BawkPalette.card, in: RoundedRectangle(cornerRadius: 18))
            }
            if store.activeClient?.goals.isEmpty != false { Text("No active goals are assigned. You can still document this session.") }
            Button("Save draft") { Task { await store.save() } }.disabled(store.busy)
            if let date = store.savedAt { Text("Draft saved \(date.formatted(date: .omitted, time: .shortened))").font(.caption).foregroundStyle(.secondary) }
            Button("Review session note") { showingNotes = true }.buttonStyle(.borderedProminent).disabled(store.busy)
            Text("Submitting the reviewed note ends the session.").font(.caption)
        }
    }
    private func counter(_ label: String, goal: String, key: WritableKeyPath<RBTCount, Int>) -> some View {
        VStack(spacing: 8) {
            Text(label).font(.caption.weight(.semibold)).lineLimit(2).minimumScaleFactor(0.75).frame(height: 30)
            Text("\(store.count(for: goal)[keyPath: key])").font(.title2.bold().monospacedDigit())
            HStack(spacing: 0) {
                Button { store.change(goal, key: key, delta: -1) } label: { Image(systemName: "minus").frame(maxWidth: .infinity, minHeight: 44) }.disabled(store.count(for: goal)[keyPath: key] == 0).accessibilityLabel("Decrease \(label)")
                Button { store.change(goal, key: key, delta: 1) } label: { Image(systemName: "plus").frame(maxWidth: .infinity, minHeight: 44) }.accessibilityLabel("Increase \(label)")
            }.buttonStyle(.borderless).disabled(store.busy)
        }.frame(maxWidth: .infinity).padding(.vertical, 8).background(BawkPalette.warmYellow.opacity(0.2), in: RoundedRectangle(cornerRadius: 10))
    }
}

struct RBTNotesView: View {
    @ObservedObject var store: RBTStore
    @Environment(\.dismiss) private var dismiss
    @State private var reviewed = false
    static let sections: [(String, [(String, String)])] = [
        ("Service", [("provider_name", "Provider full name"), ("credentials", "Credentials"), ("provider_title", "Provider title"), ("service_type", "Type of service"), ("location", "Location: home, community, telehealth"), ("present", "Others present: names and titles")]),
        ("Preparation", [("preparedness", "Client presentation / preparedness"), ("caregiver_report", "Caregiver report"), ("treatment_changes", "Treatment changes reviewed and supervisor"), ("assessment_method", "Preference / reinforcer assessment method"), ("motivators", "Client motivators"), ("pairing_statement", "Pairing and treatment implementation")]),
        ("Treatment", [("phase_changes", "Goals moved to discrimination, generalization or maintenance"), ("generalization", "Generalization"), ("maintenance", "Maintenance"), ("caregiver_participation", "Caregiver participation / observations / strategies"), ("behaviors", "Behavior observations, frequency / duration (or explicitly none)"), ("strategies", "Reactive / reduction strategies and effectiveness"), ("barriers", "Treatment barriers (or explicitly none)"), ("barrier_response", "How barriers were addressed"), ("bip", "BIP, replacement behaviors and reinforcement")]),
        ("Follow-up", [("oversight", "Supervisor / BCBA oversight, times and support"), ("safety", "Health / safety observations and actions (or explicitly none)"), ("incident", "Incident report (or not applicable)"), ("schedule_changes", "Schedule / location changes (or none)"), ("next_session", "Next scheduled session"), ("continuation_plan", "Plan for next session")])
    ]
    var body: some View {
        NavigationStack {
            Form {
                if let session = store.active {
                    Section { Text("Session times and goal percentages are generated from your recorded data. Enter observations below; blank fields remain marked Not documented.").font(.footnote) }
                    ForEach(Self.sections, id: \.0) { section in
                        Section(section.0) {
                            ForEach(section.1, id: \.0) { field in
                                VStack(alignment: .leading) {
                                    Text(field.1).font(.caption).foregroundStyle(.secondary)
                                    TextField(field.1, text: Binding(get: { store.active?.fields[field.0] ?? "" }, set: { store.setField(field.0, $0); reviewed = false }), axis: .vertical).lineLimit(2...6).disabled(store.busy)
                                }
                            }
                        }
                    }
                    Section("Goal classification") {
                        ForEach(session.counts.filter { $0.total > 0 }) { count in
                            Picker(store.activeClient?.goals.first { $0.id == count.goalId }?.title ?? count.goalId, selection: Binding(get: { store.active?.fields["category_" + count.goalId] ?? "Unclassified" }, set: { store.setField("category_" + count.goalId, $0); reviewed = false })) {
                                Text("Unclassified").tag("Unclassified")
                                Text("Acquisition").tag("Acquisition")
                                Text("Behavior").tag("Behavior")
                            }
                        }
                    }
                    Section("Generated note preview") {
                        Text(RBTNote.render(session, client: store.activeClient, at: Date())).font(.subheadline).textSelection(.enabled)
                        Text("Quarter-hour duration and 15-minute units are descriptive estimates; verify applicable documentation requirements.").font(.caption).foregroundStyle(.secondary)
                        Toggle("I reviewed this note for accuracy", isOn: $reviewed)
                    }
                    if !store.error.isEmpty { Section { Text(store.error).foregroundStyle(.red) } }
                    Section {
                        Button("Save draft") { Task { await store.save() } }.disabled(store.busy)
                        Button("Submit note & end session") { Task { await store.submit(note: RBTNote.render(session, client: store.activeClient, at: Date())); if store.active == nil { dismiss() } } }.disabled(store.busy || !reviewed || (session.fields["provider_name"] ?? "").trimmingCharacters(in: .whitespaces).isEmpty || (session.fields["location"] ?? "").trimmingCharacters(in: .whitespaces).isEmpty)
                        Text("Provider name and location are required to submit.").font(.caption)
                    }
                }
            }.navigationTitle("Session note").toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { Task { await store.save() }; dismiss() } } }
        }.tint(BawkPalette.orange)
    }
}

struct RBTHistoryView: View {
    let sessions: [RBTSession]
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                if sessions.isEmpty { Text("No submitted session notes yet.") }
                ForEach(sessions) { session in
                    NavigationLink {
                        ScrollView { Text(session.noteText ?? "No note text available.").frame(maxWidth: .infinity, alignment: .leading).padding().textSelection(.enabled) }.navigationTitle(session.clientName ?? "Session note")
                    } label: {
                        VStack(alignment: .leading) { Text(session.clientName ?? "Client").font(.headline); Text(Date(timeIntervalSince1970: session.startedAt).formatted(date: .abbreviated, time: .shortened)).font(.caption) }
                    }
                }
            }.navigationTitle("Session history").toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
        }
    }
}
