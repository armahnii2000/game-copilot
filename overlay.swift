import AppKit

// Text overlay bar for DuckStation help — v3.
// Reads ~/duckstation-help-overlay.txt every 0.5 s (line 1 = heading, rest = body).
// DuckStation is a closed app with no plugin API, so the bar is a separate
// borderless window that sits over the game. v3 fixes the "shows all the
// time" problem: the bar is VISIBLE ONLY while DuckStation is the frontmost
// app, it follows the DuckStation window, and it hides the moment the player
// switches to anything else.
// Usage: overlay [seconds-to-live]

let args = CommandLine.arguments
let ttl = args.count > 1 ? Double(args[1]) ?? 0 : 0
let msgPath = (NSHomeDirectory() as NSString).appendingPathComponent("duckstation-help-overlay.txt")
let duckBundle = "com.github.stenzek.duckstation"

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let W: CGFloat = 880, H: CGFloat = 64
let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: W, height: H),
                      styleMask: [.borderless], backing: .buffered, defer: false)
window.level = .screenSaver
window.collectionBehavior = [.canJoinAllSpaces]
window.isOpaque = false
window.backgroundColor = NSColor(calibratedRed: 0.06, green: 0.08, blue: 0.10, alpha: 0.92)
window.hasShadow = true
window.ignoresMouseEvents = true

let heading = NSTextField(labelWithString: "")
heading.frame = NSRect(x: 14, y: H - 30, width: W - 28, height: 22)
heading.font = NSFont.boldSystemFont(ofSize: 15)
heading.textColor = NSColor(calibratedRed: 1.0, green: 0.78, blue: 0.25, alpha: 1)
heading.lineBreakMode = .byTruncatingTail

let body = NSTextField(labelWithString: "")
body.frame = NSRect(x: 14, y: 8, width: W - 28, height: 22)
body.font = NSFont.systemFont(ofSize: 14)
body.textColor = .white
body.lineBreakMode = .byTruncatingTail

window.contentView?.addSubview(heading)
window.contentView?.addSubview(body)

func duckStationFrame() -> NSRect? {
    guard let infos = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] else { return nil }
    for w in infos {
        if let owner = w[kCGWindowOwnerName as String] as? String, owner == "DuckStation",
           let b = w[kCGWindowBounds as String] as? [String: CGFloat],
           let x = b["X"], let y = b["Y"], let width = b["Width"], width > 200 {
            guard let main = NSScreen.main else { return nil }
            // CG bounds are top-left origin; AppKit is bottom-left.
            return NSRect(x: x + (width - W) / 2, y: main.frame.height - y - 6 - H, width: W, height: H)
        }
    }
    return nil
}

func refresh() {
    // Text
    let text = (try? String(contentsOfFile: msgPath, encoding: .utf8)) ?? ""
    let lines = text.components(separatedBy: "\n")
    heading.stringValue = lines.first ?? ""
    body.stringValue = lines.dropFirst().joined(separator: " ")
    // Visibility: only while DuckStation is the app the player is using.
    let front = NSWorkspace.shared.frontmostApplication
    if let front = front, front.bundleIdentifier == duckBundle {
        if let f = duckStationFrame() {
            if window.frame.origin != f.origin {
                window.setFrameOrigin(f.origin)
            }
        }
        if !window.isVisible {
            window.orderFrontRegardless()
        }
    } else if front != nil {
        if window.isVisible {
            window.orderOut(nil)
        }
    }
}
refresh()
Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in refresh() }
if ttl > 0 {
    Timer.scheduledTimer(withTimeInterval: ttl, repeats: false) { _ in NSApp.terminate(nil) }
}
app.run()
