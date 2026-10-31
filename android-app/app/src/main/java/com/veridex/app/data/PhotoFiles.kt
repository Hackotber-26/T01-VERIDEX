package com.veridex.app.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import androidx.exifinterface.media.ExifInterface
import java.io.File
import java.util.UUID
import java.security.MessageDigest
import kotlin.math.abs

object PhotoFiles {
    fun create(context: Context) = File(File(context.filesDir, "evidence").apply { mkdirs() }, "${UUID.randomUUID()}.jpg")
    fun import(context: Context, uri: Uri): File {
        val temp = create(context)
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                temp.outputStream().use { output ->
                    val buffer = ByteArray(8192); var total = 0L
                    while (true) { val n = input.read(buffer); if (n < 0) break; total += n; require(total <= 30_000_000) { "Please choose a photo smaller than 30 MB" }; output.write(buffer, 0, n) }
                }
            } ?: error("Could not read this photo")
            normalize(temp)
            return temp
        } catch (e: Exception) { temp.delete(); throw e }
    }
    fun normalize(file: File) {
        val info = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.path, info)
        require(info.outWidth > 0 && info.outHeight > 0) { "This file is not a supported image" }
        var sample = 1
        while (maxOf(info.outWidth, info.outHeight) / sample > 2400) sample *= 2
        val original = BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample }) ?: error("Unable to decode photo")
        val exif = ExifInterface(file)
        val matrix = Matrix().apply {
            if (exif.isFlipped) postScale(-1f, 1f)
            postRotate(exif.rotationDegrees.toFloat())
        }
        val rotated = Bitmap.createBitmap(original, 0, 0, original.width, original.height, matrix, true)
        val ratio = minOf(1f, 1600f / maxOf(rotated.width, rotated.height))
        val scaled = Bitmap.createScaledBitmap(rotated, (rotated.width * ratio).toInt().coerceAtLeast(1), (rotated.height * ratio).toInt().coerceAtLeast(1), true)
        file.outputStream().use { scaled.compress(Bitmap.CompressFormat.JPEG, 88, it) }
        if (original !== rotated) original.recycle()
        if (rotated !== scaled) rotated.recycle()
        scaled.recycle()
    }
    fun fingerprint(file: File): String = MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }
    fun inspect(file: File): QualityReport {
        val bitmap = BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = 4 }) ?: error("Unable to inspect photo")
        val step = maxOf(1, minOf(bitmap.width, bitmap.height) / 120); var sum = 0.0; var edges = 0.0; var count = 0
        fun lum(px: Int) = .2126 * android.graphics.Color.red(px) + .7152 * android.graphics.Color.green(px) + .0722 * android.graphics.Color.blue(px)
        for (y in step until bitmap.height step step) for (x in step until bitmap.width step step) { val here = lum(bitmap.getPixel(x, y)); sum += here; count++; edges += abs(here - lum(bitmap.getPixel(x - step, y))) + abs(here - lum(bitmap.getPixel(x, y - step))) }
        val brightness = if (count == 0) 0 else (sum / count).toInt().coerceIn(0, 255); val sharpness = if (count == 0) 0 else (edges / count).toInt().coerceIn(0, 100)
        val warnings = buildList { if (brightness < 38) add("Photo is very dark"); if (brightness > 225) add("Photo is overexposed"); if (sharpness < 9) add("Photo may be blurry"); if (bitmap.width < 120 || bitmap.height < 120) add("Photo resolution is low") }
        val result = QualityReport((brightness * 100 / 255).coerceIn(0, 100), sharpness, bitmap.width * 4, bitmap.height * 4, warnings); bitmap.recycle(); return result
    }
}
