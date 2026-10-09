//
//  ContentView.swift
//  Bawk
//
//  Created by Abid Rey Magsambol on 9/2/26.
//

import SwiftUI
import Combine
import AVFoundation
import Speech

enum BawkPalette {
    static let cream = adaptive(light: UIColor(red: 1, green: 0.96, blue: 0.86, alpha: 1), dark: UIColor(red: 0.15, green: 0.12, blue: 0.10, alpha: 1))
    static let card = adaptive(light: .white, dark: UIColor(red: 0.23, green: 0.19, blue: 0.16, alpha: 1))
    private static func adaptive(light: UIColor, dark: UIColor) -> Color {
        Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? dark : light })
    }
    static let warmYellow = Color(red: 1.0, green: 0.82, blue: 0.28)
    static let orange = Color(red: 0.95, green: 0.42, blue: 0.13)
    static let red = adaptive(light: UIColor(red: 0.78, green: 0.18, blue: 0.12, alpha: 1), dark: UIColor(red: 1, green: 0.58, blue: 0.35, alpha: 1))
    static let brown = adaptive(light: UIColor(red: 0.34, green: 0.20, blue: 0.10, alpha: 1), dark: UIColor(red: 0.96, green: 0.86, blue: 0.71, alpha: 1))
}

struct ChickenDisplayView: View {
    let hungerBar: Int
    let size: CGFloat

    private var isGrown: Bool { hungerBar >= 100 }

    var body: some View {
        Canvas { context, canvasSize in
            context.scaleBy(x: canvasSize.width / 200, y: canvasSize.height / 200)
            let outline = Color(red: 0.46, green: 0.27, blue: 0.12)
            let feather = isGrown ? Color(red: 1, green: 0.97, blue: 0.86) : Color(red: 1, green: 0.86, blue: 0.36)
            let shade = isGrown ? Color(red: 0.85, green: 0.76, blue: 0.55) : Color(red: 0.93, green: 0.60, blue: 0.15)

            func oval(_ rect: CGRect, _ color: Color) {
                context.fill(Path(ellipseIn: rect), with: .color(color))
            }
            func shape(_ points: [CGPoint], _ color: Color, width: CGFloat = 2.5) {
                var path = Path()
                path.addLines(points)
                path.closeSubpath()
                context.fill(path, with: .color(color))
                context.stroke(path, with: .color(outline), style: StrokeStyle(lineWidth: width, lineJoin: .round))
            }
            func line(_ points: [CGPoint], _ color: Color, width: CGFloat) {
                var path = Path()
                path.addLines(points)
                context.stroke(path, with: .color(color), style: StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round))
            }
            func shadedOval(_ rect: CGRect, light: Color, dark: Color) {
                let path = Path(ellipseIn: rect)
                context.fill(path, with: .linearGradient(Gradient(colors: [light, dark]), startPoint: CGPoint(x: rect.minX, y: rect.minY), endPoint: CGPoint(x: rect.maxX, y: rect.maxY)))
                context.stroke(path, with: .color(outline), lineWidth: 2.5)
            }

            // Far-side parts sit behind the body to establish a three-quarter pose.
            oval(CGRect(x: 39, y: 176, width: 127, height: 15), outline.opacity(0.12))
            oval(CGRect(x: 59, y: 178, width: 89, height: 8), outline.opacity(0.10))
            line([CGPoint(x: 115, y: 155), CGPoint(x: 120, y: 177), CGPoint(x: 137, y: 179)], shade, width: 7)
            line([CGPoint(x: 120, y: 176), CGPoint(x: 113, y: 181)], shade, width: 5)
            shape([CGPoint(x: 57, y: 117), CGPoint(x: 23, y: 89), CGPoint(x: 28, y: 119), CGPoint(x: 16, y: 112), CGPoint(x: 31, y: 141), CGPoint(x: 64, y: 143)], shade)
            shadedOval(CGRect(x: 118, y: 97, width: 37, height: 49), light: feather, dark: shade)
            line([CGPoint(x: 84, y: 157), CGPoint(x: 80, y: 179), CGPoint(x: 64, y: 183)], BawkPalette.orange, width: 7)
            line([CGPoint(x: 80, y: 179), CGPoint(x: 92, y: 183)], BawkPalette.orange, width: 5)
            shadedOval(CGRect(x: 39, y: 76, width: 116, height: 93), light: feather, dark: shade)

            // The near wing overlaps the breast, with two simple feather marks.
            shadedOval(CGRect(x: 46, y: 104, width: 59, height: 43), light: feather, dark: shade)
            line([CGPoint(x: 59, y: 124), CGPoint(x: 68, y: 133), CGPoint(x: 81, y: 136)], outline.opacity(0.4), width: 2)
            line([CGPoint(x: 57, y: 132), CGPoint(x: 66, y: 140)], outline.opacity(0.3), width: 2)

            if isGrown {
                oval(CGRect(x: 97, y: 25, width: 19, height: 33), BawkPalette.red)
                oval(CGRect(x: 110, y: 19, width: 20, height: 37), BawkPalette.red)
                oval(CGRect(x: 125, y: 27, width: 18, height: 30), BawkPalette.red)
                oval(CGRect(x: 140, y: 89, width: 16, height: 27), BawkPalette.red)
            } else {
                shape([CGPoint(x: 97, y: 56), CGPoint(x: 91, y: 37), CGPoint(x: 107, y: 44), CGPoint(x: 113, y: 32), CGPoint(x: 123, y: 55)], feather)
            }
            shadedOval(CGRect(x: 81, y: 43, width: 80, height: 76), light: feather, dark: shade)
            oval(CGRect(x: 95, y: 55, width: 33, height: 17), Color.white.opacity(0.22))
            // The smaller far eye and offset beak keep the face turned to the right.
            oval(CGRect(x: 145, y: 69, width: 7, height: 12), outline)
            shape([CGPoint(x: 142, y: 84), CGPoint(x: 177, y: 90), CGPoint(x: 148, y: 101)], BawkPalette.orange)
            line([CGPoint(x: 150, y: 92), CGPoint(x: 171, y: 91)], outline.opacity(0.6), width: 1.5)
            oval(CGRect(x: 119, y: 69, width: 11, height: 16), outline)
            oval(CGRect(x: 121, y: 71, width: 4, height: 5), .white)
            oval(CGRect(x: 109, y: 88, width: 18, height: 10), BawkPalette.orange.opacity(0.3))
        }
        .frame(width: size * 1.4, height: size * 1.4)
        .accessibilityLabel(isGrown ? "Fully fed chicken" : "Young chicken")
        .accessibilityValue("\(hungerBar) percent fed")
    }
}

struct ChickenHomeView: View {
    let seeds: Int
    let hungerBar: Double
    var growthLevel: Int = 0
    let clientName: String
    let canPractice: Bool
    let startPractice: () -> Void
    var hat: String = ""
    var glasses: String = ""
    var terrain: String = ""
    var openShop: () -> Void = {}
    var isActive = true
    var openSettings: () -> Void = {}

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [BawkPalette.orange.opacity(0.24), BawkPalette.cream, BawkPalette.orange.opacity(0.13)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            .background(BawkPalette.cream)
            GeometryReader { geometry in
                Circle().fill(BawkPalette.orange.opacity(0.10))
                    .frame(width: 270, height: 270).offset(x: geometry.size.width - 155, y: -100)
                Circle().fill(BawkPalette.orange.opacity(0.08))
                    .frame(width: 210, height: 210).offset(x: -100, y: geometry.size.height - 220)
            }.allowsHitTesting(false).accessibilityHidden(true)
            GeometryReader { geometry in
            ScrollView {
            VStack(spacing: 24) {
                HStack {
                    VStack() {
                        Text("Bawk")
                            .font(.largeTitle)
                            .bold()
                            .foregroundStyle(BawkPalette.red)
                            .multilineTextAlignment(.center)
                        Text(clientName.isEmpty ? "Welcome to your farm!" : "Welcome to your farm, \(clientName)!")
                            .foregroundStyle(BawkPalette.brown)
                    }
                }
                .padding(.horizontal, 48)
                .frame(maxWidth: .infinity)
                .overlay(alignment: .topTrailing) {
                    Button(action: openSettings) {
                        Image(systemName: "gearshape.fill").font(.title3)
                            .frame(width: 44, height: 44)
                            .background(BawkPalette.card.opacity(0.85), in: Circle())
                    }.tint(BawkPalette.brown).accessibilityLabel("Game settings")
                }
                .padding(.horizontal)

                Spacer()

                VStack(spacing: 16) {
                    ChickenMeadowView(hungerBar: growthLevel, isActive: isActive, hat: hat, glasses: glasses, terrain: terrain, fedLevel: hungerBar)
                    Text("I'm \(hungerBar.formatted(.number.precision(.fractionLength(1))))% fed!")
                        .font(.title3)
                        .bold()
                        .foregroundStyle(BawkPalette.brown)
                    ProgressView(value: hungerBar, total: 100)
                        .animation(.linear(duration: 1), value: hungerBar)
                        .tint(BawkPalette.orange)
                        .padding(.horizontal)
                }
                .padding()
                .background(BawkPalette.cream.opacity(0.9))
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .padding(.horizontal)

                HStack(spacing: 12) {
                    VStack {
                        Text("🌱")
                            .font(.title)
                        Text("\(seeds)")
                            .font(.title2)
                            .bold()
                            .foregroundStyle(BawkPalette.red)
                        Text("Seeds")
                            .font(.caption)
                            .foregroundStyle(BawkPalette.brown)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(BawkPalette.cream.opacity(0.9))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                    VStack {
                        Text("🍽️")
                            .font(.title)
                        Text("\(hungerBar.formatted(.number.precision(.fractionLength(1))))%")
                            .font(.title2)
                            .bold()
                            .foregroundStyle(BawkPalette.red)
                        Text("Fed")
                            .font(.caption)
                            .foregroundStyle(BawkPalette.brown)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(BawkPalette.cream.opacity(0.9))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .padding(.horizontal)

                Button("Shop · Dress up your chicken", action: openShop)
                    .buttonStyle(.bordered).tint(BawkPalette.brown)
                Button("Feed me!") {
                    startPractice()
                }
                .buttonStyle(.borderedProminent)
                .tint(BawkPalette.orange)
                .disabled(!canPractice)
                if !canPractice {
                    Text("No problem sets are ready yet.")
                        .font(.footnote)
                        .foregroundStyle(BawkPalette.brown)
                }
                Spacer()
            }
            .padding(.vertical)
            .frame(maxWidth: .infinity, minHeight: geometry.size.height)
            }
            }
        }
    }
}

struct PairDeviceView: View {
    @ObservedObject var store: PracticeStore
    @Environment(\.dismiss) private var dismiss
    @State private var address = ""
    @State private var code = ""
    var body: some View {
        NavigationStack {
            Form {
                Section("Connect to your supervisor") {
                    Text("Ask your supervisor to open Bawk on their Mac and choose Pair iOS app.")
                    TextField("Server address", text: $address)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                    TextField("Pairing code", text: $code)
                        .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    Button(store.loading ? "Connecting…" : "Connect") {
                        Task {
                            await store.pair(address: address, code: code)
                            if store.paired && store.error.isEmpty { dismiss() }
                        }
                    }.disabled(store.loading || code.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                if !store.error.isEmpty { Text(store.error).foregroundStyle(.red) }
            }
            .navigationTitle("Connect Bawk")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
            .onAppear { address = store.serverAddress }
        }
    }
}

struct AssignedPracticeView: View {
    let problemSet: PracticeSet
    @ObservedObject var store: PracticeStore
    @Environment(\.dismiss) private var dismiss
    @State private var index = 0
    @State private var runID = ""
    @State private var answers: [String: String] = [:]
    @State private var traces: [String: TraceDrawing] = [:]
    @State private var results: [AnswerResult] = []
    @State private var checks: [String: AnswerResult] = [:]
    @State private var loadingProgress = true
    @State private var attemptIDs: [String: String] = [:]
    @State private var submitting = false
    @State private var error = ""
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    ChickenDisplayView(hungerBar: results.isEmpty ? 0 : 100, size: 70)
                    if !results.isEmpty {
                        Text("Thank you for practicing!").font(.title2).bold()
                        Text("You earned \(store.awardedSeeds) seeds 🌱").font(.headline)
                        ForEach(Array(results.enumerated()), id: \.element.id) { i, result in
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Question \(i + 1)").bold()
                                Text(result.feedback)
                            }.frame(maxWidth: .infinity, alignment: .leading).padding().background(BawkPalette.card).clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        Button("Back to my chicken") { dismiss() }.buttonStyle(.borderedProminent)
                    } else if problemSet.problems.indices.contains(index) {
                        let problem = problemSet.problems[index]
                        Text("Question \(index + 1) of \(problemSet.problems.count)").font(.subheadline)
                        Text(problem.scenario).padding().frame(maxWidth: .infinity).background(BawkPalette.warmYellow.opacity(0.3)).clipShape(RoundedRectangle(cornerRadius: 12))
                        Text(problem.question).font(.title3).bold()
                        if problem.mode == "multiple_choice" {
                            ForEach(problem.choices) { choice in
                                Button {
                                    submitting = true; error = ""
                                    let attemptKey = problem.id + ":" + choice.id
                                    let requestId = attemptIDs[attemptKey] ?? UUID().uuidString
                                    attemptIDs[attemptKey] = requestId
                                    Task {
                                        do {
                                            let result = try await store.check(set: problemSet, problem: problem, choice: choice.id, requestId: requestId, runID: runID)
                                            checks[problem.id] = result
                                            answers[problem.id] = result.selectedChoiceId ?? choice.id
                                            attemptIDs.removeValue(forKey: attemptKey)
                                        } catch { self.error = error.localizedDescription }
                                        submitting = false
                                    }
                                } label: {
                                    HStack { Image(systemName: answers[problem.id] == choice.id ? "largecircle.fill.circle" : "circle"); Text(choice.text); Spacer() }.padding()
                                }
                                .buttonStyle(.plain)
                                .background(checks[problem.id]?.hintChoiceId == choice.id ? BawkPalette.orange : BawkPalette.card)
                                .foregroundStyle(checks[problem.id]?.hintChoiceId == choice.id ? Color.white : BawkPalette.brown)
                                .fontWeight(checks[problem.id]?.hintChoiceId == choice.id ? .bold : .regular)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(BawkPalette.orange, lineWidth: checks[problem.id]?.hintChoiceId == choice.id ? 3 : 1))
                                .accessibilityHint(checks[problem.id]?.hintChoiceId == choice.id ? "Suggested answer. Try this choice." : "")
                                .accessibilityAddTraits(answers[problem.id] == choice.id ? .isSelected : [])
                                .disabled(submitting || loadingProgress || runID.isEmpty || checks[problem.id]?.correct == true)
                            }
                        } else if problem.mode == "tracing" {
                            TracingQuestionView(template: problem.traceTemplate ?? "school", drawing: Binding(get: { traces[problem.id] ?? TraceDrawing() }, set: { traces[problem.id] = $0 }))
                                .id(problem.id).disabled(submitting || loadingProgress)
                        } else {
                            VoiceAnswerField(answer: Binding(get: { answers[problem.id] ?? "" }, set: { answers[problem.id] = String($0.prefix(5000)) }))
                                .id(problem.id).disabled(submitting)
                            Text("Your supervisor will review your answer.").font(.footnote)
                        }
                        if let check = checks[problem.id], !check.feedback.isEmpty {
                            Text(check.feedback).font(.headline).foregroundStyle(BawkPalette.brown)
                        }
                        if loadingProgress { ProgressView("Loading your practice…") }
                        if !loadingProgress && checks.isEmpty && !error.isEmpty {
                            Button("Retry connection") { Task { await loadProgress() } }
                        }
                        HStack {
                            if index > 0 { Button("Back") { index -= 1 }.disabled(submitting) }
                            Spacer()
                            Button(index == problemSet.problems.count - 1 ? "Finish practice" : "Next") {
                                if index < problemSet.problems.count - 1 { index += 1 }
                                else {
                                    submitting = true; error = ""
                                    Task {
                                        do { results = try await store.submit(set: problemSet, answers: answers, traces: traces, runID: runID) }
                                        catch { self.error = error.localizedDescription }
                                        submitting = false
                                    }
                                }
                            }.buttonStyle(.borderedProminent).tint(BawkPalette.orange)
                                .disabled(submitting || loadingProgress || runID.isEmpty || (problem.mode == "multiple_choice" ? checks[problem.id]?.correct != true : problem.mode == "tracing" ? (traces[problem.id]?.coverage(template: problem.traceTemplate ?? "school") ?? 0) < 0.75 : (answers[problem.id] ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty))
                        }
                        if submitting { ProgressView("Saving your answers…") }
                        if !error.isEmpty { Text(error).foregroundStyle(.red) }
                    } else {
                        Text("No questions are available yet.")
                    }
                }.padding()
            }
            .background(BawkPalette.cream)
            .navigationTitle(problemSet.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() }.disabled(submitting) } }
            .interactiveDismissDisabled(submitting)
            .task { await loadProgress() }
        }
    }
    private func loadProgress() async {
        loadingProgress = true
        do {
            let saved = try await store.progress(set: problemSet)
            guard let id = saved.runId else { throw BridgeError(message: "Update the Bawk server to start practice.") }
            runID = id
            for result in saved.results {
                checks[result.problemId] = result
                if let choice = result.selectedChoiceId { answers[result.problemId] = choice }
            }
            error = ""
        } catch { self.error = error.localizedDescription }
        loadingProgress = false
    }
}

struct ContentView: View {
    @StateObject private var store = PracticeStore()
    @Environment(\.scenePhase) private var scenePhase
    @State private var showConnection = false
    @State private var activeSet: PracticeSet?
    @State private var showShop = false
    @State private var showSettings = false
    @AppStorage("bawk.theme") private var theme = "system"
    @AppStorage("bawk.reduceMotion") private var reduceMotion = false
    @StateObject private var wardrobe = ChickenWardrobe()
    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { timeline in
        VStack(spacing: 0) {
            ChickenHomeView(seeds: max(0, store.earnedSeeds - wardrobe.spent), hungerBar: store.hunger.value(at: timeline.date), growthLevel: min(100, store.completedSets * 20),
                clientName: store.clientName, canPractice: !store.loading && !store.sets.isEmpty && store.error.isEmpty,
                startPractice: {
                    GameSound.shared.play()
                    Task {
                        await store.refresh()
                        if store.error.isEmpty { activeSet = store.sets.first }
                    }
                },
                hat: wardrobe.hat, glasses: wardrobe.glasses, terrain: wardrobe.terrain, openShop: { GameSound.shared.play(); showShop = true },
                isActive: activeSet == nil && !showConnection && !showShop && !showSettings && !reduceMotion,
                openSettings: { showSettings = true })
            if !store.error.isEmpty { Text(store.error).font(.footnote).foregroundStyle(.red).padding(.horizontal) }
            HStack {
                Button(store.paired ? "Connection" : "Connect to supervisor") { showConnection = true }
                if store.paired { Button(store.loading ? "Loading…" : "Refresh") { Task { await store.refresh() } }.disabled(store.loading) }
            }.font(.footnote).padding().frame(maxWidth: .infinity).background(BawkPalette.cream)
                .tint(BawkPalette.orange)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(BawkPalette.cream.ignoresSafeArea())
        .onChange(of: store.clientID) { _, id in wardrobe.load(clientID: id) }
        .sheet(isPresented: $showSettings) { GameSettingsView() }
        .sheet(isPresented: $showShop) { ChickenShopView(wardrobe: wardrobe, earned: store.earnedSeeds, hungerBar: min(100, store.completedSets * 20), fedLevel: store.hunger.value(at: timeline.date)) }
        .sheet(isPresented: $showConnection) { PairDeviceView(store: store) }
        .sheet(item: $activeSet, onDismiss: { Task { await store.refresh() } }) { set in AssignedPracticeView(problemSet: set, store: store) }
        .task {
            await store.refresh()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(30))
                if !Task.isCancelled && activeSet == nil && !showConnection { await store.refresh() }
            }
        }
        .onChange(of: scenePhase) { _, phase in if phase == .active && activeSet == nil { Task { await store.refresh() } } }
        }
        .preferredColorScheme(theme == "dark" ? .dark : theme == "light" ? .light : nil)
    }
}
#Preview { ContentView() }

struct ChickenShopItem: Identifiable {
    let id: String
    let title: String
    let category: String
    let price: Int
    static let all: [Self] = [
        .init(id: "party", title: "Party hat", category: "Hats", price: 150),
        .init(id: "yankees", title: "Yankees hat", category: "Hats", price: 240),
        .init(id: "thug", title: "Thug life glasses", category: "Glasses", price: 150),
        .init(id: "2026", title: "2026 glasses", category: "Glasses", price: 240),
        .init(id: "volcanic", title: "Volcanic terrain", category: "Terrains", price: 400),
        .init(id: "glowing", title: "Moonberry meadow", category: "Terrains", price: 400),
        .init(id: "crown", title: "Sunshine crown", category: "Hats", price: 360),
        .init(id: "wizard", title: "Starlight wizard hat", category: "Hats", price: 450),
        .init(id: "flower", title: "Daisy sunhat", category: "Hats", price: 300),
        .init(id: "round", title: "Explorer spectacles", category: "Glasses", price: 240),
        .init(id: "rose", title: "Rose-colored glasses", category: "Glasses", price: 300),
        .init(id: "snow", title: "Snowdrop garden", category: "Terrains", price: 550),
        .init(id: "beach", title: "Seashell island", category: "Terrains", price: 600)
    ]
}

@MainActor final class ChickenWardrobe: ObservableObject {
    private struct Saved: Codable {
        var owned: Set<String> = []
        var spent = 0
        var hat = ""
        var glasses = ""
        var terrain = ""
    }
    @Published private var saved = Saved()
    private var key = ""
    var spent: Int { saved.spent }
    var hat: String { saved.hat }
    var glasses: String { saved.glasses }
    var terrain: String { saved.terrain }
    func owns(_ item: ChickenShopItem) -> Bool { saved.owned.contains(item.id) }
    func equipped(_ item: ChickenShopItem) -> Bool { [hat, glasses, terrain].contains(item.id) }
    func load(clientID: String) {
        key = clientID.isEmpty ? "" : "bawkWardrobe.\(clientID)"
        saved = UserDefaults.standard.data(forKey: key).flatMap { try? JSONDecoder().decode(Saved.self, from: $0) } ?? Saved()
    }
    func choose(_ item: ChickenShopItem, earned: Int) {
        guard !key.isEmpty else { return }
        if !owns(item) {
            guard earned - spent >= item.price else { return }
            saved.owned.insert(item.id); saved.spent += item.price
        }
        let selection = equipped(item) ? "" : item.id
        switch item.category {
        case "Hats": saved.hat = selection
        case "Glasses": saved.glasses = selection
        default: saved.terrain = selection
        }
        if let data = try? JSONEncoder().encode(saved) { UserDefaults.standard.set(data, forKey: key) }
    }
}

struct ChickenShopView: View {
    @ObservedObject var wardrobe: ChickenWardrobe
    let earned: Int
    let hungerBar: Int
    let fedLevel: Double
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    Text("\(max(0, earned - wardrobe.spent)) seeds available").font(.headline)
                    Text("Earn seeds by finishing practice. Repeating the same set earns fewer seeds. Pick one hat, one pair of glasses, and a terrain.")
                        .font(.subheadline).multilineTextAlignment(.center)
                    ChickenMeadowView(hungerBar: hungerBar, isActive: false, hat: wardrobe.hat, glasses: wardrobe.glasses, terrain: wardrobe.terrain, fedLevel: fedLevel)
                    Text("Your equipped look").font(.caption)
                    ForEach(["Hats", "Glasses", "Terrains"], id: \.self) { category in
                        Text(category).font(.title2.bold()).frame(maxWidth: .infinity, alignment: .leading)
                        ForEach(ChickenShopItem.all.filter { $0.category == category }) { item in
                            VStack(spacing: 10) {
                                ShopItemArt(item: item).frame(height: 100)
                                Text(item.title).font(.headline)
                                if item.id == "glowing" { Text("Blue grass, glowing flowers & berries").font(.caption) }
                                Text("Try it on").font(.caption)
                                ChickenMeadowView(hungerBar: hungerBar, isActive: false,
                                    hat: category == "Hats" ? item.id : wardrobe.hat,
                                    glasses: category == "Glasses" ? item.id : wardrobe.glasses,
                                    terrain: category == "Terrains" ? item.id : wardrobe.terrain, fedLevel: fedLevel)
                                Button(wardrobe.equipped(item) ? "Unequip" : wardrobe.owns(item) ? "Equip" : "Buy & equip · \(item.price) seeds") {
                                    wardrobe.choose(item, earned: earned)
                                }.buttonStyle(.borderedProminent).tint(BawkPalette.orange)
                                    .disabled(!wardrobe.owns(item) && earned - wardrobe.spent < item.price)
                                if !wardrobe.owns(item) && earned - wardrobe.spent < item.price {
                                    Text("\(item.price - max(0, earned - wardrobe.spent)) more seeds needed").font(.caption)
                                }
                            }.padding().frame(maxWidth: .infinity).background(BawkPalette.card.opacity(0.75)).clipShape(RoundedRectangle(cornerRadius: 18))
                        }
                    }
                }.padding().foregroundStyle(BawkPalette.brown)
            }.background(BawkPalette.cream).navigationTitle("Chicken shop")
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}

struct ShopItemArt: View {
    let item: ChickenShopItem
    var body: some View {
        Canvas { context, size in
            if item.category == "Terrains" {
                context.scaleBy(x: size.width / 740, y: size.height / 180)
                context.translateBy(x: 0, y: -200)
                var painter = ChickenPainter(context: context)
                painter.meadow(time: 0, terrain: item.id)
                painter.greenery(time: 0, front: true, terrain: item.id)
            } else {
                context.translateBy(x: size.width / 2 - 120, y: item.category == "Hats" ? 25 : -30)
                var painter = ChickenPainter(context: context)
                painter.accessories(hat: item.category == "Hats" ? item.id : "", glasses: item.category == "Glasses" ? item.id : "")
            }
        }.accessibilityLabel(item.title)
    }
}


/// A short, bundled-in-code chime keeps the volume control useful without network audio.
@MainActor final class GameSound {
    static let shared = GameSound()
    private var player: AVAudioPlayer?
    func play() {
        let defaults = UserDefaults.standard
        guard defaults.object(forKey: "bawk.soundEnabled") as? Bool ?? true else { return }
        let volume = defaults.object(forKey: "bawk.volume") as? Double ?? 0.5
        guard volume > 0 else { return }
        let sampleRate = 22_050
        let count = sampleRate / 6
        var wave = Data()
        func word(_ value: UInt16) { var v = value.littleEndian; withUnsafeBytes(of: &v) { wave.append(contentsOf: $0) } }
        func dword(_ value: UInt32) { var v = value.littleEndian; withUnsafeBytes(of: &v) { wave.append(contentsOf: $0) } }
        wave.append(contentsOf: "RIFF".utf8); dword(UInt32(36 + count * 2))
        wave.append(contentsOf: "WAVEfmt ".utf8); dword(16); word(1); word(1)
        dword(UInt32(sampleRate)); dword(UInt32(sampleRate * 2)); word(2); word(16)
        wave.append(contentsOf: "data".utf8); dword(UInt32(count * 2))
        for index in 0..<count {
            let t = Double(index) / Double(sampleRate)
            let envelope = min(1, t * 150) * pow(1 - Double(index) / Double(count), 2)
            let value = Int16(sin(t * 880 * 2 * .pi) * envelope * 8_000)
            word(UInt16(bitPattern: value))
        }
        do {
            try AVAudioSession.sharedInstance().setCategory(.ambient, mode: .default)
            player = try AVAudioPlayer(data: wave)
            player?.volume = Float(volume)
            player?.play()
        } catch { /* Optional feedback must not interrupt practice. */ }
    }
}

struct GameSettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("bawk.theme") private var theme = "system"
    @AppStorage("bawk.soundEnabled") private var soundEnabled = true
    @AppStorage("bawk.volume") private var volume = 0.5
    @AppStorage("bawk.reduceMotion") private var reduceMotion = false
    var body: some View {
        NavigationStack {
            Form {
                Section("Appearance") {
                    Picker("Color theme", selection: $theme) {
                        Label("System", systemImage: "iphone").tag("system")
                        Label("Light", systemImage: "sun.max.fill").tag("light")
                        Label("Dark", systemImage: "moon.fill").tag("dark")
                    }.pickerStyle(.segmented)
                    .accessibilityLabel("Color theme")
                }
                Section {
                    Toggle("Sound effects", isOn: $soundEnabled)
                    HStack {
                        Button { volume = max(0, volume - 0.1); GameSound.shared.play() } label: {
                            Image(systemName: "speaker.fill").frame(width: 44, height: 44)
                        }.buttonStyle(.borderless).accessibilityLabel("Decrease volume")
                        Slider(value: $volume, in: 0...1, onEditingChanged: { editing in
                            if !editing { GameSound.shared.play() }
                        }).accessibilityLabel("Sound effects volume")
                        Button { volume = min(1, volume + 0.1); GameSound.shared.play() } label: {
                            Image(systemName: "speaker.wave.3.fill").frame(width: 44, height: 44)
                        }.buttonStyle(.borderless).accessibilityLabel("Increase volume")
                    }.disabled(!soundEnabled)
                    HStack {
                        Text("Volume")
                        Spacer()
                        Text(volume, format: .percent.precision(.fractionLength(0)))
                            .foregroundStyle(.secondary).monospacedDigit()
                    }
                    Button("Play sample sound") { GameSound.shared.play() }.disabled(!soundEnabled || volume == 0)
                } header: { Text("Audio") } footer: {
                    Text("Controls the chime when opening the shop or starting practice. Device volume and silent mode also apply.")
                }
                Section {
                    Toggle("Reduce chicken movement", isOn: $reduceMotion)
                } header: { Text("Movement") } footer: {
                    Text("Pause the chicken’s roaming animation. Your device’s Reduce Motion setting is also respected.")
                }
            }
            .tint(BawkPalette.orange)
            .navigationTitle("Game settings")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .scrollContentBackground(.hidden)
            .background(BawkPalette.cream)
        }
        .preferredColorScheme(theme == "dark" ? .dark : theme == "light" ? .light : nil)
    }
}

struct TracePoint: Codable {
    let x: Double
    let y: Double
    func point(in size: CGSize) -> CGPoint { CGPoint(x: x * size.width, y: y * size.height) }
}
struct TraceDrawing {
    var strokes: [[TracePoint]] = []
    static func guide(_ template: String) -> [[TracePoint]] {
        let paths: [[(Double, Double)]]
        switch template {
        case "letter_a": paths = [[(0.2,0.85),(0.5,0.15),(0.8,0.85)],[(0.33,0.55),(0.67,0.55)]]
        case "number_2": paths = [[(0.25,0.3),(0.3,0.18),(0.5,0.13),(0.7,0.2),(0.75,0.35),(0.65,0.5),(0.25,0.85),(0.78,0.85)]]
        case "star": paths = [[(0.5,0.12),(0.6,0.39),(0.88,0.4),(0.66,0.58),(0.74,0.87),(0.5,0.7),(0.26,0.87),(0.34,0.58),(0.12,0.4),(0.4,0.39),(0.5,0.12)]]
        default: paths = [[(0.1,0.8),(0.2,0.65),(0.36,0.65),(0.44,0.4),(0.62,0.4),(0.7,0.2),(0.88,0.2)]]
        }
        return paths.map { $0.map { TracePoint(x: $0.0, y: $0.1) } }
    }
    func coverage(template: String) -> Double {
        let points = strokes.flatMap { $0 }
        guard !points.isEmpty else { return 0 }
        var count = 0, covered = 0
        for stroke in Self.guide(template) {
            for (a,b) in zip(stroke, stroke.dropFirst()) {
                let steps = max(1, Int(hypot(b.x-a.x, b.y-a.y) / 0.015))
                for i in 0...steps {
                    let t = Double(i) / Double(steps)
                    let x = a.x + (b.x-a.x)*t, y = a.y + (b.y-a.y)*t
                    count += 1
                    if points.contains(where: { hypot($0.x-x, $0.y-y) <= 0.065 }) { covered += 1 }
                }
            }
        }
        return Double(covered) / Double(max(1,count))
    }
}
struct TracingQuestionView: View {
    let template: String
    @Binding var drawing: TraceDrawing
    @State private var activeStroke = false
    var body: some View {
        VStack(spacing: 12) {
            Text(template == "school" ? "Help the chicken follow the dotted path to school." : "Use your finger to follow the dotted shape.")
            Canvas { context, size in
                for guide in TraceDrawing.guide(template) {
                    var path = Path(); path.addLines(guide.map { $0.point(in: size) })
                    context.stroke(path, with: .color(BawkPalette.brown.opacity(0.5)), style: StrokeStyle(lineWidth: 7, lineCap: .round, dash: [1, 13]))
                }
                for stroke in drawing.strokes {
                    var path = Path(); path.addLines(stroke.map { $0.point(in: size) })
                    context.stroke(path, with: .color(BawkPalette.orange), style: StrokeStyle(lineWidth: 8, lineCap: .round, lineJoin: .round))
                }
                if template == "school" {
                    context.draw(Text("🐥").font(.largeTitle), at: CGPoint(x: size.width * 0.1, y: size.height * 0.89))
                    context.draw(Text("🏫").font(.largeTitle), at: CGPoint(x: size.width * 0.88, y: size.height * 0.1))
                }
            }
            .frame(height: 280).background(BawkPalette.card).clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay { GeometryReader { geometry in
                Color.clear.contentShape(Rectangle()).gesture(DragGesture(minimumDistance: 0).onChanged { value in
                    guard drawing.strokes.reduce(0, { $0 + $1.count }) < 1500, activeStroke || drawing.strokes.count < 200 else { return }
                    let x = min(1,max(0,value.location.x / geometry.size.width))
                    let y = min(1,max(0,value.location.y / geometry.size.height))
                    let p = TracePoint(x: (x * 10000).rounded() / 10000, y: (y * 10000).rounded() / 10000)
                    if activeStroke, let previous = drawing.strokes.last?.last, hypot(previous.x-p.x, previous.y-p.y) < 0.003 { return }
                    if !activeStroke { drawing.strokes.append([]); activeStroke = true }
                    drawing.strokes[drawing.strokes.count-1].append(p)
                }.onEnded { _ in activeStroke = false })
            }}
            .accessibilityLabel("Finger tracing area")
            .accessibilityHint("Follow the dotted line. Ask your support person for help if needed.")
            HStack {
                Text(drawing.coverage(template: template) >= 0.75 ? "Nice tracing! You can continue." : "Keep following the dots.").font(.footnote)
                Spacer()
                Button("Start over") { drawing = TraceDrawing(); activeStroke = false }.buttonStyle(.bordered)
            }
            if drawing.strokes.reduce(0, { $0 + $1.count }) >= 1500 || drawing.strokes.count >= 200 {
                Text("Drawing area is full. Continue if ready, or tap Start over to try again.").font(.caption)
            }
            Text("Tracing is saved for supervisor review.").font(.caption)
        }
    }
}

@MainActor final class AnswerDictation: ObservableObject {
    @Published var recording = false
    @Published var requesting = false
    @Published var transcript = ""
    @Published var message = ""
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var tapInstalled = false
    private var generation = UUID()
    func start() async {
        guard !recording, !requesting else { return }
        generation = UUID(); let current = generation
        requesting = true; message = ""; transcript = ""
        let speech = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) }
        }
        let microphone = await withCheckedContinuation { continuation in
            AVAudioSession.sharedInstance().requestRecordPermission { continuation.resume(returning: $0) }
        }
        guard current == generation else { return }
        requesting = false
        guard speech == .authorized, microphone else { message = "To dictate, allow Microphone and Speech Recognition in Settings. You can still type your answer."; return }
        guard let recognizer = SFSpeechRecognizer(), recognizer.isAvailable else { message = "Dictation is unavailable. Please type your answer."; return }
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true)
            let request = SFSpeechAudioBufferRecognitionRequest()
            request.shouldReportPartialResults = true
            self.request = request
            let input = engine.inputNode
            let format = input.outputFormat(forBus: 0)
            guard format.sampleRate > 0 else { throw BridgeError(message: "No microphone is available.") }
            input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in request.append(buffer) }
            tapInstalled = true
            engine.prepare(); try engine.start(); recording = true
            task = recognizer.recognitionTask(with: request) { [weak self] result, error in
                let words = result?.bestTranscription.formattedString
                let done = result?.isFinal == true || error != nil
                Task { @MainActor [weak self] in
                    guard let self, self.generation == current else { return }
                    if let words { self.transcript = words }
                    if done { self.stop(); if error != nil && self.transcript.isEmpty { self.message = "Could not hear an answer. Try again or type it." } }
                }
            }
        } catch { stop(); message = "Could not start dictation. You can still type your answer." }
    }
    func stop() {
        generation = UUID(); requesting = false; recording = false
        engine.stop()
        if tapInstalled { engine.inputNode.removeTap(onBus: 0); tapInstalled = false }
        request?.endAudio(); task?.cancel(); task = nil; request = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
struct VoiceAnswerField: View {
    @Environment(\.scenePhase) private var scenePhase
    @Binding var answer: String
    @StateObject private var dictation = AnswerDictation()
    @State private var prefix = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            TextField("Type your answer", text: $answer, axis: .vertical)
                .lineLimit(3...8).textFieldStyle(.roundedBorder).disabled(dictation.recording || dictation.requesting)
            Button {
                if dictation.recording { dictation.stop() }
                else { prefix = answer; Task { await dictation.start() } }
            } label: {
                Label(dictation.recording ? "Stop recording" : dictation.requesting ? "Requesting microphone…" : "Speak your answer", systemImage: dictation.recording ? "stop.circle.fill" : "mic.fill")
            }.buttonStyle(.bordered).tint(BawkPalette.orange).disabled(dictation.requesting)
            if dictation.recording { Text("Listening… Tap Stop when finished.").font(.caption) }
            Text("Dictation uses Apple Speech Recognition and may send audio to Apple. Review the text before continuing.").font(.caption).foregroundStyle(.secondary)
            if !dictation.message.isEmpty { Text(dictation.message).font(.caption).foregroundStyle(.red) }
        }
        .onChange(of: dictation.transcript) { _, words in
            if !words.isEmpty { answer = String((prefix + (prefix.isEmpty ? "" : " ") + words).prefix(5000)) }
        }
        .onDisappear { dictation.stop() }
        .onChange(of: scenePhase) { _, phase in if phase != .active { dictation.stop() } }
    }
}
