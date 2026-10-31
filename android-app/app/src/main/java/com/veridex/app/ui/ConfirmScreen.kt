package com.veridex.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.location.LocationManager
import android.os.Build
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.veridex.app.data.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable fun ConfirmScreen(path: String, source: String, existing: RoadCase?, busy: Boolean, back: () -> Unit, message: (String) -> Unit, save: (String, String, Region, Double?, Double?, Float?) -> Unit) {
    val context = LocalContext.current
    var location by rememberSaveable(path) { mutableStateOf(existing?.location ?: "") }
    var note by rememberSaveable(path) { mutableStateOf(existing?.note ?: "") }
    var left by rememberSaveable(path) { mutableFloatStateOf(.2f) }
    var top by rememberSaveable(path) { mutableFloatStateOf(.25f) }
    var right by rememberSaveable(path) { mutableFloatStateOf(.8f) }
    var bottom by rememberSaveable(path) { mutableFloatStateOf(.75f) }
    var marked by rememberSaveable(path) { mutableStateOf(false) }
    val regionSmall by remember { derivedStateOf { (right - left) * (bottom - top) < .03f } }
    var latitude by rememberSaveable(path) { mutableStateOf<Double?>(null) }; var longitude by rememberSaveable(path) { mutableStateOf<Double?>(null) }; var accuracy by rememberSaveable(path) { mutableStateOf<Float?>(null) }
    var locating by rememberSaveable(path) { mutableStateOf(false) }
    val bitmap by produceState<ImageBitmap?>(null, path) { value = withContext(Dispatchers.IO) { BitmapFactory.decodeFile(path)?.asImageBitmap() } }
    val quality by produceState<QualityReport?>(null, path) { value = withContext(Dispatchers.IO) { runCatching { PhotoFiles.inspect(java.io.File(path)) }.getOrNull() } }
    fun getLocation() {
        val manager = context.getSystemService(LocationManager::class.java)
        try {
            locating = true
            val providers = listOf(LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER)
                .filter { runCatching { manager.isProviderEnabled(it) }.getOrDefault(false) }
            if (providers.isEmpty()) { locating = false; message("Turn on Location in Android settings, or enter a landmark."); return }
            fun applyFix(result: android.location.Location) {
                latitude = result.latitude; longitude = result.longitude
                accuracy = if (result.hasAccuracy()) result.accuracy else null
                location = "%.5f, %.5f".format(java.util.Locale.US, result.latitude, result.longitude)
                locating = false
            }
            val cached = providers.mapNotNull { runCatching { manager.getLastKnownLocation(it) }.getOrNull() }
                .filter { System.currentTimeMillis() - it.time < 10 * 60 * 1000L }
                .minByOrNull { if (it.hasAccuracy()) it.accuracy else Float.MAX_VALUE }
            cached?.let(::applyFix)
            if (Build.VERSION.SDK_INT < 30) {
                locating = false
                if (cached == null) message("This Android version has no recent location fix. Turn on Location or enter a landmark.")
                return
            }
            fun requestProvider(index: Int) {
                if (index >= providers.size) {
                    locating = false
                    if (cached == null) message("Could not get a current location. Check that Location is on, then try again or enter a landmark.")
                    return
                }
                val cancellation = android.os.CancellationSignal()
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ cancellation.cancel() }, 7000)
                manager.getCurrentLocation(providers[index], cancellation, ContextCompat.getMainExecutor(context)) { result ->
                    if (result != null) applyFix(result) else requestProvider(index + 1)
                }
            }
            requestProvider(0)
        } catch (_: SecurityException) { locating = false; message("Allow location permission in Android settings, or enter a landmark.") }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        if (grants.values.any { it }) getLocation() else message("Location permission declined. You can still enter a landmark.")
    }
    LaunchedEffect(path, existing?.id) {
        val fineGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarseGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (fineGranted || coarseGranted) getLocation()
        else permission.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION))
    }
    val speech = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { note = listOf(note, it).filter(String::isNotBlank).joinToString(" ") }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).imePadding().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        PageHeader("Review your photo", back)
        Eyebrow("02 MARK & SAVE", Mint)
        Title(if (existing == null) "Focus on what matters." else "Mark the same road area.", 28)
        Body("Drag a box around the affected area, or confirm the suggested box. Include a little road around it.")
        quality?.let { q ->
            val original = existing?.photos?.firstOrNull()?.quality
            val orientationChanged = original != null && original.width > 0 && q.width > 0 && (original.width > original.height) != (q.width > q.height)
            val aspectChanged = original != null && original.height > 0 && q.height > 0 && kotlin.math.abs(original.width.toFloat()/original.height - q.width.toFloat()/q.height) > .35f
            val issues = q.warnings + listOfNotNull("Photo orientation differs from the original".takeIf { orientationChanged }, "Framing shape differs from the original".takeIf { aspectChanged })
            Sheet { Eyebrow("ON-DEVICE QUALITY CHECK", if (issues.isEmpty()) Mint else Amber); Text("Brightness ${q.brightness}%  •  Sharpness ${q.sharpness}%", fontSize = 13.sp); if (issues.isEmpty()) Body("Photo passes the basic local checks.") else issues.forEach { Text("• $it", color = Amber, fontSize = 12.sp) } }
        }
        bitmap?.let { image ->
            Box(Modifier.fillMaxWidth().aspectRatio(image.width.toFloat() / image.height).clip(RoundedCornerShape(20.dp))) {
                Image(image, "Evidence photo. Draw a box around the pothole.", Modifier.fillMaxSize())
                Canvas(Modifier.fillMaxSize().pointerInput(path) {
                    var start = Offset.Zero
                    detectDragGestures(onDragStart = { start = Offset((it.x / size.width).coerceIn(0f, 1f), (it.y / size.height).coerceIn(0f, 1f)) }, onDragEnd = { marked = right - left >= .03f && bottom - top >= .03f }) { change, _ ->
                        change.consume()
                        val end = Offset((change.position.x / size.width).coerceIn(0f, 1f), (change.position.y / size.height).coerceIn(0f, 1f))
                        left = minOf(start.x, end.x); right = maxOf(start.x, end.x); top = minOf(start.y, end.y); bottom = maxOf(start.y, end.y)
                        marked = false
                    }
                }) {
                    val start = Offset(left * size.width, top * size.height)
                    val extent = Size((right - left) * size.width, (bottom - top) * size.height)
                    drawRect(Mint.copy(alpha = .18f), start, extent)
                    drawRect(Mint, start, extent, style = Stroke(3.dp.toPx()))
                }
            }
        } ?: LinearProgressIndicator(Modifier.fillMaxWidth())
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Checkbox(marked, { checked ->
                if (right - left < .03f || bottom - top < .03f) { left = .2f; top = .25f; right = .8f; bottom = .75f }
                marked = checked
            }); Text("The box covers the affected area", fontSize = 13.sp)
        }
        if (regionSmall) Text("Make the marked area larger and include some surrounding road.", color = Amber, fontSize = 12.sp)
        if (existing == null) {
            OutlinedTextField(location, { location = it }, Modifier.fillMaxWidth(), label = { Text("Location or landmark *") }, shape = RoundedCornerShape(16.dp), maxLines = 2)
            TextButton({
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) getLocation()
                else permission.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION))
            }, enabled = !locating) { if (locating) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp) else Icon(Icons.Outlined.MyLocation, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text(if (locating) "Finding your location…" else if (latitude != null) "Location attached · ±${accuracy?.toInt() ?: "?"} m" else "Use current location") }
            if (latitude == null && !locating) Body("VERIDEX will fill this from your phone when location permission and Location are available.")
            OutlinedTextField(note, { note = it }, Modifier.fillMaxWidth(), label = { Text("Notes (optional)") }, shape = RoundedCornerShape(16.dp), minLines = 2, maxLines = 4)
            TextButton({ runCatching { speech.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)) }.onFailure { message("Voice entry is unavailable on this device.") } }) { Icon(Icons.Outlined.Mic, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Speak notes") }
        } else {
            Pill(existing.location)
            TextButton({
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) getLocation()
                else permission.launch(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION))
            }, enabled = !locating) { if (locating) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp) else Icon(Icons.Outlined.MyLocation, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text(if (locating) "Finding location…" else if (latitude == null) "Attach current location" else "Location attached · ±${accuracy?.toInt() ?: "?"} m") }
        }
        if (source == "gallery") Body("Gallery import • original capture metadata may not be available.", Amber)
        Action(if (busy) "Saving…" else tr("save"), Icons.Outlined.Check, enabled = !busy && marked && !regionSmall && location.isNotBlank() && bitmap != null) { save(location, note, Region(left, top, right, bottom), latitude, longitude, accuracy) }
        Body("Saved privately on your phone. You choose when to upload it.")
    }
}
