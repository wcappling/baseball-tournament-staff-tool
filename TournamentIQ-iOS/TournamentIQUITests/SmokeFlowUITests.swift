import XCTest

/// Smoke test against a real backend. Requires `TIQ_TEST_TEAM_SLUG` and
/// `TIQ_TEST_TEAM_PASSWORD` env vars on the test scheme; skipped otherwise.
final class SmokeFlowUITests: XCTestCase {
    func testLoginAndTabNavigation() throws {
        let env = ProcessInfo.processInfo.environment
        guard
            let slug = env["TIQ_TEST_TEAM_SLUG"], !slug.isEmpty,
            let password = env["TIQ_TEST_TEAM_PASSWORD"], !password.isEmpty
        else {
            throw XCTSkip("Set TIQ_TEST_TEAM_SLUG and TIQ_TEST_TEAM_PASSWORD on the UI test scheme.")
        }

        let app = XCUIApplication()
        app.launchEnvironment = env
        app.launch()

        let teamField = app.textFields["Team code"]
        XCTAssertTrue(teamField.waitForExistence(timeout: 5), "Login form should appear")
        teamField.tap()
        teamField.typeText(slug)

        let passwordField = app.secureTextFields["Password"]
        passwordField.tap()
        passwordField.typeText(password)

        app.buttons["Sign In"].tap()

        XCTAssertTrue(app.tabBars.buttons["Tournaments"].waitForExistence(timeout: 10))

        app.tabBars.buttons["Upcoming"].tap()
        XCTAssertTrue(app.navigationBars["Upcoming"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Teams"].tap()
        XCTAssertTrue(app.navigationBars["Teams"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Changes"].tap()
        XCTAssertTrue(app.navigationBars["Changes"].waitForExistence(timeout: 5))

        app.tabBars.buttons["Settings"].tap()
        XCTAssertTrue(app.navigationBars["Settings"].waitForExistence(timeout: 5))
    }
}
