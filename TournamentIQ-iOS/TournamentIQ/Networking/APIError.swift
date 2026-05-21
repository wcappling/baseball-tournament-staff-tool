import Foundation

enum APIError: Error, LocalizedError, Equatable {
    case unauthorized
    case transport(URLError)
    case http(status: Int, code: String?, message: String?)
    case decoding(String)
    case invalidURL
    case cancelled

    var errorDescription: String? {
        switch self {
        case .unauthorized:
            return "Your session has expired. Please sign in again."
        case .transport(let urlError):
            return urlError.localizedDescription
        case .http(_, _, let message):
            return message ?? "The server returned an error."
        case .decoding(let detail):
            return "Couldn't read the server response: \(detail)"
        case .invalidURL:
            return "The configured server URL is invalid."
        case .cancelled:
            return "Request cancelled."
        }
    }

    static func == (lhs: APIError, rhs: APIError) -> Bool {
        switch (lhs, rhs) {
        case (.unauthorized, .unauthorized), (.invalidURL, .invalidURL), (.cancelled, .cancelled):
            return true
        case (.transport(let l), .transport(let r)):
            return l.code == r.code
        case (.http(let ls, let lc, let lm), .http(let rs, let rc, let rm)):
            return ls == rs && lc == rc && lm == rm
        case (.decoding(let l), .decoding(let r)):
            return l == r
        default:
            return false
        }
    }
}

struct APIErrorEnvelope: Decodable {
    struct Body: Decodable {
        let code: String?
        let message: String?
    }
    let error: Body
}
