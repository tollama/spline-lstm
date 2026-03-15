import Foundation

struct PendingMobileBenchmarkUpload: Codable {
    let queueId: String
    let runId: String
    let deviceProfile: String
    let expectedPlatform: String
    let benchmarkPayload: [String: AnyCodable]
    let idempotencyKey: String
    let createdAt: Date
    let lastAttemptAt: Date?
    let nextAttemptAt: Date
    let attemptCount: Int

    init(
        queueId: String = UUID().uuidString,
        runId: String,
        deviceProfile: String,
        expectedPlatform: String,
        benchmarkPayload: [String: Any],
        idempotencyKey: String,
        createdAt: Date = Date(),
        lastAttemptAt: Date? = nil,
        nextAttemptAt: Date = Date(),
        attemptCount: Int = 0
    ) {
        self.queueId = queueId
        self.runId = runId
        self.deviceProfile = deviceProfile
        self.expectedPlatform = expectedPlatform
        self.benchmarkPayload = benchmarkPayload.mapValues(AnyCodable.init)
        self.idempotencyKey = idempotencyKey
        self.createdAt = createdAt
        self.lastAttemptAt = lastAttemptAt
        self.nextAttemptAt = nextAttemptAt
        self.attemptCount = attemptCount
    }
}

final class MobileBenchmarkQueueStore {
    private let queueURL: URL
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(fileManager: FileManager = .default) throws {
        let baseURL = try fileManager.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        queueURL = baseURL.appendingPathComponent("mobile-benchmark-queue.json")
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
    }

    func listReady(now: Date = Date()) throws -> [PendingMobileBenchmarkUpload] {
        try loadAll()
            .filter { $0.nextAttemptAt <= now }
            .sorted { $0.createdAt < $1.createdAt }
    }

    func enqueue(_ item: PendingMobileBenchmarkUpload) throws {
        var items = try loadAll()
        items.append(item)
        try persist(items)
    }

    func remove(queueId: String) throws {
        try persist(loadAll().filter { $0.queueId != queueId })
    }

    func reschedule(queueId: String, now: Date = Date()) throws {
        let items = try loadAll().map { item -> PendingMobileBenchmarkUpload in
            guard item.queueId == queueId else { return item }
            let nextAttempt = now.addingTimeInterval(computeBackoffSeconds(attemptCount: item.attemptCount + 1))
            return PendingMobileBenchmarkUpload(
                queueId: item.queueId,
                runId: item.runId,
                deviceProfile: item.deviceProfile,
                expectedPlatform: item.expectedPlatform,
                benchmarkPayload: item.benchmarkPayload.mapValues(\.value),
                idempotencyKey: item.idempotencyKey,
                createdAt: item.createdAt,
                lastAttemptAt: now,
                nextAttemptAt: nextAttempt,
                attemptCount: item.attemptCount + 1
            )
        }
        try persist(items)
    }

    private func loadAll() throws -> [PendingMobileBenchmarkUpload] {
        guard FileManager.default.fileExists(atPath: queueURL.path) else {
            return []
        }
        let data = try Data(contentsOf: queueURL)
        guard !data.isEmpty else {
            return []
        }
        return try decoder.decode([PendingMobileBenchmarkUpload].self, from: data)
    }

    private func persist(_ items: [PendingMobileBenchmarkUpload]) throws {
        let data = try encoder.encode(items)
        try data.write(to: queueURL, options: .atomic)
    }

    private func computeBackoffSeconds(attemptCount: Int) -> TimeInterval {
        let cappedAttempt = min(max(attemptCount, 1), 6)
        return 15.0 * pow(2.0, Double(cappedAttempt - 1))
    }
}

struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let intValue = try? container.decode(Int.self) {
            value = intValue
        } else if let doubleValue = try? container.decode(Double.self) {
            value = doubleValue
        } else if let boolValue = try? container.decode(Bool.self) {
            value = boolValue
        } else if let stringValue = try? container.decode(String.self) {
            value = stringValue
        } else if let dictValue = try? container.decode([String: AnyCodable].self) {
            value = dictValue.mapValues(\.value)
        } else if let arrayValue = try? container.decode([AnyCodable].self) {
            value = arrayValue.map(\.value)
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let intValue as Int:
            try container.encode(intValue)
        case let doubleValue as Double:
            try container.encode(doubleValue)
        case let boolValue as Bool:
            try container.encode(boolValue)
        case let stringValue as String:
            try container.encode(stringValue)
        case let dictValue as [String: Any]:
            try container.encode(dictValue.mapValues(AnyCodable.init))
        case let arrayValue as [Any]:
            try container.encode(arrayValue.map(AnyCodable.init))
        default:
            try container.encodeNil()
        }
    }
}
