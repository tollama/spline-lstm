package ai.tollama.splineforecast.mobile

import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object MobileBenchmarkUploader {
    fun upload(
        endpoint: String,
        apiToken: String?,
        runId: String,
        deviceProfile: String,
        expectedPlatform: String,
        benchmarkPayloadJson: String,
    ): Int {
        val requestJson = """
            {
              "run_id": "$runId",
              "device_profile": "$deviceProfile",
              "expected_platform": "$expectedPlatform",
              "benchmark_result": $benchmarkPayloadJson
            }
        """.trimIndent()

        val conn = URL(endpoint).openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "application/json")
        apiToken?.let { conn.setRequestProperty("X-API-Token", it) }

        OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(requestJson) }
        return conn.responseCode
    }
}
