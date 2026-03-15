package ai.tollama.splineforecast.mobile

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

data class PendingMobileBenchmarkUpload(
    val queueId: String = UUID.randomUUID().toString(),
    val runId: String,
    val deviceProfile: String,
    val expectedPlatform: String,
    val benchmarkPayloadJson: String,
    val idempotencyKey: String,
    val createdAtMillis: Long = System.currentTimeMillis(),
    val lastAttemptAtMillis: Long? = null,
    val nextAttemptAtMillis: Long = System.currentTimeMillis(),
    val attemptCount: Int = 0,
)

class MobileBenchmarkQueueStore(
    context: Context,
    fileName: String = "mobile-benchmark-queue.json",
) {
    private val queueFile = File(context.filesDir, fileName)

    @Synchronized
    fun listReady(nowMillis: Long = System.currentTimeMillis()): List<PendingMobileBenchmarkUpload> {
        return loadAll()
            .filter { it.nextAttemptAtMillis <= nowMillis }
            .sortedBy { it.createdAtMillis }
    }

    @Synchronized
    fun enqueue(item: PendingMobileBenchmarkUpload) {
        val items = loadAll().toMutableList()
        items.add(item)
        persist(items)
    }

    @Synchronized
    fun remove(queueId: String) {
        persist(loadAll().filterNot { it.queueId == queueId })
    }

    @Synchronized
    fun reschedule(queueId: String, nowMillis: Long = System.currentTimeMillis()) {
        val items = loadAll().map { item ->
            if (item.queueId != queueId) {
                item
            } else {
                val nextAttempt = nowMillis + computeBackoffMillis(item.attemptCount + 1)
                item.copy(
                    attemptCount = item.attemptCount + 1,
                    lastAttemptAtMillis = nowMillis,
                    nextAttemptAtMillis = nextAttempt,
                )
            }
        }
        persist(items)
    }

    private fun loadAll(): List<PendingMobileBenchmarkUpload> {
        if (!queueFile.exists()) {
            return emptyList()
        }
        val raw = queueFile.readText(Charsets.UTF_8)
        if (raw.isBlank()) {
            return emptyList()
        }
        val array = JSONArray(raw)
        return buildList(array.length()) {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                add(
                    PendingMobileBenchmarkUpload(
                        queueId = item.getString("queue_id"),
                        runId = item.getString("run_id"),
                        deviceProfile = item.getString("device_profile"),
                        expectedPlatform = item.getString("expected_platform"),
                        benchmarkPayloadJson = item.getJSONObject("benchmark_result").toString(),
                        idempotencyKey = item.getString("idempotency_key"),
                        createdAtMillis = item.getLong("created_at_ms"),
                        lastAttemptAtMillis = item.optLong("last_attempt_at_ms").takeIf { item.has("last_attempt_at_ms") },
                        nextAttemptAtMillis = item.getLong("next_attempt_at_ms"),
                        attemptCount = item.getInt("attempt_count"),
                    ),
                )
            }
        }
    }

    private fun persist(items: List<PendingMobileBenchmarkUpload>) {
        val array = JSONArray()
        items.forEach { item ->
            array.put(
                JSONObject(
                    mapOf(
                        "queue_id" to item.queueId,
                        "run_id" to item.runId,
                        "device_profile" to item.deviceProfile,
                        "expected_platform" to item.expectedPlatform,
                        "benchmark_result" to JSONObject(item.benchmarkPayloadJson),
                        "idempotency_key" to item.idempotencyKey,
                        "created_at_ms" to item.createdAtMillis,
                        "last_attempt_at_ms" to item.lastAttemptAtMillis,
                        "next_attempt_at_ms" to item.nextAttemptAtMillis,
                        "attempt_count" to item.attemptCount,
                    ),
                ),
            )
        }
        queueFile.writeText(array.toString(2), Charsets.UTF_8)
    }

    private fun computeBackoffMillis(attemptCount: Int): Long {
        val cappedAttempt = attemptCount.coerceAtMost(6)
        return 15_000L * (1L shl (cappedAttempt - 1))
    }
}
