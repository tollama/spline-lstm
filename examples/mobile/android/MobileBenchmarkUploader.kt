package ai.tollama.splineforecast.mobile

import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object MobileBenchmarkUploader {
    private const val HMAC_ALGORITHM = "HmacSHA256"

    fun upload(
        endpoint: String,
        apiToken: String?,
        idempotencyKey: String?,
        runId: String,
        deviceProfile: String,
        expectedPlatform: String,
        benchmarkPayloadJson: String,
        signingSecret: String? = null,
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
        if (!signingSecret.isNullOrBlank()) {
            val timestamp = (System.currentTimeMillis() / 1000L).toString()
            val signature = hmacSha256Hex(signingSecret, "$timestamp\n$requestJson")
            conn.setRequestProperty("X-Mobile-Timestamp", timestamp)
            conn.setRequestProperty("X-Mobile-Signature", signature)
        }

        OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(requestJson) }
        return conn.responseCode
    }

    private fun hmacSha256Hex(secret: String, message: String): String {
        val key = SecretKeySpec(secret.toByteArray(Charsets.UTF_8), HMAC_ALGORITHM)
        val mac = Mac.getInstance(HMAC_ALGORITHM)
        mac.init(key)
        return mac.doFinal(message.toByteArray(Charsets.UTF_8)).joinToString("") { byte -> "%02x".format(byte) }
    }
}
