package ai.tollama.splineforecast.mobile

class MobileBenchmarkReplayWorker(
    private val queueStore: MobileBenchmarkQueueStore,
    private val endpoint: String,
    private val apiToken: String?,
) {
    fun flushReadyUploads() {
        queueStore.listReady().forEach { item ->
            val responseCode = MobileBenchmarkUploader.upload(
                endpoint = endpoint,
                apiToken = apiToken,
                idempotencyKey = item.idempotencyKey,
                runId = item.runId,
                deviceProfile = item.deviceProfile,
                expectedPlatform = item.expectedPlatform,
                benchmarkPayloadJson = item.benchmarkPayloadJson,
            )

            when {
                responseCode in 200..299 -> queueStore.remove(item.queueId)
                responseCode in listOf(408, 425, 429) || responseCode >= 500 -> queueStore.reschedule(item.queueId)
                else -> queueStore.remove(item.queueId)
            }
        }
    }
}
