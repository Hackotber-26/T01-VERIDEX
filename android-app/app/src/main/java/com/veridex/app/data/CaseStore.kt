package com.veridex.app.data

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

data class Region(val left: Float = .2f, val top: Float = .25f, val right: Float = .8f, val bottom: Float = .75f) {
    fun json() = JSONArray(listOf(left, top, right, bottom))
    companion object { fun parse(a: JSONArray) = Region(a.getDouble(0).toFloat(), a.getDouble(1).toFloat(), a.getDouble(2).toFloat(), a.getDouble(3).toFloat()) }
}
data class QualityReport(val brightness: Int = 50, val sharpness: Int = 50, val width: Int = 0, val height: Int = 0, val warnings: List<String> = emptyList()) {
    fun json() = JSONObject().put("brightness", brightness).put("sharpness", sharpness).put("width", width).put("height", height).put("warnings", JSONArray(warnings))
    companion object { fun parse(j: JSONObject?) = if (j == null) QualityReport() else QualityReport(j.optInt("brightness", 50), j.optInt("sharpness", 50), j.optInt("width"), j.optInt("height"), j.optJSONArray("warnings")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList()) }
}
data class Evidence(
    val path: String, val role: String, val time: Long = System.currentTimeMillis(), val region: Region = Region(),
    val source: String = "camera", val sha256: String = "", val quality: QualityReport = QualityReport(),
    val latitude: Double? = null, val longitude: Double? = null, val accuracyMeters: Float? = null
) {
    fun json() = JSONObject().put("path", path).put("role", role).put("time", time).put("region", region.json()).put("source", source)
        .put("sha256", sha256).put("quality", quality.json()).put("latitude", latitude).put("longitude", longitude).put("accuracy_meters", accuracyMeters)
    companion object { fun parse(p: JSONObject) = Evidence(p.getString("path"), p.getString("role"), p.optLong("time", System.currentTimeMillis()), Region.parse(p.getJSONArray("region")), p.optString("source", "camera"), p.optString("sha256"), QualityReport.parse(p.optJSONObject("quality")), p.optDouble("latitude").takeUnless { it.isNaN() }, p.optDouble("longitude").takeUnless { it.isNaN() }, p.optDouble("accuracy_meters").takeUnless { it.isNaN() }?.toFloat()) }
}
data class Finding(val outcome: String, val explanation: String, val nextPhoto: String = "", val demo: Boolean = false, val reasonCode: String = "") {
    val modelUnavailable get() = !demo && (reasonCode == "MODEL_UNAVAILABLE" || explanation.contains("model could not complete this review", true) || explanation.contains("provider request failed", true) || explanation.contains("timed out", true))
    fun json() = JSONObject().put("outcome", outcome).put("explanation", explanation).put("next_photo", nextPhoto).put("demo", demo).put("reason_code", reasonCode)
    companion object {
        fun parse(j: JSONObject, demo: Boolean = false): Finding {
            val outcome = j.getString("outcome"); require(outcome in setOf("visible_repair_evidence", "visible_defect_remains", "insufficient_evidence")) { "Unknown AI outcome" }
            val explanation = j.getString("explanation"); require(explanation.isNotBlank()) { "Missing review explanation" }
            val next = j.optString("next_photo"); require(outcome != "insufficient_evidence" || next.isNotBlank()) { "Missing recapture instruction" }
            return Finding(outcome, explanation, next, demo, j.optString("reason_code"))
        }
    }
}
data class RoadCase(
    val id: String = UUID.randomUUID().toString(), val location: String, val note: String = "", val created: Long = System.currentTimeMillis(),
    val photos: List<Evidence>, val sync: String = "local", val error: String = "", val finding: Finding? = null,
    val history: List<String> = listOf("Original evidence saved on this device"), val revision: Int = 1,
    val title: String = location, val archived: Boolean = false, val reminderAt: Long? = null,
    val consentRevision: Int? = null, val consentAt: Long? = null,
    val trainingRevision: Int? = null, val trainingAt: Long? = null
) {
    val shortId get() = id.take(6).uppercase(); val latitude get() = photos.firstOrNull()?.latitude; val longitude get() = photos.firstOrNull()?.longitude
    val hasReviewConsent get() = consentRevision == revision && consentAt != null
    val hasTrainingConsent get() = hasReviewConsent && trainingRevision == revision && trainingAt != null
    val status get() = when { archived -> "Archived"; finding?.modelUnavailable == true -> "Review unavailable"; finding?.outcome == "insufficient_evidence" -> "New photo needed"; finding != null -> "Awaiting human review"; photos.size > 1 -> "Ready for review"; else -> "Awaiting repair photo" }
    fun json() = JSONObject().put("id", id).put("location", location).put("note", note).put("created", created).put("photos", JSONArray(photos.map { it.json() })).put("sync", sync).put("error", error).put("finding", finding?.json()).put("history", JSONArray(history)).put("revision", revision).put("title", title).put("archived", archived).put("reminder_at", reminderAt).put("review_consent", hasReviewConsent).put("review_consent_revision", consentRevision.takeIf { hasReviewConsent }).put("review_consent_at", consentAt.takeIf { hasReviewConsent }).put("training_consent", hasTrainingConsent).put("training_consent_revision", trainingRevision.takeIf { hasTrainingConsent }).put("training_consent_at", trainingAt.takeIf { hasTrainingConsent })
    companion object {
        fun parse(j: JSONObject): RoadCase {
            val images = j.getJSONArray("photos"); val history = j.optJSONArray("history") ?: JSONArray(); val location = j.getString("location")
            return RoadCase(j.getString("id"), location, j.optString("note"), j.getLong("created"), List(images.length()) { Evidence.parse(images.getJSONObject(it)) }, j.optString("sync", "local"), j.optString("error"), j.optJSONObject("finding")?.let { Finding.parse(it, it.optBoolean("demo")) }, List(history.length()) { history.getString(it) }, j.optInt("revision", 1), j.optString("title", location), j.optBoolean("archived"), j.optLong("reminder_at").takeIf { it > 0 }, j.optInt("review_consent_revision").takeIf { it > 0 }, j.optLong("review_consent_at").takeIf { it > 0 }, j.optInt("training_consent_revision").takeIf { it > 0 }, j.optLong("training_consent_at").takeIf { it > 0 })
        }
    }
}
data class CaptureDraft(val path: String, val existingCaseId: String?, val source: String, val savedAt: Long = System.currentTimeMillis()) {
    fun json() = JSONObject().put("path", path).put("existing_case_id", existingCaseId).put("source", source).put("saved_at", savedAt)
    companion object { fun parse(raw: String?) = runCatching { raw?.let(::JSONObject)?.let { CaptureDraft(it.getString("path"), it.optString("existing_case_id").takeIf(String::isNotBlank), it.optString("source", "camera"), it.optLong("saved_at")) } }.getOrNull() }
}

class CaseStore private constructor(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences("veridex_cases", Context.MODE_PRIVATE)
    private val mutable = MutableStateFlow(read()); val cases = mutable.asStateFlow()
    private fun read(): List<RoadCase> { val raw = preferences.getString("cases", "[]") ?: "[]"; return try { val a = JSONArray(raw); List(a.length()) { RoadCase.parse(a.getJSONObject(it)) } } catch (e: Exception) { throw IllegalStateException("Saved case data could not be read; it has not been overwritten.", e) } }
    @Synchronized fun put(case: RoadCase) { val next = (mutable.value.filterNot { it.id == case.id } + case).sortedByDescending { it.created }; check(preferences.edit().putString("cases", JSONArray(next.map { it.json() }).toString()).commit()) { "Could not save case" }; mutable.value = next }
    @Synchronized fun update(id: String, transform: (RoadCase) -> RoadCase) { mutable.value.find { it.id == id }?.let { put(transform(it)) } }
    @Synchronized fun remove(id: String) { val target = mutable.value.find { it.id == id } ?: return; val next = mutable.value.filterNot { it.id == id }; check(preferences.edit().putString("cases", JSONArray(next.map { it.json() }).toString()).commit()) { "Could not delete case" }; mutable.value = next; target.photos.forEach { File(it.path).takeIf(File::exists)?.delete() } }
    fun get(id: String) = mutable.value.find { it.id == id }
    fun duplicate(sha: String, excludingCase: String? = null) = sha.takeIf(String::isNotBlank)?.let { value -> mutable.value.firstOrNull { it.id != excludingCase && it.photos.any { photo -> photo.sha256 == value } } }
    var baseUrl: String get() = preferences.getString("base_url", "") ?: ""; set(value) { preferences.edit().putString("base_url", value.trim().trimEnd('/')).apply() }
    var language: String get() = preferences.getString("language", "en") ?: "en"; set(value) { preferences.edit().putString("language", value).apply() }
    var onboardingComplete: Boolean get() = preferences.getBoolean("onboarding", false); set(value) { preferences.edit().putBoolean("onboarding", value).apply() }
    var draft: CaptureDraft? get() = CaptureDraft.parse(preferences.getString("draft", null))?.takeIf { File(it.path).exists() }; set(value) { preferences.edit().apply { if (value == null) remove("draft") else putString("draft", value.json().toString()) }.apply() }
    companion object { @Volatile private var instance: CaseStore? = null; fun get(context: Context) = instance ?: synchronized(this) { instance ?: CaseStore(context).also { instance = it } } }
}
