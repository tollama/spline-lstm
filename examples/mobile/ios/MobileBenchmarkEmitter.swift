import Foundation

struct MobileAccuracy: Codable {
    let rmse: Double
    let baseline_rmse: Double
    let rmse_degradation_pct: Double
    let mae: Double?
    let wape: Double?
    let max_abs_diff: Double?
    let n_samples: Int?
    let per_horizon_rmse: [Double]
}

struct LatencySummary: Codable {
    let p50: Double
    let p95: Double
}

struct MobileBenchmarkPayload: Codable {
    let runtime_stack: String
    let fallback_chain: [String]
    let status: String
    let latency_ms: LatencySummary
    let memory_peak_mb: Double
    let size_mb: Double
    let attempts: Int
    let failures: Int
    let metadata: [String: String]
    let accuracy: MobileAccuracy
}

enum MobileBenchmarkEmitter {
    static func encode(_ payload: MobileBenchmarkPayload) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(payload)
    }
}
