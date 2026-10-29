import SwiftUI

/// Palette/font dùng chung trong design/tokens.json.
enum VFTheme {
    static let background = Color(red: 0xFB / 255, green: 0xF6 / 255, blue: 0xEE / 255)
    static let surface = Color.white
    static let ink = Color(red: 0x1F / 255, green: 0x24 / 255, blue: 0x30 / 255)
    static let muted = Color(red: 0x6B / 255, green: 0x72 / 255, blue: 0x80 / 255)
    static let accent = Color(red: 0xC6 / 255, green: 0x28 / 255, blue: 0x1E / 255)
    static let accentDark = Color(red: 0x99 / 255, green: 0x1B / 255, blue: 0x1B / 255)
    static let border = Color(red: 0xE8 / 255, green: 0xDD / 255, blue: 0xD0 / 255)
    static let soft = Color(red: 0xFB / 255, green: 0xF0 / 255, blue: 0xEC / 255)
    static let success = Color(red: 0x15 / 255, green: 0x80 / 255, blue: 0x3D / 255)
    static let warning = Color(red: 0xB4 / 255, green: 0x53 / 255, blue: 0x09 / 255)
    static let error = Color(red: 0xB9 / 255, green: 0x1C / 255, blue: 0x1C / 255)

    static let fontName = "BeVietnamPro-Regular"

    static func font(_ size: CGFloat) -> Font {
        .custom(fontName, size: size)
    }

    static let body = font(15)
    static let caption = font(12)
    static let title = font(28)
    static let section = font(17)
}
