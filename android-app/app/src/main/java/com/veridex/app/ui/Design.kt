package com.veridex.app.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.*

val Ink = Color(0xFF101714)
val Panel = Color(0xFF1B2520)
val Line = Color(0xFF334139)
val Mint = Color(0xFFCAEF85)
val Paper = Color(0xFFF2F5EC)
val Muted = Color(0xFFA6B4A9)
val Lilac = Color(0xFFD5C7F1)
val Amber = Color(0xFFF4CC83)

@Composable fun VeridexTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = darkColorScheme(primary = Mint, onPrimary = Ink, background = Ink, surface = Panel, onSurface = Paper, onBackground = Paper, outline = Line, secondary = Lilac), content = content)
}
@Composable fun Eyebrow(text: String, color: Color = Muted) = Text(text.uppercase(), color = color, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
@Composable fun Title(text: String, size: Int = 32) = Text(text, fontSize = size.sp, lineHeight = (size + 4).sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-1).sp)
@Composable fun Body(text: String, color: Color = Muted) = Text(text, color = color, fontSize = 14.sp, lineHeight = 21.sp)
@Composable fun Pill(text: String, color: Color = Mint) {
    Box(Modifier.clip(RoundedCornerShape(50)).background(color.copy(alpha = .11f)).border(1.dp, color.copy(alpha = .2f), RoundedCornerShape(50)).padding(horizontal = 10.dp, vertical = 6.dp)) {
        Text(text, color = color, fontSize = 11.sp, fontWeight = FontWeight.Medium)
    }
}
@Composable fun Action(text: String, icon: androidx.compose.ui.graphics.vector.ImageVector = Icons.Outlined.ArrowForward, enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick, Modifier.fillMaxWidth().heightIn(min = 56.dp), enabled = enabled, shape = RoundedCornerShape(18.dp), contentPadding = PaddingValues(18.dp)) {
        Text(text, Modifier.weight(1f), fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
        Icon(icon, null, Modifier.size(21.dp))
    }
}
@Composable fun Sheet(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Panel).border(1.dp, Line, RoundedCornerShape(24.dp)).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
}
@Composable fun PageHeader(label: String, onBack: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onBack, Modifier.background(Panel, CircleShape)) { Icon(Icons.Outlined.ArrowBack, "Go back") }
        Spacer(Modifier.width(14.dp)); Text(label, fontWeight = FontWeight.Medium, fontSize = 16.sp)
    }
}
@Composable fun Photo(path: String, modifier: Modifier = Modifier, fit: Boolean = false) {
    val bitmap by produceState<ImageBitmap?>(null, path) {
        value = withContext(Dispatchers.IO) {
            BitmapFactory.decodeFile(path, BitmapFactory.Options().apply { inSampleSize = 2 })?.asImageBitmap()
        }
    }
    if (bitmap != null) Image(bitmap!!, "Captured road evidence", modifier.clip(RoundedCornerShape(18.dp)), contentScale = if (fit) ContentScale.Fit else ContentScale.Crop)
    else Box(modifier.background(Line, RoundedCornerShape(18.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Outlined.Image, "Photo unavailable", tint = Muted) }
}
fun date(time: Long): String = SimpleDateFormat("dd MMM · HH:mm", Locale.getDefault()).format(Date(time))

@Composable fun RoadArtwork(modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val w = size.width; val h = size.height
        val road = Path().apply { moveTo(w * .40f, 0f); lineTo(w * .66f, 0f); lineTo(w * .99f, h); lineTo(w * .04f, h); close() }
        drawPath(road, Color(0xFF2D4031))
        drawLine(Mint.copy(alpha = .32f), Offset(w * .4f, 0f), Offset(w * .04f, h), 1.5f)
        drawLine(Mint.copy(alpha = .32f), Offset(w * .66f, 0f), Offset(w * .99f, h), 1.5f)
        repeat(5) { n ->
            val y = h * n / 5
            drawLine(Paper.copy(alpha = .35f), Offset(w * .53f, y), Offset(w * .53f, y + h * .08f), 3f)
        }
        val center = Offset(w * .51f, h * .62f)
        drawCircle(Mint.copy(alpha = .08f), h * .26f, center)
        drawCircle(Mint.copy(alpha = .22f), h * .19f, center, style = Stroke(1.5f))
        drawCircle(Mint, h * .12f, center, style = Stroke(2.5f))
        drawCircle(Ink, h * .07f, center)
        drawLine(Mint, center + Offset(-h * .04f, 0f), center + Offset(-h * .01f, h * .03f), 3f)
        drawLine(Mint, center + Offset(-h * .01f, h * .03f), center + Offset(h * .05f, -h * .04f), 3f)
    }
}
