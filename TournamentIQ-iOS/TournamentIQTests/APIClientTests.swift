import XCTest
@testable import TournamentIQ

final class APIClientTests: XCTestCase {
    private var session: URLSession!

    override func setUp() {
        super.setUp()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        session = URLSession(configuration: config)
        StubURLProtocol.reset()
    }

    override func tearDown() {
        StubURLProtocol.reset()
        session = nil
        super.tearDown()
    }

    func testGetAttachesBearerHeader() async throws {
        StubURLProtocol.register(path: "/api/v1/me") { request in
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer test-token")
            let body = #"{"team":{"id":"t1","slug":"slug","display_name":"Display"}}"#
            return (200, Data(body.utf8))
        }

        let client = makeClient(token: "test-token")
        let response = try await client.send(APIRequest(method: .get, path: "/api/v1/me"), as: MeResponse.self)
        XCTAssertEqual(response.team.slug, "slug")
    }

    func testUnauthorizedTriggersCallbackAndThrows() async {
        StubURLProtocol.register(path: "/api/v1/me") { _ in
            let body = #"{"error":{"code":"invalid_session","message":"nope"}}"#
            return (401, Data(body.utf8))
        }

        let counter = CallCounter()
        let client = makeClient(token: "stale-token") {
            await counter.increment()
        }

        do {
            _ = try await client.send(APIRequest(method: .get, path: "/api/v1/me"), as: MeResponse.self)
            XCTFail("Expected unauthorized error")
        } catch APIError.unauthorized {
            let count = await counter.value
            XCTAssertEqual(count, 1)
        } catch {
            XCTFail("Wrong error: \(error)")
        }
    }

    func testServerErrorDecodesEnvelope() async {
        StubURLProtocol.register(path: "/api/v1/me") { _ in
            let body = #"{"error":{"code":"bad_request","message":"missing field"}}"#
            return (400, Data(body.utf8))
        }

        let client = makeClient(token: "t")
        do {
            _ = try await client.send(APIRequest(method: .get, path: "/api/v1/me"), as: MeResponse.self)
            XCTFail("Expected http error")
        } catch APIError.http(let status, let code, let message) {
            XCTAssertEqual(status, 400)
            XCTAssertEqual(code, "bad_request")
            XCTAssertEqual(message, "missing field")
        } catch {
            XCTFail("Wrong error: \(error)")
        }
    }

    func testUnauthenticatedRequestSkipsAuthHeader() async throws {
        StubURLProtocol.register(path: "/api/v1/login") { request in
            XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
            let body = #"{"team":{"id":"t1","slug":"slug","display_name":"Display"},"session":{"token":"abc","expires_at":null}}"#
            return (200, Data(body.utf8))
        }

        let client = makeClient(token: "should-not-be-attached")
        let payload = try JSONSerialization.data(withJSONObject: ["team_slug": "slug", "password": "pw"])
        let response = try await client.send(
            APIRequest(method: .post, path: "/api/v1/login", body: payload, contentType: "application/json", requiresAuth: false),
            as: LoginResponse.self
        )
        XCTAssertEqual(response.session.token, "abc")
    }

    // MARK: - Helpers

    private func makeClient(
        token: String?,
        onUnauthorized: @escaping @Sendable () async -> Void = {}
    ) -> APIClient {
        APIClient(
            baseURL: URL(string: "https://example.test")!,
            session: session,
            tokenProvider: { token },
            onUnauthorized: onUnauthorized
        )
    }
}

private actor CallCounter {
    private(set) var value = 0
    func increment() { value += 1 }
}

private final class StubURLProtocol: URLProtocol {
    typealias Responder = (URLRequest) -> (Int, Data)
    private static var responders: [String: Responder] = [:]

    static func reset() { responders = [:] }
    static func register(path: String, responder: @escaping Responder) {
        responders[path] = responder
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let url = request.url else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
            return
        }
        let responder = Self.responders[url.path] ?? { _ in (404, Data()) }
        let (status, body) = responder(request)
        let response = HTTPURLResponse(
            url: url,
            statusCode: status,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
