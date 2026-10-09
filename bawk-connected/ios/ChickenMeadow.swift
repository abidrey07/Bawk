import SwiftUI

// A complete itinerary is generated once, rather than choosing random actions every frame.
struct MeadowRoute {
    enum Action: CaseIterable { case walk, look, stretch, peck }
    struct Segment {
        var action: Action
        var duration: Double
        var from: CGPoint
        var to: CGPoint
        var direction: Double
        var previousDirection: Double
    }
    struct Pose {
        var action: Action = .walk
        var progress: Double = 0
        var position = CGPoint(x: 330, y: 293)
        var direction: Double = 1
        var leg: Double = 0
        var bounce: Double = 0
    }
    let segments: [Segment]
    let duration: Double

    init() {
        var result: [Segment] = []
        var point = CGPoint(x: 330, y: 293)
        var direction = 1.0
        var lastAction: Action = .walk
        for index in 0..<48 {
            let destination = index == 47 ? CGPoint(x: 330, y: 293) : CGPoint(
                x: point.x > 370 ? Double.random(in: 240...340) : Double.random(in: 400...495),
                y: Double.random(in: 280...303))
            let nextDirection = destination.x > point.x ? 1.0 : -1.0
            result.append(Segment(action: .walk, duration: Double.random(in: 4.5...7.5), from: point,
                                  to: destination, direction: nextDirection, previousDirection: direction))
            point = destination; direction = nextDirection
            let action = [Action.look, .stretch, .peck].filter { $0 != lastAction }.randomElement()!
            result.append(Segment(action: action, duration: action == .look ? 4 : action == .stretch ? 3.6 : 3.4,
                                  from: point, to: point, direction: direction, previousDirection: direction))
            lastAction = action
        }
        result[0].previousDirection = direction
        segments = result
        duration = result.reduce(0) { $0 + $1.duration }
    }

    func pose(at time: Double) -> Pose {
        var remainder = max(0, time).truncatingRemainder(dividingBy: duration)
        for segment in segments {
            if remainder < segment.duration {
                let p = remainder / segment.duration
                let travel = p * p * (3 - 2 * p)
                let envelope = min(1, sin(p * .pi) * 4)
                let leg = segment.action == .walk ? sin(p * .pi * 12) * envelope : 0
                let turn = min(1, remainder / 0.36)
                let facing = segment.action == .walk
                    ? segment.previousDirection + (segment.direction - segment.previousDirection) * turn * turn * (3 - 2 * turn)
                    : segment.direction
                return Pose(action: segment.action, progress: p,
                            position: CGPoint(x: segment.from.x + (segment.to.x - segment.from.x) * travel,
                                              y: segment.from.y + (segment.to.y - segment.from.y) * travel),
                            direction: facing, leg: leg, bounce: -abs(leg) * 3)
            }
            remainder -= segment.duration
        }
        return Pose()
    }
}

// Fullness affects condition independently of earned growth.
struct ChickenCondition {
    let stage: Int
    init(fedLevel: Double) {
        let level = fedLevel.isFinite ? min(100, max(0, fedLevel)) : 0
        stage = level <= 0 ? 4 : level <= 25 ? 3 : level <= 50 ? 2 : level <= 75 ? 1 : 0
    }
    var wear: Double { Double(stage) / 4 }
    var label: String { ["Bright and well fed", "A little hungry", "Hungry and tired", "Very hungry", "Empty belly and exhausted"][stage] }
}

struct ChickenMeadowView: View {
    let hungerBar: Int
    var isActive = true
    var hat = ""
    var glasses = ""
    var terrain = ""
    var fedLevel: Double? = nil
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var route = MeadowRoute()
    @State private var accumulated: Double = 0
    @State private var resumedAt: Date? = nil
    private var shouldAnimate: Bool { isActive && !reduceMotion && scenePhase == .active }

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: !shouldAnimate)) { timeline in
            let elapsed = accumulated + (resumedAt.map { max(0, timeline.date.timeIntervalSince($0)) } ?? 0)
            Canvas { context, size in
                context.scaleBy(x: size.width / 740, y: size.height / 380)
                context.translateBy(x: 0, y: -20)
                var painter = ChickenPainter(context: context)
                painter.meadow(time: elapsed, terrain: terrain)
                painter.chicken(pose: reduceMotion ? MeadowRoute.Pose() : route.pose(at: elapsed), grown: hungerBar >= 100, hat: hat, glasses: glasses, condition: ChickenCondition(fedLevel: fedLevel ?? Double(hungerBar)))
                painter.greenery(time: elapsed, front: true, terrain: terrain)
            }
        }
        .aspectRatio(740.0 / 380, contentMode: .fit)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Your chicken in \(terrain == "volcanic" ? "volcanic terrain" : terrain == "glowing" ? "a glowing blue meadow" : terrain == "snow" ? "a snowdrop garden" : terrain == "beach" ? "a seashell island" : "a wildflower meadow")")
        .accessibilityValue("\((fedLevel ?? Double(hungerBar)).formatted(.number.precision(.fractionLength(1)))) percent fed. \(ChickenCondition(fedLevel: fedLevel ?? Double(hungerBar)).label)")
        .onChange(of: shouldAnimate, initial: true) { _, running in
            if running { resumedAt = Date() }
            else if let start = resumedAt { accumulated += Date().timeIntervalSince(start); resumedAt = nil }
        }
        .onDisappear {
            if let start = resumedAt { accumulated += Date().timeIntervalSince(start); resumedAt = nil }
        }
        .onAppear { if shouldAnimate && resumedAt == nil { resumedAt = Date() } }
    }
}

struct ChickenPainter {
    var context: GraphicsContext
    private let outline = Color(red: 0.47, green: 0.31, blue: 0.18)
    private func color(_ hex: UInt32) -> Color {
        Color(red: Double((hex >> 16) & 255) / 255, green: Double((hex >> 8) & 255) / 255, blue: Double(hex & 255) / 255)
    }
    private func pulse(_ p: Double, _ a: Double, _ b: Double) -> Double {
        guard p >= a && p <= b else { return 0 }
        return pow(sin((p - a) / (b - a) * .pi), 2)
    }
    private func oval(_ x: Double, _ y: Double, _ rx: Double, _ ry: Double, _ fill: Color, stroke: Bool = false) {
        let path = Path(ellipseIn: CGRect(x: x-rx, y: y-ry, width: rx*2, height: ry*2))
        context.fill(path, with: .color(fill))
        if stroke { context.stroke(path, with: .color(outline), lineWidth: 2.5) }
    }
    private func line(_ points: [(Double, Double)], _ fill: Color?, _ stroke: Color?, width: Double = 2.5) {
        var path = Path()
        path.addLines(points.map { CGPoint(x: $0.0, y: $0.1) })
        if let fill { path.closeSubpath(); context.fill(path, with: .color(fill)) }
        if let stroke { context.stroke(path, with: .color(stroke), style: StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round)) }
    }
    private func shadedOval(_ rect: CGRect, _ light: Color, _ dark: Color, stroke: Bool = true) {
        let path = Path(ellipseIn: rect)
        context.fill(path, with: .linearGradient(Gradient(colors: [light, dark]), startPoint: rect.origin,
                                                endPoint: CGPoint(x: rect.maxX, y: rect.maxY)))
        if stroke { context.stroke(path, with: .color(outline), lineWidth: 2.5) }
    }
    private mutating func rotate(_ radians: Double, at point: CGPoint) {
        context.translateBy(x: point.x, y: point.y)
        context.rotate(by: .radians(radians))
        context.translateBy(x: -point.x, y: -point.y)
    }
    private func tuft(_ x: Double, _ y: Double, _ s: Double) {
        line([(x-7*s,y),(x-9*s,y-8*s),(x-2*s,y-3*s),(x,y-13*s),(x+3*s,y-3*s),(x+9*s,y-8*s),(x+7*s,y)], color(0x78a74a), nil)
    }
    private mutating func plant(_ x: Double, _ y: Double, _ s: Double, _ t: Double) {
        let saved = context
        context.translateBy(x: x, y: y); context.rotate(by: .radians(sin(t*1.3+x)*0.04)); context.scaleBy(x: s, y: s)
        line([(0,0),(0,-36)], nil, color(0x4c7a43), width: 2)
        for i in 0..<4 {
            let base = context, n = Double(i)
            context.translateBy(x: 0, y: -7-n*8); context.rotate(by: .radians(-0.55))
            oval(-7,-3,10-n,4.5,color(0x62954b)); context = base
            context.translateBy(x: 0, y: -11-n*7); context.rotate(by: .radians(0.55))
            oval(7,-3,10-n,4.5,color(0x85b65d)); context = base
        }
        context = saved
    }
    private mutating func flower(_ x: Double, _ y: Double, _ s: Double, _ fill: Color, _ t: Double, _ phase: Double) {
        let saved = context
        context.translateBy(x: x, y: y); context.rotate(by: .radians(sin(t * .pi / 2 + phase)*0.055)); context.scaleBy(x: s, y: s)
        line([(0,0),(-2,-22)], nil, color(0x578345))
        oval(-5,-10,6,2.8,color(0x77a454))
        for i in 0..<5 { let a = Double(i) * .pi * 2 / 5; oval(-2+cos(a)*6,-25+sin(a)*6,4.5,4.5,fill) }
        oval(-2,-25,3.2,3.2,color(0xe8b443)); context = saved
    }
    mutating func greenery(time: Double, front: Bool, terrain: String = "") {
        if terrain == "volcanic" { return }
        if terrain == "snow" || terrain == "beach" {
            for i in 0..<16 {
                let a = (front ? 0 : Double.pi) + (Double(i)+0.5) * .pi / 16
                let x = 370+258*cos(a), y = 276+53*sin(a)
                if terrain == "snow" {
                    line([(x,y),(x,y-22)],nil,color(0x5b8a79),width: 2)
                    oval(x+3,y-22,5,7,.white)
                    oval(x,y+3,10,3,.white.opacity(0.8))
                } else {
                    oval(x,y,8,5,color(i%2 == 0 ? 0xffd1b6 : 0xfff2da))
                    line([(x-4,y-2),(x+3,y+2)],nil,color(0xce9977),width: 1)
                }
            }
            return
        }
        if terrain == "glowing" {
            for i in 0..<20 {
                let a = (front ? 0 : Double.pi) + (Double(i)+0.5) * .pi / 20
                let x = 370 + 257*cos(a), y = 276+53*sin(a)
                line([(x-8,y),(x-5,y-15),(x,y-3),(x+5,y-18),(x+8,y)], color(0x298dda), nil)
                oval(x,y-24,17,17,color(0x7bfbe1).opacity(0.12))
                flower(x,y,0.8,color(i%2 == 0 ? 0x8ffff0 : 0xf1b6ff),time,Double(i))
                if i%3 == 0 {
                    line([(x+15,y),(x+16,y-30)],nil,color(0x66bbd6))
                    for j in 0..<3 { oval(x+12+Double(j%2)*9,y-17-Double(j)*6,4,4,color(0xbc8cff)); oval(x+11+Double(j%2)*9,y-18-Double(j)*6,1.4,1.4,.white) }
                }
            }
            return
        }
        let palette: [UInt32] = [0xfff6d6,0xe6a5b5,0xc5b5de,0xf4d77d]
        for i in 0..<24 {
            let a = (front ? 0 : Double.pi) + (Double(i)+0.5) * .pi / 24
            let x = 370 + (257+Double(i%3)*5)*cos(a), y = 276+53*sin(a)
            tuft(x,y,0.9+Double(i%3)*0.18)
            if i%3 == 0 { plant(x,y,0.62+Double(i%4)*0.1,time) }
            flower(x+7,y+2,0.55+Double(i%4)*0.13,color(palette[i%4]),time,Double(i))
            if i%2 == 0 { flower(x-9,y+4,0.48,color(palette[(i+1)%4]),time,Double(i+1)) }
        }
        let plants: [(Double,Double,Double)] = front ? [(142,304,1),(588,304,1.1),(242,329,0.55),(501,329,0.6)] : [(132,262,1.2),(203,241,1.1),(299,227,0.7),(432,229,0.8),(540,246,1.15),(610,269,1)]
        for (x,y,s) in plants { plant(x,y,s,time) }
    }
    mutating func meadow(time: Double, terrain: String = "") {
        if terrain == "snow" || terrain == "beach" {
            let snow = terrain == "snow"
            oval(370,347,277,25,color(0x302044).opacity(0.12))
            shadedOval(CGRect(x: 85,y: 234,width: 570,height: 126),color(snow ? 0x8cb5c9 : 0x278fab),color(snow ? 0x64879b : 0x146b91),stroke: false)
            shadedOval(CGRect(x: 85,y: 210,width: 570,height: 130),color(snow ? 0xf1fbff : 0xffe7a6),color(snow ? 0xc7e6ed : 0xe6bc73),stroke: false)
            greenery(time: time, front: false, terrain: terrain)
            return
        }
        if !terrain.isEmpty {
            let lava = terrain == "volcanic"
            oval(370,347,277,25,color(0x302044).opacity(0.15))
            shadedOval(CGRect(x: 85,y: 234,width: 570,height: 126),color(lava ? 0x52404d : 0x324887),color(lava ? 0x241f31 : 0x202e65),stroke: false)
            shadedOval(CGRect(x: 85,y: 210,width: 570,height: 130),color(lava ? 0x62545f : 0x48bcec),color(lava ? 0x342a40 : 0x266bd2),stroke: false)
            if lava {
                line([(140,284),(230,264),(293,285),(360,266),(470,290),(588,267)],nil,color(0xff582b),width: 10)
                line([(140,284),(230,264),(293,285),(360,266),(470,290),(588,267)],nil,color(0xffc45d),width: 3)
                line([(293,285),(273,322)],nil,color(0xff7735),width: 5)
                line([(470,290),(512,321)],nil,color(0xff7735),width: 5)
                line([(145,243),(215,140),(279,243)],color(0x49404f),nil)
                oval(214,153,18,7,color(0xff743a)); oval(214,153,10,3,color(0xffd479))
                for i in 0..<5 { oval(214+sin(Double(i))*12,129-Double(i)*17,8+Double(i)*3,9,color(0x8d8093).opacity(0.25)) }
                for i in 0..<8 { oval(142+Double(i)*63,302+sin(Double(i)*4)*14,9,5,color(0x292435)) }
            } else { greenery(time: time, front: false, terrain: terrain) }
            return
        }
        oval(370,347,277,25,color(0x705027).opacity(0.09))
        var earth = Path()
        earth.move(to: CGPoint(x: 86,y: 270))
        earth.addCurve(to: CGPoint(x: 654,y: 270), control1: CGPoint(x: 91,y: 235), control2: CGPoint(x: 639,y: 235))
        earth.addLine(to: CGPoint(x: 654,y: 300))
        earth.addCurve(to: CGPoint(x: 86,y: 300), control1: CGPoint(x: 646,y: 367), control2: CGPoint(x: 99,y: 367))
        earth.closeSubpath()
        context.fill(earth, with: .linearGradient(Gradient(colors: [color(0xbc9056),color(0x997145)]), startPoint: CGPoint(x: 0,y: 260), endPoint: CGPoint(x: 0,y: 350)))
        for i in 0..<23 { oval(124+Double(i)*22,319+sin(Double(i)*2.2)*11,2.6,1.8,color(0xd7b17a)) }
        shadedOval(CGRect(x: 85,y: 210,width: 570,height: 130),color(0xb5d978),color(0x83b355),stroke: false)
        for i in 0..<28 {
            let a = Double(i)*2.4, r = 90+Double(i%5)*30
            let x = 370+cos(a)*r, y = 275+sin(a)*r*0.2
            for j in 0..<3 { oval(x+cos(Double(j)*2.094)*2.3,y+sin(Double(j)*2.094)*1.6,2.8,1.8,color(i%2 == 0 ? 0x78a74f : 0x94bd62)) }
        }
        greenery(time: time, front: false)
    }
    mutating func chicken(pose: MeadowRoute.Pose, grown: Bool, hat: String = "", glasses: String = "", condition: ChickenCondition = ChickenCondition(fedLevel: 100)) {
        let wear = condition.wear
        let p = pose.progress, act = pose.action
        var look = 0.0, wing = 0.0, peck = 0.0
        var breath = 1+0.012*sin(p * .pi * 2)
        if act == .look { look = 0.20*pulse(p,0.18,0.48)-0.12*pulse(p,0.56,0.86) }
        if act == .stretch { wing = -1.1*pulse(p,0.18,0.75); breath = 1+0.035*pulse(p,0.18,0.75); look = -0.08*pulse(p,0.18,0.75) }
        if act == .walk { breath = 1 }
        if act == .peck {
            peck = max(pulse(p,0.15,0.37),pulse(p,0.40,0.62),pulse(p,0.65,0.87)); look = 0.5*peck
            let eaten = p > 0.76 ? 3 : p > 0.51 ? 2 : p > 0.26 ? 1 : 0
            for i in eaten..<5 { oval(pose.position.x+pose.direction*(94+Double(i%3-1)*4),pose.position.y+Double(i%2)*3,2.7,1.6,color(0xd1a044)) }
        }
        look += wear * 0.32
        wing = wing * (1 - wear * 0.65) + wear * 0.65
        let blink = (1 - wear * 0.78) * (1-0.94*max(pulse(p,0.68,0.735),act == .look ? pulse(p,0.79,0.835) : 0))
        let saved = context
        oval(pose.position.x,pose.position.y+2,53*(2-breath),9,color(0x4e6136).opacity(0.17))
        context.translateBy(x: pose.position.x, y: pose.position.y); context.scaleBy(x: pose.direction*1.18,y: 1.18); context.translateBy(x: -100,y: -183)
        let feather = color(grown ? 0xfff2cf : 0xffdb65)
        let shade = color(grown ? 0xd8c795 : 0xedb13c), orange = color(0xed8b2c), leg = pose.leg * (1 - wear * 0.6)
        line([(115,155),(120+leg*6,177),(137+leg*6,179)],nil,color(0xba933f),width: 6)
        line([(120+leg*6,176),(113+leg*6,181)],nil,color(0xba933f),width: 4)
        line([(84,157),(80-leg*6,179),(64-leg*6,183)],nil,orange,width: 6)
        line([(80-leg*6,179),(92-leg*6,183)],nil,orange,width: 4)
        context.translateBy(x: 100,y: 162+pose.bounce * (1 - wear * 0.8) + wear * 10); context.rotate(by: .radians(0.72*peck)); context.scaleBy(x: 1/breath,y: breath * (1 - wear * 0.12)); context.translateBy(x: -100,y: -162)
        line([(57,117),(23,89),(28,119),(16,112),(31,141),(64,143)],shade,outline)
        oval(136,121,18,24,shade,stroke: true)
        shadedOval(CGRect(x: 39,y: 76.5,width: 116,height: 93),feather,shade)
        if condition.stage >= 1 {
            dirtPatch(x: 124, y: 142, size: 8, opacity: 0.28)
        }
        if condition.stage >= 2 {
            dirtPatch(x: 100, y: 155, size: 6, opacity: 0.34)
            oval(136,128,7,4,color(0x98728c).opacity(0.38))
        }
        if condition.stage >= 3 {
            dirtPatch(x: 52, y: 95, size: 7, opacity: 0.4)
            line([(117,132),(122,137)],nil,color(0xa76c62).opacity(0.7),width: 1.8)
            line([(122,130),(127,135)],nil,color(0xa76c62).opacity(0.7),width: 1.8)
        }
        let body = context
        rotate(wing,at: CGPoint(x: 77,y: 115))
        shadedOval(CGRect(x: 46,y: 104,width: 59,height: 43),feather,shade)
        if condition.stage >= 2 { dirtPatch(x: 72, y: 118, size: 7, opacity: 0.32) }
        if condition.stage >= 4 {
            oval(85,132,8,5,color(0x98728c).opacity(0.42))
            line([(81,128),(86,134),(90,129)],nil,color(0x98665e).opacity(0.65),width: 1.6)
        }
        line([(59,124),(68,133),(81,136)],nil,color(0xb88a3d),width: 2)
        line([(57,132),(66,140)],nil,color(0xb88a3d),width: 2); context = body
        rotate(look,at: CGPoint(x: 116,y: 102))
        if grown {
            oval(106,42,9.5,16.5,color(0xbd452e)); oval(120,37,10,18.5,color(0xc84b31)); oval(134,43,9,15,color(0xbd452e)); oval(148,101,8,13.5,color(0xbd452e))
        } else { line([(97,56),(91,37),(107,44),(113,32),(123,55)],feather,outline) }
        shadedOval(CGRect(x: 81,y: 43,width: 80,height: 76),feather,shade)
        oval(111,62,16,8,color(0xfff4ba).opacity(0.33)); oval(148.5,75,3.5,6*blink,outline)
        line([(142,84),(177,90),(148,101)],orange,outline)
        line([(150,92),(171,91)],nil,color(0xa96a35),width: 1.5)
        oval(124.5,77,5.5,8*blink,outline)
        if blink > 0.3 { oval(123,74,2,2.5*blink,color(0xfff9e8)) }
        oval(118,93,9,5,color(0xef9e42))
        if condition.stage >= 3 { dirtPatch(x: 99, y: 88, size: 5, opacity: 0.3) }
        if condition.stage >= 4 {
            oval(133,91,6,3.5,color(0x98728c).opacity(0.38))
            line([(100,65),(104,69)],nil,color(0xa76c62).opacity(0.65),width: 1.6)
            line([(104,63),(108,67)],nil,color(0xa76c62).opacity(0.65),width: 1.6)
        }
        accessories(hat: hat, glasses: glasses); context = saved
    }
    // Overlapping soft marks keep dirt local and leave the feather color visible.
    private func dirtPatch(x: Double, y: Double, size: Double, opacity: Double) {
        let dirt = color(0x685342).opacity(opacity)
        oval(x,y,size,size * 0.58,dirt)
        oval(x-size * 0.55,y-size * 0.35,size * 0.52,size * 0.45,dirt)
        oval(x+size * 0.62,y+size * 0.18,size * 0.45,size * 0.32,dirt)
        oval(x+size * 0.85,y-size * 0.62,size * 0.16,size * 0.14,dirt)
    }
    mutating func accessories(hat: String, glasses: String) {
        if hat == "crown" {
            line([(83,47),(82,10),(102,26),(119,-1),(138,26),(156,10),(152,47)],color(0xffcb3f),outline)
            for x in [97.0,119,140] { oval(x,37,4,5,color(0xf47757)) }
        } else if hat == "wizard" {
            line([(85,49),(114,-42),(150,49)],color(0x6153a6),outline)
            oval(117,50,46,8,color(0x7967ba))
            context.draw(Text("✦").font(.system(size: 24)).foregroundColor(color(0xffdf7c)),at: CGPoint(x: 113,y: 12))
        } else if hat == "flower" {
            shadedOval(CGRect(x: 86,y: 5,width: 68,height: 48),color(0xffe7ac),color(0xd5ad68))
            oval(118,49,49,9,color(0xf2d491),stroke: true)
            for i in 0..<5 { let a = Double(i)*2*Double.pi/5; oval(145+cos(a)*7,34+sin(a)*7,5,5,.white) }
            oval(145,34,4,4,color(0xffbb35))
        } else if hat == "party" {
            line([(85,51),(118,-17),(151,51)],color(0xb777df),outline)
            line([(97,27),(139,27),(145,40),(91,40)],color(0xffca57),nil)
            oval(118,-17,7,7,color(0xff7097)); oval(114,12,4,4,color(0x73f3db))
            oval(118,51,34,5,color(0xf095d6))
        } else if hat == "yankees" {
            shadedOval(CGRect(x: 82,y: 15,width: 77,height: 43),color(0x233b64),color(0x0b1933))
            oval(137,53,40,7,color(0x132743))
            context.draw(Text("NY").font(.system(size: 22, weight: .black, design: .serif)).foregroundColor(.white), at: CGPoint(x: 122,y: 35))
        }
        if glasses == "round" || glasses == "rose" {
            let tint = color(glasses == "rose" ? 0xc65d83 : 0x805433)
            line([(99,72),(165,72)],nil,tint,width: 3)
            for x in [118.0,149] {
                let lens = Path(ellipseIn: CGRect(x: x-12,y: 62,width: 24,height: 26))
                context.fill(lens,with: .color(color(glasses == "rose" ? 0xffa5c6 : 0xb5e4e7).opacity(0.7)))
                context.stroke(lens,with: .color(tint),lineWidth: 3)
            }
        } else if glasses == "thug" {
            line([(100,68),(163,68)],nil,color(0x11131d),width: 5)
            line([(106,68),(132,68),(132,81),(127,87),(111,87),(106,82)],color(0x121521),nil)
            line([(139,68),(161,68),(161,82),(156,87),(143,85)],color(0x121521),nil)
            for i in 0..<3 { line([(111+Double(i)*5,73),(114+Double(i)*5,73)],nil,.white.opacity(0.8),width: 2) }
            line([(144,73),(153,73)],nil,.white.opacity(0.8),width: 2)
        } else if glasses == "2026" {
            line([(99,75),(162,75)],nil,color(0xcd5eaa),width: 3)
            context.draw(Text("2026").font(.system(size: 26, weight: .black, design: .rounded)).foregroundColor(color(0xe64b96)), at: CGPoint(x: 130,y: 75))
            oval(122,74,4,6,color(0x292549)); oval(155,78,3,4,color(0x292549))
            oval(122,73,1.2,2,.white); oval(155,77,1,1.5,.white)
        }
    }

}
