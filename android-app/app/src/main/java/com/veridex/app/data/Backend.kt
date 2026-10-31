package com.veridex.app.data

import android.content.Context
import android.util.Base64
import androidx.work.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

class BackendException(val status: Int, message: String): IOException(message)
class Backend(private val baseUrl: String) {
    private fun request(path: String, body: JSONObject? = null, method: String = "POST"): JSONObject {
        require(baseUrl.isNotBlank()) { "Add your backend address in Connection first." }
        val connection = URL(baseUrl + path).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 15000; connection.readTimeout = if (path.endsWith("/review")) 420000 else 60000
            connection.requestMethod = method
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Accept", "application/json")
            if (body != null) {
                connection.doOutput = true
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            val text = (if (status in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() }.orEmpty()
            val json = runCatching { JSONObject(text) }.getOrElse { throw IOException("Backend returned an unreadable response ($status)") }
            if (status !in 200..299) throw BackendException(status, json.optString("error", "Request failed ($status)"))
            return json
        } finally { connection.disconnect() }
    }
    fun health(): JSONObject = request("/health", method = "GET")
    fun revokeCase(caseId: String) { request("/v1/cases/$caseId", method = "DELETE") }
    fun upload(case: RoadCase) {
        check(case.hasReviewConsent) { "Consent is required before uploading photos for AI review." }
        val body = case.json()
        val photos = body.getJSONArray("photos")
        case.photos.forEachIndexed { index, photo ->
            val file = File(photo.path)
            require(file.exists() && file.length() <= 6_000_000) { "Photo is missing or exceeds 6 MB" }
            photos.getJSONObject(index).remove("path")
            photos.getJSONObject(index).put("image_base64", Base64.encodeToString(file.readBytes(), Base64.NO_WRAP))
        }
        body.remove("finding"); body.remove("history"); body.remove("sync"); body.remove("error")
        val result = request("/v1/cases/sync", body)
        require(result.getString("id") == case.id && result.getInt("revision") == case.revision) { "Upload acknowledgement did not match this evidence" }
    }
    fun review(case: RoadCase): Finding = Finding.parse(request("/v1/cases/${case.id}/review", JSONObject().put("revision", case.revision)))
}

class UploadWorker(context: Context, params: WorkerParameters): CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val store = CaseStore.get(applicationContext)
        val id = inputData.getString("case_id") ?: return@withContext Result.failure()
        val snapshot = store.get(id) ?: return@withContext Result.failure()
        val endpoint = store.baseUrl
        store.update(id) { it.copy(sync = "uploading", error = "") }
        try {
            Backend(endpoint).upload(snapshot)
            store.update(id) {
                if (it.revision == snapshot.revision && store.baseUrl == endpoint) it.copy(sync = "uploaded", history = it.history + "Evidence uploaded to backend") else it
            }
            Notifier.show(applicationContext, id.hashCode(), "Evidence uploaded", "Case ${snapshot.shortId} is safely uploaded.")
            Result.success()
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            val retryable = e is IOException && (e !is BackendException || e.status >= 500 || e.status == 429)
            val retry = retryable && runAttemptCount < 3
            store.update(id) {
                if (it.revision == snapshot.revision && store.baseUrl == endpoint) it.copy(sync = if (retry) "queued" else "failed", error = e.message ?: "Upload failed") else it
            }
            if (!retry) Notifier.show(applicationContext, id.hashCode(), "Upload needs attention", "Case ${snapshot.shortId} could not be uploaded. Open VERIDEX to retry.")
            if (retry) Result.retry() else Result.failure()
        }
    }
    companion object {
        fun enqueue(context: Context, id: String) {
            val work = OneTimeWorkRequestBuilder<UploadWorker>()
                .setInputData(workDataOf("case_id" to id))
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS).build()
            WorkManager.getInstance(context).enqueueUniqueWork("upload-$id", ExistingWorkPolicy.APPEND_OR_REPLACE, work)
        }
    }
}
