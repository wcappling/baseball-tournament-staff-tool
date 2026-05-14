import Foundation
import os

final class APIClient: APIClientProtocol {
    let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let tokenProvider: @Sendable () async -> String?
    private let onUnauthorized: @Sendable () async -> Void
    private let log = Logger(subsystem: "com.tournamentiq.ios", category: "network")

    init(
        baseURL: URL,
        session: URLSession? = nil,
        decoder: JSONDecoder = DecodingStrategies.makeDecoder(),
        tokenProvider: @escaping @Sendable () async -> String?,
        onUnauthorized: @escaping @Sendable () async -> Void
    ) {
        self.baseURL = baseURL
        self.session = session ?? APIClient.makeDefaultSession()
        self.decoder = decoder
        self.tokenProvider = tokenProvider
        self.onUnauthorized = onUnauthorized
    }

    static func makeDefaultSession() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.httpShouldSetCookies = false
        config.httpCookieAcceptPolicy = .never
        config.httpAdditionalHeaders = ["Accept": "application/json"]
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        return URLSession(configuration: config)
    }

    func send<T: Decodable>(_ request: APIRequest, as type: T.Type) async throws -> T {
        let data = try await performRequest(request)
        if data.isEmpty, let empty = EmptyResponse() as? T {
            return empty
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            log.error("Decoding failed for \(request.path, privacy: .public): \(String(describing: error), privacy: .public)")
            throw APIError.decoding(String(describing: error))
        }
    }

    func send(_ request: APIRequest) async throws {
        _ = try await performRequest(request)
    }

    private func performRequest(_ request: APIRequest) async throws -> Data {
        let urlRequest = try await buildURLRequest(request)
        do {
            let (data, response) = try await session.data(for: urlRequest)
            guard let http = response as? HTTPURLResponse else {
                throw APIError.http(status: -1, code: nil, message: "Invalid response")
            }
            if http.statusCode == 401 {
                await onUnauthorized()
                throw APIError.unauthorized
            }
            if (200..<300).contains(http.statusCode) {
                return data
            }
            let envelope = try? decoder.decode(APIErrorEnvelope.self, from: data)
            throw APIError.http(
                status: http.statusCode,
                code: envelope?.error.code,
                message: envelope?.error.message
            )
        } catch let error as APIError {
            throw error
        } catch let urlError as URLError where urlError.code == .cancelled {
            throw APIError.cancelled
        } catch let urlError as URLError {
            throw APIError.transport(urlError)
        }
    }

    private func buildURLRequest(_ request: APIRequest) async throws -> URLRequest {
        guard var components = URLComponents(url: baseURL.appendingPathComponent(request.path), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        if !request.query.isEmpty {
            components.queryItems = request.query
        }
        guard let url = components.url else { throw APIError.invalidURL }

        var urlRequest = URLRequest(url: url, timeoutInterval: request.timeout)
        urlRequest.httpMethod = request.method.rawValue
        urlRequest.httpBody = request.body
        if let contentType = request.contentType {
            urlRequest.setValue(contentType, forHTTPHeaderField: "Content-Type")
        }
        if request.requiresAuth, let token = await tokenProvider() {
            urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return urlRequest
    }
}

struct EmptyResponse: Decodable {}
