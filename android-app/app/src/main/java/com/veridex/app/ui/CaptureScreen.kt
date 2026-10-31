package com.veridex.app.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.veridex.app.data.*
import kotlinx.coroutines.*

@Composable fun CaptureScreen(existing: RoadCase?, back: () -> Unit, captured: (String, String) -> Unit, message: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    var permission by remember { mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) }
    var taking by remember { mutableStateOf(false) }
    var ready by remember { mutableStateOf(false) }
    var cameraError by remember { mutableStateOf("") }
    var overlayEnabled by remember { mutableStateOf(existing != null) }
    var overlayAlpha by remember { mutableFloatStateOf(.32f) }
    val reference by produceState<androidx.compose.ui.graphics.ImageBitmap?>(null, existing?.photos?.firstOrNull()?.path) { value = withContext(Dispatchers.IO) { existing?.photos?.firstOrNull()?.path?.let(BitmapFactory::decodeFile)?.asImageBitmap() } }
    androidx.lifecycle.compose.LifecycleEventEffect(androidx.lifecycle.Lifecycle.Event.ON_RESUME) {
        permission = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
    }
    val requestPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { permission = it }
    val importPhoto = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        uri?.let {
            scope.launch {
                taking = true
                try { val file = withContext(Dispatchers.IO) { PhotoFiles.import(context, uri) }; captured(file.path, "gallery") }
                catch (e: Exception) { message(e.message ?: "Could not import photo") }
                finally { taking = false }
            }
        }
    }
    val imageCapture = remember { ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build() }
    val previewView = remember { PreviewView(context).apply { implementationMode = PreviewView.ImplementationMode.COMPATIBLE; scaleType = PreviewView.ScaleType.FILL_CENTER } }
    DisposableEffect(permission, lifecycle) {
        var disposed = false
        var provider: ProcessCameraProvider? = null
        if (permission) {
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener({
                if (!disposed) try {
                    provider = future.get()
                    val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
                    provider?.unbindAll()
                    provider?.bindToLifecycle(lifecycle, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageCapture)
                    ready = true
                } catch (e: Exception) { cameraError = "Camera unavailable. You can import a photo instead." }
            }, ContextCompat.getMainExecutor(context))
        }
        onDispose { disposed = true; provider?.unbindAll(); ready = false }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        PageHeader(if (existing == null) "Capture original" else "Capture repair evidence", back)
        Row(verticalAlignment = Alignment.CenterVertically) { Eyebrow("01 CAPTURE", Mint); Spacer(Modifier.width(24.dp)); Eyebrow("02 MARK & SAVE") }
        Text(if (existing == null) "Show us the problem." else "Match the original view.", fontSize = 27.sp, lineHeight = 32.sp, fontWeight = FontWeight.Medium)
        existing?.let { case ->
            Row(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(18.dp)).padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Photo(case.photos.first().path, Modifier.size(64.dp))
                Column(Modifier.weight(1f)) { Eyebrow("ORIGINAL REFERENCE", Mint); Spacer(Modifier.height(6.dp)); Body(case.finding?.nextPhoto?.takeIf { it.isNotBlank() } ?: "Keep the same road area and a similar viewpoint.") }
            }
        }
        Box(Modifier.fillMaxWidth().height(330.dp).clip(RoundedCornerShape(28.dp)).background(Panel), contentAlignment = Alignment.Center) {
            if (permission && cameraError.isBlank()) {
                AndroidView(factory = { previewView }, modifier = Modifier.fillMaxSize())
                if (overlayEnabled && reference != null) {
                    Image(reference!!, "Original photo overlay", Modifier.fillMaxSize().graphicsLayer(alpha = overlayAlpha), contentScale = ContentScale.Crop)
                    existing?.photos?.firstOrNull()?.region?.let { r -> Canvas(Modifier.fillMaxSize()) { drawRect(Mint.copy(alpha = .8f), androidx.compose.ui.geometry.Offset(r.left * size.width, r.top * size.height), androidx.compose.ui.geometry.Size((r.right-r.left)*size.width, (r.bottom-r.top)*size.height), style = Stroke(2.dp.toPx())) } }
                }
                Box(Modifier.fillMaxWidth(.75f).height(180.dp).border(1.5.dp, Mint.copy(alpha = .85f), RoundedCornerShape(20.dp)))
                PillOverlay(Modifier.align(Alignment.TopCenter).padding(16.dp))
            } else Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Icon(Icons.Outlined.PhotoCamera, null, tint = Mint, modifier = Modifier.size(44.dp))
                Text(if (cameraError.isNotBlank()) cameraError else "Let’s open your camera", fontSize = 20.sp)
                Body("Camera access is only used when you capture evidence.")
                Button({ requestPermission.launch(Manifest.permission.CAMERA) }) { Text("Allow camera") }
                TextButton({ context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))) }) { Text("App permissions") }
            }
        }
        if (existing != null) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Switch(overlayEnabled, { overlayEnabled = it }); Text("Original overlay", fontSize = 12.sp)
            Slider(overlayAlpha, { overlayAlpha = it }, Modifier.weight(1f), enabled = overlayEnabled, valueRange = .1f..7f/10f)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Outlined.HealthAndSafety, null, tint = Muted, modifier = Modifier.size(18.dp)); Text("Stay off the roadway. Capture from a safe position.", color = Muted, fontSize = 11.sp) }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) {
            OutlinedIconButton({ importPhoto.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }, enabled = !taking, modifier = Modifier.size(56.dp)) { Icon(Icons.Outlined.PhotoLibrary, "Import photo") }
            Button(onClick = {
                taking = true
                val file = PhotoFiles.create(context)
                imageCapture.targetRotation = previewView.display?.rotation ?: android.view.Surface.ROTATION_0
                imageCapture.takePicture(ImageCapture.OutputFileOptions.Builder(file).build(), ContextCompat.getMainExecutor(context), object: ImageCapture.OnImageSavedCallback {
                    override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                        scope.launch {
                            try { withContext(Dispatchers.IO) { PhotoFiles.normalize(file) }; captured(file.path, "camera") }
                            catch (e: Exception) { file.delete(); message(e.message ?: "Could not save photo") }
                            finally { taking = false }
                        }
                    }
                    override fun onError(exception: ImageCaptureException) { file.delete(); taking = false; message("Capture failed. Please try again.") }
                })
            }, enabled = permission && ready && !taking, modifier = Modifier.size(80.dp), shape = CircleShape, contentPadding = PaddingValues(0.dp)) {
                if (taking) CircularProgressIndicator(Modifier.size(30.dp), color = Ink) else Icon(Icons.Outlined.PhotoCamera, "Take photo", Modifier.size(32.dp))
            }
            Box(Modifier.size(56.dp), contentAlignment = Alignment.Center) { Text("1×", color = Muted, fontSize = 16.sp) }
        }
        Text("Import or capture, then mark the affected area.", Modifier.align(Alignment.CenterHorizontally), fontSize = 12.sp, color = Muted)
    }
}
@Composable private fun PillOverlay(modifier: Modifier) {
    Box(modifier.background(Ink.copy(alpha = .8f), RoundedCornerShape(30.dp)).padding(horizontal = 14.dp, vertical = 8.dp)) { Text("KEEP THE WHOLE AREA VISIBLE", color = Mint, fontSize = 9.sp, letterSpacing = 1.sp) }
}
