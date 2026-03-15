import Foundation

enum MobileBenchmarkUploader {
    static func makeRequest(
        endpoint: URL,
        apiToken: String?,
        idempotencyKey: String?,
        runId: String,
        deviceProfile: String,
        expectedPlatform: String,
        benchmarkPayload: [String: Any],
        batch: Bool = false
    ) throws -> URLRequest {
        let body: [String: Any]
        if batch {
            body = [
                "uploads": [[
                    "run_id": runId,
                    "device_profile": deviceProfile,
                    "expected_platform": expectedPlatform,
                    "benchmark_result": benchmarkPayload,
                ]],
            ]
        } else {
            body = [
                "run_id": runId,
                "device_profile": deviceProfile,
                "expected_platform": expectedPlatform,
                "benchmark_result": benchmarkPayload,
            ]
        }
        let data = try JSONSerialization.data(withJSONObject: body, options: [.prettyPrinted, .sortedKeys])
        let target: URL
        if batch, endpoint.absoluteString.hasSuffix(":ingest"), let url = URL(string: endpoint.absoluteString.replacingOccurrences(of: ":ingest", with: ":ingest-batch")) {
            target = url
        } else {
            target = endpoint
        }
        var request = URLRequest(url: target)
        request.httpMethod = "POST"
        request.httpBody = data
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let apiToken {
            request.setValue(apiToken, forHTTPHeaderField: "X-API-Token")
        }
        if let idempotencyKey {
            request.setValue(idempotencyKey, forHTTPHeaderField: "X-Idempotency-Key")
        }
        return request
    }
}
