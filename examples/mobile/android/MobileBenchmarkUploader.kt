package ai.tollama.splineforecast.mobile

import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object MobileBenchmarkUploader {
    fun upload(
        endpoint: String,
        apiToken: String?,
        idempotencyKey: String?,
        runId: String,
        deviceProfile: String,
        expectedPlatform: String,
        benchmarkPayloadJson: String,
        batch: Boolean = false,
    ): Int {
        val requestJson = if (batch) {
            """
                {
                  "uploads": [
                    {
                      "run_id": "$runId",
                      "device_profile": "$deviceProfile",
                      "expected_platform": "$expectedPlatform",
                      "benchmark_result": $benchmarkPayloadJson
                    }
                  ]
                }
            """.trimIndent()
        } else {
            """
                {
                  "run_id": "$runId",
                  "device_profile": "$deviceProfile",
                  "expected_platform": "$expectedPlatform",
                  "benchmark_result": $benchmarkPayloadJson
                }
            """.trimIndent()
        }

        val target = if (batch && endpoint.endsWith(":ingest")) {
            endpoint.removeSuffix(":ingest") + ":ingest-batch"
        } else {
            endpoint
        }
        val conn = URL(target).openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "application/json")
        apiToken?.let { conn.setRequestProperty("X-API-Token", it) }
        idempotencyKey?.let { conn.setRequestProperty("X-Idempotency-Key", it) }

        OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(requestJson) }
        return conn.responseCode
    }
}
