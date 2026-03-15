package ai.tollama.splineforecast.mobile

import org.json.JSONArray
import org.json.JSONObject

data class MobileAccuracy(
    val rmse: Double,
    val baselineRmse: Double,
    val rmseDegradationPct: Double,
    val mae: Double? = null,
    val wape: Double? = null,
    val maxAbsDiff: Double? = null,
    val nSamples: Int? = null,
    val perHorizonRmse: List<Double> = emptyList(),
)

data class MobileBenchmarkPayload(
    val runtimeStack: String,
    val fallbackChain: List<String>,
    val latencyP50Ms: Double,
    val latencyP95Ms: Double,
    val memoryPeakMb: Double,
    val sizeMb: Double,
    val attempts: Int,
    val failures: Int,
    val metadata: Map<String, String>,
    val accuracy: MobileAccuracy,
)

fun MobileBenchmarkPayload.toJson(): JSONObject {
    val accuracyJson = JSONObject()
        .put("rmse", accuracy.rmse)
        .put("baseline_rmse", accuracy.baselineRmse)
        .put("rmse_degradation_pct", accuracy.rmseDegradationPct)

    accuracy.mae?.let { accuracyJson.put("mae", it) }
    accuracy.wape?.let { accuracyJson.put("wape", it) }
    accuracy.maxAbsDiff?.let { accuracyJson.put("max_abs_diff", it) }
    accuracy.nSamples?.let { accuracyJson.put("n_samples", it) }
    if (accuracy.perHorizonRmse.isNotEmpty()) {
        accuracyJson.put("per_horizon_rmse", JSONArray(accuracy.perHorizonRmse))
    }

    val metadataJson = JSONObject()
    for ((key, value) in metadata) {
        metadataJson.put(key, value)
    }

    return JSONObject()
        .put("runtime_stack", runtimeStack)
        .put("fallback_chain", JSONArray(fallbackChain))
        .put("status", if (failures == 0) "succeeded" else "failed")
        .put("latency_ms", JSONObject().put("p50", latencyP50Ms).put("p95", latencyP95Ms))
        .put("memory_peak_mb", memoryPeakMb)
        .put("size_mb", sizeMb)
        .put("attempts", attempts)
        .put("failures", failures)
        .put("metadata", metadataJson)
        .put("accuracy", accuracyJson)
}
