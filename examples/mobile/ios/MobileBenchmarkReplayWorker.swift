import Foundation

final class MobileBenchmarkReplayWorker {
    private let queueStore: MobileBenchmarkQueueStore
    private let endpoint: URL
    private let apiToken: String?
    private let signingSecret: String?
    private let urlSession: URLSession

    init(
        queueStore: MobileBenchmarkQueueStore,
        endpoint: URL,
        apiToken: String?,
        signingSecret: String? = nil,
        urlSession: URLSession = .shared
    ) {
        self.queueStore = queueStore
        self.endpoint = endpoint
        self.apiToken = apiToken
        self.signingSecret = signingSecret
        self.urlSession = urlSession
    }

    func flushReadyUploads() async {
        guard let items = try? queueStore.listReady() else { return }
        for item in items {
            do {
                let request = try MobileBenchmarkUploader.makeRequest(
                    endpoint: endpoint,
                    apiToken: apiToken,
                    idempotencyKey: item.idempotencyKey,
                    runId: item.runId,
                    deviceProfile: item.deviceProfile,
                    expectedPlatform: item.expectedPlatform,
                    benchmarkPayload: item.benchmarkPayload.mapValues(\.value),
                    signingSecret: signingSecret
                )
                let (_, response) = try await urlSession.data(for: request)
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
                switch statusCode {
                case 200 ..< 300:
                    try queueStore.remove(queueId: item.queueId)
                case 408, 425, 429, 500 ... 599:
                    try queueStore.reschedule(queueId: item.queueId)
                default:
                    try queueStore.remove(queueId: item.queueId)
                }
            } catch {
                try? queueStore.reschedule(queueId: item.queueId)
            }
        }
    }
}
