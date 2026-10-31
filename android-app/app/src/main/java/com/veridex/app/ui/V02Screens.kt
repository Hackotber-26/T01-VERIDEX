package com.veridex.app.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.*
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.veridex.app.data.CaptureDraft
import com.veridex.app.data.RoadCase
import kotlin.math.max
import kotlin.math.min

@Composable fun OnboardingScreen(language: String, setLanguage: (String) -> Unit, finish: () -> Unit) {
    var page by rememberSaveable { mutableIntStateOf(0) }
    val cards = listOf(
        Triple(Icons.Outlined.PhotoCamera, "Capture the same place", "Save the original pothole, location and marked road area."),
        Triple(Icons.Outlined.CenterFocusStrong, "Return with guidance", "Use the original-photo overlay to match the completion view safely."),
        Triple(Icons.Outlined.FactCheck, "Keep decisions accountable", "VERIDEX keeps evidence and human review separate. It never certifies a repair by itself.")
    )
    Surface(Modifier.fillMaxSize(), color = Ink, contentColor = Paper) { Column(Modifier.fillMaxSize().padding(28.dp), verticalArrangement = Arrangement.spacedBy(24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) { Text("VERIDEX", fontWeight = FontWeight.ExtraBold, letterSpacing = 3.sp); Spacer(Modifier.weight(1f)); TextButton(finish) { Text(tr("skip")) } }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { listOf("en" to "English", "kn" to "ಕನ್ನಡ", "hi" to "हिन्दी").forEach { (code, label) -> FilterChip(language == code, { setLanguage(code) }, label = { Text(label) }) } }
        Spacer(Modifier.weight(.2f))
        Icon(cards[page].first, null, tint = Mint, modifier = Modifier.size(70.dp))
        Eyebrow("${page + 1} / 3")
        Title(if (page == 0) tr("welcome") else cards[page].second, 36)
        Body(cards[page].third)
        Sheet { Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Outlined.HealthAndSafety, null, tint = Mint); Body("Stay off the roadway. Capture evidence only from a safe position.") } }
        Spacer(Modifier.weight(1f))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) { repeat(3) { Box(Modifier.weight(1f).height(4.dp).background(if (it <= page) Mint else Line, RoundedCornerShape(50))) } }
        Action(if (page == 2) tr("start") else tr("next"), onClick = { if (page == 2) finish() else page++ })
    } }
}

@Composable fun DraftCard(draft: CaptureDraft, resume: () -> Unit, discard: () -> Unit) {
    Sheet {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) { Icon(Icons.Outlined.EditNote, null, tint = Amber); Column(Modifier.weight(1f)) { Text(tr("resume"), fontWeight = FontWeight.Medium); Body(if (draft.existingCaseId == null) "Unfinished original report" else "Unfinished repair evidence") } }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { OutlinedButton(discard, Modifier.weight(1f)) { Text("Discard") }; Button(resume, Modifier.weight(1f)) { Text("Resume") } }
    }
}

@Composable fun MapScreen(cases: List<RoadCase>, open: (String) -> Unit) {
    val context = LocalContext.current; val located = cases.filter { !it.archived && it.latitude != null && it.longitude != null }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Eyebrow("LOCATION OVERVIEW"); Title("Case map"); Body("Coordinates remain on your device until you choose to upload a case.")
        if (located.isEmpty()) Sheet { Icon(Icons.Outlined.Map, null, tint = Mint, modifier = Modifier.size(38.dp)); Text("No mapped cases yet", fontSize = 20.sp); Body("Use current location while creating a case to place it on this map.") }
        else {
            val minLat = located.minOf { it.latitude!! }; val maxLat = located.maxOf { it.latitude!! }; val minLon = located.minOf { it.longitude!! }; val maxLon = located.maxOf { it.longitude!! }
            Box(Modifier.fillMaxWidth().height(360.dp).background(Panel, RoundedCornerShape(26.dp)).border(1.dp, Line, RoundedCornerShape(26.dp))) {
                Canvas(Modifier.fillMaxSize().padding(24.dp)) {
                    repeat(6) { n -> val x = size.width * n / 5; val y = size.height * n / 5; drawLine(Line, Offset(x, 0f), Offset(x, size.height), 1f); drawLine(Line, Offset(0f, y), Offset(size.width, y), 1f) }
                    located.forEachIndexed { index, item ->
                        val x = if (maxLon == minLon) size.width / 2 else ((item.longitude!! - minLon) / (maxLon - minLon) * size.width).toFloat()
                        val y = if (maxLat == minLat) size.height / 2 else (size.height - (item.latitude!! - minLat) / (maxLat - minLat) * size.height).toFloat()
                        drawCircle(Mint.copy(alpha = .18f), 28f, Offset(x, y)); drawCircle(Mint, 14f, Offset(x, y)); drawCircle(Ink, 6f, Offset(x, y)); drawCircle(Paper, 4f, Offset(x, y), style = Stroke(2f))
                    }
                }
                Pill("${located.size} mapped", Mint)
            }
            Body("This privacy-friendly overview plots saved coordinates without downloading third-party map tiles.")
            located.forEach { item ->
                Row(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(18.dp)).clickable { open(item.id) }.padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Icon(Icons.Outlined.LocationOn, null, tint = Mint); Column(Modifier.weight(1f)) { Text(item.title, fontWeight = FontWeight.Medium); Text("%.5f, %.5f".format(item.latitude, item.longitude), color = Muted, fontSize = 11.sp) }
                    IconButton({ context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("geo:${item.latitude},${item.longitude}?q=${item.latitude},${item.longitude}(${Uri.encode(item.title)})"))) }) { Icon(Icons.Outlined.OpenInNew, "Open in maps") }
                }
            }
        }
    }
}
