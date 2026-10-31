package com.veridex.app.data

import android.Manifest
import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.*
import android.graphics.pdf.PdfDocument
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.FileProvider
import androidx.work.*
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit
import kotlin.math.*

object EvidenceExporter {
    private fun output(context: Context, case: RoadCase, extension: String) = File(File(context.cacheDir, "reports").apply { mkdirs() }, "VERIDEX-${case.shortId}.$extension")
    fun json(context: Context, case: RoadCase): File {
        val report = case.json().apply {
            remove("error"); remove("sync")
            val photos = getJSONArray("photos")
            repeat(photos.length()) { photos.getJSONObject(it).remove("path") }
            put("report_notice", "Evidence record only. This report does not certify repair quality or close a civic complaint.")
        }
        return output(context, case, "json").apply { writeText(report.toString(2)) }
    }
    fun pdf(context: Context, case: RoadCase): File {
        val document = PdfDocument(); val pageWidth = 1240; val pageHeight = 1754
        val title = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(18, 28, 23); textSize = 58f; typeface = Typeface.DEFAULT_BOLD }
        val body = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(48, 61, 52); textSize = 28f }
        val small = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(90, 102, 94); textSize = 22f }
        fun page(number: Int): Pair<PdfDocument.Page, Canvas> { val p = document.startPage(PdfDocument.PageInfo.Builder(pageWidth, pageHeight, number).create()); p.canvas.drawColor(Color.rgb(244, 247, 239)); return p to p.canvas }
        var pageNo = 1; var (page, canvas) = page(pageNo); var y = 110f
        fun finishAndNext() { document.finishPage(page); pageNo++; val next = page(pageNo); page = next.first; canvas = next.second; y = 100f }
        fun line(text: String, paint: Paint = body, gap: Float = 45f) { if (y > pageHeight - 110) finishAndNext(); canvas.drawText(text.take(82), 80f, y, paint); y += gap }
        line("VERIDEX EVIDENCE REPORT", title, 82f); line("Case ${case.shortId}  •  ${case.title}", body, 52f); line("Location: ${case.location}", body); line("Created: ${SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault()).format(Date(case.created))}", body)
        if (case.note.isNotBlank()) line("Notes: ${case.note}", body)
        line("Status: ${case.status}", body, 60f); line("Evidence timeline", title.apply { textSize = 40f }, 65f)
        case.photos.forEachIndexed { index, evidence ->
            if (y > pageHeight - 650) finishAndNext()
            line("${index + 1}. ${evidence.role.uppercase()} • ${SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault()).format(Date(evidence.time))}", body, 42f)
            line("Source: ${evidence.source}   SHA-256: ${evidence.sha256.take(20)}…", small, 36f)
            line("Quality: brightness ${evidence.quality.brightness}% • sharpness ${evidence.quality.sharpness}%", small, 36f)
            evidence.latitude?.let { line("Coordinates: %.5f, %.5f".format(Locale.US, it, evidence.longitude), small, 42f) }
            BitmapFactory.decodeFile(evidence.path)?.let { bitmap ->
                val maxW = 1000f; val maxH = 500f; val scale = min(maxW / bitmap.width, maxH / bitmap.height); val w = bitmap.width * scale; val h = bitmap.height * scale
                canvas.drawBitmap(bitmap, null, RectF(80f, y, 80f + w, y + h), Paint(Paint.ANTI_ALIAS_FLAG)); y += h + 42f; bitmap.recycle()
            }
        }
        line("NOTICE", title.apply { textSize = 34f }, 52f); line("This report records visual evidence. It does not certify repair quality", body); line("or automatically close a civic complaint. Human review remains required.", body)
        document.finishPage(page); return output(context, case, "pdf").also { file -> file.outputStream().use(document::writeTo); document.close() }
    }
    fun share(context: Context, file: File, mime: String) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
        context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply { type = mime; putExtra(Intent.EXTRA_STREAM, uri); addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION) }, "Share evidence report"))
    }
}

object Notifier {
    const val CHANNEL = "veridex_updates"
    fun createChannel(context: Context) { if (Build.VERSION.SDK_INT >= 26) context.getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel(CHANNEL, "Case updates", NotificationManager.IMPORTANCE_DEFAULT).apply { description = "Evidence uploads and follow-up reminders" }) }
    fun show(context: Context, id: Int, title: String, text: String) {
        createChannel(context)
        if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        NotificationManagerCompat.from(context).notify(id, NotificationCompat.Builder(context, CHANNEL).setSmallIcon(com.veridex.app.R.drawable.ic_launcher).setContentTitle(title).setContentText(text).setStyle(NotificationCompat.BigTextStyle().bigText(text)).setAutoCancel(true).build())
    }
}

class ReminderWorker(context: Context, params: WorkerParameters): Worker(context, params) {
    override fun doWork(): Result { val id = inputData.getString("case_id") ?: return Result.failure(); val item = CaseStore.get(applicationContext).get(id) ?: return Result.success(); if (!item.archived && item.photos.size == 1) Notifier.show(applicationContext, id.hashCode(), "Repair photo follow-up", "Case ${item.shortId} at ${item.location} is ready for a completion photo."); return Result.success() }
    companion object {
        fun schedule(context: Context, case: RoadCase, days: Int) {
            val target = System.currentTimeMillis() + TimeUnit.DAYS.toMillis(days.toLong())
            CaseStore.get(context).update(case.id) { it.copy(reminderAt = target, history = it.history + "Follow-up reminder set for $days day(s)") }
            val request = OneTimeWorkRequestBuilder<ReminderWorker>().setInitialDelay(days.toLong(), TimeUnit.DAYS).setInputData(workDataOf("case_id" to case.id)).build()
            WorkManager.getInstance(context).enqueueUniqueWork("reminder-${case.id}", ExistingWorkPolicy.REPLACE, request)
        }
    }
}

fun distanceMeters(aLat: Double, aLon: Double, bLat: Double, bLon: Double): Double {
    val earth = 6371000.0; val dLat = Math.toRadians(bLat - aLat); val dLon = Math.toRadians(bLon - aLon)
    val h = sin(dLat / 2).pow(2) + cos(Math.toRadians(aLat)) * cos(Math.toRadians(bLat)) * sin(dLon / 2).pow(2)
    return earth * 2 * atan2(sqrt(h), sqrt(1 - h))
}
