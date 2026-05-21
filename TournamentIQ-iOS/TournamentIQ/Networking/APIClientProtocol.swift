import Foundation

struct APIRequest {
    enum Method: String { case get = "GET", post = "POST", put = "PUT", delete = "DELETE" }

    var method: Method
    var path: String
    var query: [URLQueryItem]
    var body: Data?
    var contentType: String?
    var timeout: TimeInterval
    var requiresAuth: Bool

    init(
        method: Method = .get,
        path: String,
        query: [URLQueryItem] = [],
        body: Data? = nil,
        contentType: String? = nil,
        timeout: TimeInterval = 30,
        requiresAuth: Bool = true
    ) {
        self.method = method
        self.path = path
        self.query = query
        self.body = body
        self.contentType = contentType
        self.timeout = timeout
        self.requiresAuth = requiresAuth
    }
}

protocol APIClientProtocol: AnyObject {
    var baseURL: URL { get }
    func send<T: Decodable>(_ request: APIRequest, as: T.Type) async throws -> T
    func send(_ request: APIRequest) async throws
}

extension APIClientProtocol {
    func get<T: Decodable>(_ path: String, query: [URLQueryItem] = [], as type: T.Type) async throws -> T {
        try await send(APIRequest(method: .get, path: path, query: query), as: type)
    }
}
