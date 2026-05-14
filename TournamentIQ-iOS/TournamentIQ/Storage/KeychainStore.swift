import Foundation
import Security

protocol KeychainStoring: Sendable {
    func saveSession(_ session: SessionToken, teamSlug: String) throws
    func loadSession() throws -> StoredSession?
    func clear() throws
}

struct StoredSession: Equatable {
    let token: String
    let expiresAt: Date?
    let teamSlug: String
}

struct KeychainStore: KeychainStoring {
    enum Error: Swift.Error, Equatable {
        case unexpectedStatus(OSStatus)
        case encoding
    }

    private let service: String
    private let account: String

    init(service: String = "com.tournamentiq.ios", account: String = "session") {
        self.service = service
        self.account = account
    }

    func saveSession(_ session: SessionToken, teamSlug: String) throws {
        let payload: [String: Any] = [
            "token": session.token,
            "expires_at": session.expiresAt?.timeIntervalSince1970 as Any,
            "team_slug": teamSlug
        ]
        let data = try JSONSerialization.data(withJSONObject: payload)

        let baseQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(baseQuery as CFDictionary)

        var addQuery = baseQuery
        addQuery[kSecValueData as String] = data
        addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock

        let status = SecItemAdd(addQuery as CFDictionary, nil)
        guard status == errSecSuccess else { throw Error.unexpectedStatus(status) }
    }

    func loadSession() throws -> StoredSession? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = item as? Data else {
            throw Error.unexpectedStatus(status)
        }
        guard
            let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            let token = payload["token"] as? String,
            let slug = payload["team_slug"] as? String
        else {
            throw Error.encoding
        }
        let expiresAt: Date?
        if let raw = payload["expires_at"] as? TimeInterval {
            expiresAt = Date(timeIntervalSince1970: raw)
        } else {
            expiresAt = nil
        }
        return StoredSession(token: token, expiresAt: expiresAt, teamSlug: slug)
    }

    func clear() throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw Error.unexpectedStatus(status)
        }
    }
}
