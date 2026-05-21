import Foundation

enum DateFormatting {
    private static let monthDay: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "MMM d"
        return f
    }()

    private static let monthDayYear: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale.autoupdatingCurrent
        f.dateStyle = .medium
        f.timeStyle = .none
        return f
    }()

    static func dateRange(_ start: Date?, _ end: Date?) -> String {
        switch (start, end) {
        case (nil, nil): return "Dates TBD"
        case (let s?, nil): return monthDayYear.string(from: s)
        case (nil, let e?): return "Ends " + monthDayYear.string(from: e)
        case (let s?, let e?):
            let calendar = Calendar(identifier: .gregorian)
            if calendar.isDate(s, inSameDayAs: e) {
                return monthDayYear.string(from: s)
            }
            if calendar.component(.year, from: s) == calendar.component(.year, from: e) {
                return "\(monthDay.string(from: s)) – \(monthDay.string(from: e)), \(calendar.component(.year, from: e))"
            }
            return "\(monthDayYear.string(from: s)) – \(monthDayYear.string(from: e))"
        }
    }

    static func relativeUpdated(_ date: Date?) -> String? {
        guard let date else { return nil }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}
