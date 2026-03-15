import Foundation

enum MobileBenchmarkUploader {
    static func makeRequest(
        endpoint: URL,
        apiToken: String?,
        runId: String,
        deviceProfile: String,
        expectedPlatform: String,
        benchmarkPayload: [String: Any]
    ) throws -> URLRequest {
        let body: [String: Any] = [
            "run_id": runId,
            "device_profile": deviceProfile,
            "expected_platform": expectedPlatform,
            "benchmark_result": benchmarkPayload,
        ]
        let data = try JSONSerialization.data(withJSONObject: body, options: [.prettyPrinted, .sortedKeys])
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.httpBody = data
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let apiToken {
            request.setValue(apiToken, forHTTPHeaderField: "X-API-Token")
        }
        return request
    }
}
