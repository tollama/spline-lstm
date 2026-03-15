import CryptoKit
import Foundation

enum ModelChecksumVerifier {
    static func sha256(url: URL) throws -> String {
        let data = try Data(contentsOf: url)
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    static func verify(url: URL, expectedSha256: String) throws -> Bool {
        return try sha256(url: url).caseInsensitiveCompare(expectedSha256) == .orderedSame
    }
}
