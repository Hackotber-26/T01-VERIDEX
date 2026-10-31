package com.veridex.app

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.veridex.app.data.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

class AppModel(application: Application): AndroidViewModel(application) {
    val store = CaseStore.get(application)
    val cases = store.cases
    private val busyState = MutableStateFlow(false)
    val busy = busyState.asStateFlow()
    private val messageState = MutableStateFlow<String?>(null)
    val message = messageState.asStateFlow()
    fun clearMessage() { messageState.value = null }
    fun notify(text: String) { messageState.value = text }
    fun configure(url: String) {
        viewModelScope.launch(Dispatchers.IO) {
            if (store.baseUrl != url) {
                store.baseUrl = url
                store.cases.value.forEach { item ->
                    androidx.work.WorkManager.getInstance(getApplication()).cancelUniqueWork("upload-${item.id}")
                    store.update(item.id) { it.copy(sync = "local", error = "") }
                }
            }
            notify(if (url.isBlank()) "Connection cleared. Local capture remains available." else "Backend address saved. Upload a case to connect.")
        }
    }
    fun beginDraft(path: String, existingId: String?, source: String) { store.draft = CaptureDraft(path, existingId, source) }
    fun discardDraft() { store.draft?.let { java.io.File(it.path).delete() }; store.draft = null }
    fun save(path: String, location: String, note: String, region: Region, existingId: String?, source: String, latitude: Double?, longitude: Double?, accuracy: Float?, done: (String) -> Unit) {
        viewModelScope.launch {
            busyState.value = true
            try {
                val id = withContext(Dispatchers.IO) {
                    if (existingId != null) {
                        val existing = store.get(existingId) ?: error("Case no longer exists")
                        require(existing.photos.size < 12) { "This prototype supports up to 12 photos per case." }
                        val report = PhotoFiles.inspect(java.io.File(path)); val sha = PhotoFiles.fingerprint(java.io.File(path))
                        store.duplicate(sha, existing.id)?.let { duplicate -> error("This image already belongs to case ${duplicate.shortId}.") }
                        val distance = if (latitude != null && longitude != null && existing.latitude != null && existing.longitude != null) distanceMeters(existing.latitude!!, existing.longitude!!, latitude, longitude) else null
                        val additions = buildList { add("New completion evidence saved; review required"); if (distance != null && distance > 250) add("Location warning: capture was ${distance.toInt()} m from the original") }
                        store.put(existing.copy(photos = existing.photos + Evidence(path, if (existing.photos.size > 1) "recapture" else "after", region = region, source = source, sha256 = sha, quality = report, latitude = latitude, longitude = longitude, accuracyMeters = accuracy), finding = null, sync = "local", error = "", revision = existing.revision + 1, history = existing.history + additions))
                        existing.id
                    } else {
                        val report = PhotoFiles.inspect(java.io.File(path)); val sha = PhotoFiles.fingerprint(java.io.File(path))
                        store.duplicate(sha)?.let { duplicate -> error("This image already belongs to case ${duplicate.shortId}.") }
                        val new = RoadCase(location = location.trim(), note = note.trim(), photos = listOf(Evidence(path, "before", region = region, source = source, sha256 = sha, quality = report, latitude = latitude, longitude = longitude, accuracyMeters = accuracy)))
                        store.put(new); new.id
                    }
                }
                store.draft = null
                done(id)
            } catch (e: Exception) { notify(e.message ?: "Could not save") }
            finally { busyState.value = false }
        }
    }
    fun rename(id: String, title: String) { if (title.isNotBlank()) store.update(id) { it.copy(title = title.trim(), history = it.history + "Case renamed") } }
    fun archive(id: String) { store.update(id) { it.copy(archived = !it.archived, history = it.history + if (it.archived) "Case restored" else "Case archived") } }
    fun delete(id: String) { androidx.work.WorkManager.getInstance(getApplication()).cancelUniqueWork("upload-$id"); androidx.work.WorkManager.getInstance(getApplication()).cancelUniqueWork("reminder-$id"); store.remove(id) }
    fun remind(id: String, days: Int) { store.get(id)?.let { ReminderWorker.schedule(getApplication(), it, days); notify("Follow-up reminder set for $days day(s).") } }
    fun upload(id: String) {
        if (store.baseUrl.isBlank()) { notify("Add a backend address in Connection to upload. Your case is saved locally."); return }
        viewModelScope.launch(Dispatchers.IO) {
            store.update(id) { it.copy(sync = "queued", error = "") }
            UploadWorker.enqueue(getApplication(), id)
        }
    }
    fun review(id: String) {
        viewModelScope.launch {
            busyState.value = true
            try {
                withContext(Dispatchers.IO) {
                    val snapshot = store.get(id) ?: error("Case not found")
                    require(snapshot.sync == "uploaded") { "Upload the latest evidence before requesting a review." }
                    val result = Backend(store.baseUrl).review(snapshot)
                    store.update(id) { if (it.revision == snapshot.revision) it.copy(finding = result, history = it.history + "AI evidence review: ${result.explanation}" + listOfNotNull(result.nextPhoto.takeIf { text -> text.isNotBlank() }?.let { text -> "Requested photo: $text" })) else it }
                }
            } catch (e: Exception) { notify(e.message ?: "AI review failed. Try again.") }
            finally { busyState.value = false }
        }
    }
}
