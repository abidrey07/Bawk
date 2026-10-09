import Foundation
for _ in 0..<8 {
    let route = MeadowRoute()
    var previous = route.pose(at: 0)
    var seen = Set<String>()
    for i in 1...Int(route.duration * 40) {
        let pose = route.pose(at: Double(i) / 20)
        precondition(pose.position.x.isFinite && pose.position.y.isFinite)
        precondition((240...495).contains(pose.position.x))
        precondition((280...303).contains(pose.position.y))
        precondition(abs(pose.position.x-previous.position.x) < 5)
        precondition(abs(pose.position.y-previous.position.y) < 1)
        precondition(abs(pose.direction-previous.direction) < 0.6)
        if pose.action != .walk { precondition(pose.leg == 0 && pose.bounce == 0) }
        seen.insert(String(describing: pose.action)); previous = pose
    }
    precondition(seen.count == 4)
    for i in 1..<route.segments.count {
        let a = route.segments[i-1], b = route.segments[i]
        precondition(a.to.x == b.from.x && a.to.y == b.from.y)
        precondition(a.action == .walk || b.action == .walk)
    }
}
print("PASS: 8 randomized itineraries, two cycles each; all actions, continuous movement and turns, platform bounds, planted feet during pauses.")
