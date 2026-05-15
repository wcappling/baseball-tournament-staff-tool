import Foundation
import XCTest

enum FixtureLoader {
    static func data(_ name: String, file: StaticString = #filePath, line: UInt = #line) throws -> Data {
        guard let url = Bundle(for: BundleSentinel.self).url(forResource: name, withExtension: "json")
            ?? Bundle(for: BundleSentinel.self).url(forResource: name, withExtension: "json", subdirectory: "Fixtures")
        else {
            XCTFail("Missing fixture: \(name).json", file: file, line: line)
            throw CocoaError(.fileNoSuchFile)
        }
        return try Data(contentsOf: url)
    }
}

private final class BundleSentinel {}
