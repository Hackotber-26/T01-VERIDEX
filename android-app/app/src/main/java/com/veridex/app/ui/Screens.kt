package com.veridex.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import com.veridex.app.AppModel
import com.veridex.app.BuildConfig
import com.veridex.app.data.*
import java.net.URI

@Composable fun HomeScreen(cases: List<RoadCase>, draft: CaptureDraft?, capture: () -> Unit, resume: () -> Unit, discard: () -> Unit, open: (String) -> Unit, all: () -> Unit, demo: () -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(24.dp), verticalArrangement = Arrangement.spacedBy(24.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(38.dp).background(Mint, RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Outlined.Verified, null, tint = Ink, modifier = Modifier.size(23.dp)) }
                Spacer(Modifier.width(10.dp)); Text("VERIDEX", fontWeight = FontWeight.ExtraBold, letterSpacing = 3.sp, fontSize = 17.sp)
                Spacer(Modifier.weight(1f)); Pill("FIELD NOTES", Muted)
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Eyebrow("Better roads. Clearer evidence.")
                Title("A photo starts it.\nProof completes it.", 36)
                Body("Capture the problem. Follow the repair.\nMake every resolution reviewable.")
            }
        }
        item {
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp)).background(Color(0xFF233526)).border(1.dp, Color(0xFF41563C), RoundedCornerShape(28.dp))) {
                Row(Modifier.fillMaxWidth().padding(start = 22.dp, top = 20.dp, end = 22.dp), verticalAlignment = Alignment.CenterVertically) {
                    Pill("01  /  ON THE GROUND", Mint)
                    Spacer(Modifier.weight(1f)); Icon(Icons.Outlined.NorthEast, null, tint = Mint)
                }
                Row(Modifier.fillMaxWidth().height(146.dp).padding(start = 22.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1.2f), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                        Text("See a pothole?\nStart here.", fontSize = 26.sp, fontWeight = FontWeight.Medium, lineHeight = 30.sp, color = Paper)
                        Text("One photo. A clearer record.", fontSize = 12.sp, color = Muted)
                    }
                    RoadArtwork(Modifier.weight(1f).fillMaxHeight())
                }
                Box(Modifier.padding(16.dp)) { Action(tr("capture"), Icons.Outlined.PhotoCamera, onClick = capture) }
            }
        }
        if (draft != null) item { DraftCard(draft, resume, discard) }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Stat(cases.size.toString().padStart(2, '0'), "Your cases", Modifier.weight(1f), Mint)
                Stat(cases.count { it.finding?.outcome == "insufficient_evidence" }.toString().padStart(2, '0'), "Need a new view", Modifier.weight(1f), Lilac)
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Your recent activity", fontSize = 19.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                TextButton(all) { Text("View all", color = Mint) }
            }
        }
        if (cases.isEmpty()) item {
            Sheet {
                Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    Icon(Icons.Outlined.AddLocationAlt, null, tint = Muted)
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) { Text("Your first case belongs here", fontWeight = FontWeight.Medium); Body("Take a photo to start an evidence trail. It stays saved on your phone.") }
                }
            }
        } else items(cases.take(3), key = { it.id }) { CaseCard(it) { open(it.id) } }
        item {
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Lilac.copy(alpha = .09f)).clickable(onClick = demo).padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.AutoAwesome, null, tint = Lilac)
                Column(Modifier.weight(1f).padding(horizontal = 14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Why ask for another photo?", fontSize = 14.sp, fontWeight = FontWeight.Medium, color = Lilac)
                    Text("Explore the evidence-review demo", fontSize = 12.sp, color = Muted)
                }
                Icon(Icons.Outlined.ArrowForward, null, tint = Lilac, modifier = Modifier.size(18.dp))
            }
        }
        item { Eyebrow("A status is not proof.") }
    }
}
@Composable private fun Stat(value: String, label: String, modifier: Modifier, accent: Color) {
    Column(modifier.clip(RoundedCornerShape(22.dp)).background(Panel).padding(18.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(value, fontSize = 32.sp, color = accent, fontWeight = FontWeight.Medium)
        Text(label, fontSize = 12.sp, color = Muted)
    }
}
@Composable fun CaseCard(case: RoadCase, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Panel).clickable(onClick = onClick).padding(14.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
        Photo(case.photos.first().path, Modifier.size(72.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Eyebrow("CASE ${case.shortId}")
            Text(case.title, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
            Text(case.status, color = if (case.finding?.outcome == "insufficient_evidence") Amber else Mint, fontSize = 11.sp)
        }
        Icon(Icons.Outlined.ChevronRight, null, tint = Muted)
    }
}
@Composable fun CasesScreen(cases: List<RoadCase>, capture: () -> Unit, open: (String) -> Unit) {
    var filter by rememberSaveable { mutableStateOf("All") }
    var query by rememberSaveable { mutableStateOf("") }
    val filtered = cases.filter { item -> (query.isBlank() || item.title.contains(query, true) || item.location.contains(query, true) || item.shortId.contains(query, true)) && when (filter) { "Local" -> !item.archived && item.sync != "uploaded"; "Follow-up" -> !item.archived && (item.finding?.outcome == "insufficient_evidence" || item.photos.size == 1); "Archived" -> item.archived; else -> !item.archived } }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        item { Eyebrow("YOUR EVIDENCE TRAIL"); Spacer(Modifier.height(10.dp)); Title(tr("cases")); Spacer(Modifier.height(8.dp)); Body("Every photo. Every follow-up. In one place.") }
        item { OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth(), leadingIcon = { Icon(Icons.Outlined.Search, null) }, label = { Text(tr("search")) }, trailingIcon = { if (query.isNotBlank()) IconButton({ query = "" }) { Icon(Icons.Outlined.Close, "Clear search") } }, singleLine = true, shape = RoundedCornerShape(16.dp)) }
        item { Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) { listOf("All", "Local", "Follow-up", "Archived").forEach { label -> FilterChip(selected = filter == label, onClick = { filter = label }, label = { Text(label) }) } } }
        if (filtered.isEmpty()) item { Sheet { Icon(Icons.Outlined.FolderOpen, null, tint = Mint, modifier = Modifier.size(36.dp)); Text("No cases here yet", fontSize = 20.sp); Body("Capture an original photo to begin. Your saved cases will appear here.") } }
        items(filtered, key = { it.id }) { CaseCard(it) { open(it.id) } }
        item { Action(tr("new_case"), Icons.Outlined.Add, onClick = capture) }
    }
}

@Composable fun DetailScreen(case: RoadCase, busy: Boolean, back: () -> Unit, capture: () -> Unit, upload: () -> Unit, review: () -> Unit, rename: (String) -> Unit, archive: () -> Unit, delete: () -> Unit, remind: (Int) -> Unit) {
    val context = LocalContext.current
    var renameDialog by remember { mutableStateOf(false) }; var deleteDialog by remember { mutableStateOf(false) }; var reminderMenu by remember { mutableStateOf(false) }; var title by remember(case.title) { mutableStateOf(case.title) }
    val notificationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        PageHeader("Case ${case.shortId}", back)
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { Eyebrow(date(case.created)); Title(case.title, 28); Body(case.location); Pill(case.status, if (case.finding?.outcome == "insufficient_evidence") Amber else Mint) }
        if (case.note.isNotBlank()) Body(case.note)
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            AssistChip({ renameDialog = true }, { Text("Rename") }, leadingIcon = { Icon(Icons.Outlined.Edit, null, Modifier.size(16.dp)) })
            AssistChip({ reminderMenu = true }, { Text("Remind") }, leadingIcon = { Icon(Icons.Outlined.NotificationsActive, null, Modifier.size(16.dp)) })
            AssistChip(archive, { Text(if (case.archived) "Restore" else "Archive") }, leadingIcon = { Icon(Icons.Outlined.Archive, null, Modifier.size(16.dp)) })
            AssistChip({ EvidenceExporter.share(context, EvidenceExporter.pdf(context, case), "application/pdf") }, { Text("PDF") }, leadingIcon = { Icon(Icons.Outlined.PictureAsPdf, null, Modifier.size(16.dp)) })
            AssistChip({ EvidenceExporter.share(context, EvidenceExporter.json(context, case), "application/json") }, { Text("JSON") }, leadingIcon = { Icon(Icons.Outlined.DataObject, null, Modifier.size(16.dp)) })
            AssistChip({ deleteDialog = true }, { Text("Delete") }, leadingIcon = { Icon(Icons.Outlined.Delete, null, Modifier.size(16.dp)) })
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) { Photo(case.photos.first().path, Modifier.fillMaxWidth().height(190.dp)); Eyebrow("Original") }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (case.photos.size > 1) Photo(case.photos.last().path, Modifier.fillMaxWidth().height(190.dp)) else Box(Modifier.fillMaxWidth().height(190.dp).clip(RoundedCornerShape(18.dp)).background(Panel).border(1.dp, Line, RoundedCornerShape(18.dp)).clickable(onClick = capture), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) { Icon(Icons.Outlined.AddAPhoto, "Add repair photo", tint = Mint); Text("Add repair photo", fontSize = 12.sp, color = Muted) } }
                Eyebrow(if (case.photos.size > 2) "Latest recapture" else "Claimed after")
            }
        }
        case.finding?.let { FindingCard(it) }
        Sheet {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) { Icon(if (case.sync == "uploaded") Icons.Outlined.CloudDone else Icons.Outlined.CloudUpload, null, tint = Mint); Text(when (case.sync) { "uploaded" -> "Evidence uploaded"; "queued" -> "Upload queued"; "uploading" -> "Uploading evidence…"; "failed" -> "Upload needs attention"; else -> "Saved on this phone" }, fontWeight = FontWeight.Medium) }
            Body(when (case.sync) { "queued" -> "Uploads resume when connected. You can leave this screen."; "uploaded" -> "This version of your evidence is saved on the backend."; else -> "Your photos are retained locally, even if the connection drops." })
            if (case.error.isNotBlank()) Text(case.error, color = Amber, fontSize = 12.sp)
            if (case.sync !in listOf("queued", "uploading", "uploaded")) OutlinedButton(upload, Modifier.fillMaxWidth()) { Text(if (case.sync == "failed") "Retry upload" else "Upload evidence") }
        }
        Action(if (case.finding?.outcome == "insufficient_evidence") "Take requested photo" else if (case.photos.size > 1) "Add another repair photo" else "Capture repair photo", Icons.Outlined.PhotoCamera, enabled = !busy && case.photos.size < 12, onClick = capture)
        if (case.photos.size > 1) OutlinedButton(review, Modifier.fillMaxWidth().heightIn(min = 52.dp), enabled = !busy && case.sync == "uploaded", shape = RoundedCornerShape(18.dp)) { if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp) else Icon(Icons.Outlined.AutoAwesome, null, Modifier.size(18.dp)); Spacer(Modifier.width(10.dp)); Text(if (busy) "Reviewing evidence…" else "Request AI review") }
        Eyebrow("EVIDENCE HISTORY")
        case.photos.forEachIndexed { index, photo ->
            Sheet { Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) { Photo(photo.path, Modifier.size(54.dp)); Column(Modifier.weight(1f)) { Text("${index + 1}. ${photo.role.replaceFirstChar { it.uppercase() }} • ${photo.source}", fontSize = 14.sp); Text(date(photo.time), fontSize = 11.sp, color = Muted); Text("Brightness ${photo.quality.brightness}% • Sharpness ${photo.quality.sharpness}%", fontSize = 10.sp, color = Muted); if (photo.sha256.isNotBlank()) Text("SHA-256 ${photo.sha256.take(14)}…", fontSize = 9.sp, color = Muted) } } }
        }
        case.history.forEach { event -> Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { Text("•", color = Mint); Body(event) } }
        Body("AI findings describe visible evidence. A human reviewer makes the final decision; this app does not certify repair quality.")
    }
    if (renameDialog) AlertDialog({ renameDialog = false }, title = { Text("Rename case") }, text = { OutlinedTextField(title, { title = it }, singleLine = true) }, confirmButton = { TextButton({ rename(title); renameDialog = false }) { Text("Save") } }, dismissButton = { TextButton({ renameDialog = false }) { Text("Cancel") } })
    if (deleteDialog) AlertDialog({ deleteDialog = false }, title = { Text("Delete this case?") }, text = { Text("Photos and local evidence history will be permanently removed from this device.") }, confirmButton = { TextButton({ delete(); deleteDialog = false }, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Delete") } }, dismissButton = { TextButton({ deleteDialog = false }) { Text("Cancel") } })
    if (reminderMenu) AlertDialog({ reminderMenu = false }, title = { Text("Follow-up reminder") }, text = { Column { listOf(1, 3, 7, 14).forEach { days -> TextButton({ if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS); remind(days); reminderMenu = false }, Modifier.fillMaxWidth()) { Text("In $days day${if (days == 1) "" else "s"}") } } } }, confirmButton = {}, dismissButton = { TextButton({ reminderMenu = false }) { Text("Cancel") } })
}

@Composable fun FindingCard(finding: Finding) {
    val accent = when (finding.outcome) { "visible_repair_evidence" -> Mint; "visible_defect_remains" -> Lilac; else -> Amber }
    Sheet {
        Eyebrow(if (finding.demo) "DEMO RESULT · NOT AN AI PREDICTION" else "AI EVIDENCE FINDING", accent)
        Text(when (finding.outcome) { "visible_repair_evidence" -> "Visible repair evidence"; "visible_defect_remains" -> "The defect is still visible"; else -> "We need a clearer view" }, fontSize = 23.sp, lineHeight = 28.sp, fontWeight = FontWeight.Medium)
        Body(finding.explanation)
        if (finding.nextPhoto.isNotBlank()) {
            HorizontalDivider(color = Line)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) { Icon(Icons.Outlined.CenterFocusStrong, null, tint = accent); Text(finding.nextPhoto, fontSize = 14.sp, lineHeight = 21.sp, color = accent) }
        }
        Pill("Human review pending", Muted)
    }
}

@Composable fun DemoScreen(back: () -> Unit) {
    var scenario by rememberSaveable { mutableIntStateOf(0) }
    val findings = listOf(
        Finding("insufficient_evidence", "The completion photo is obstructed. The original pothole area cannot be assessed.", "Take a new photo showing the entire marked area without the obstruction, from a similar viewpoint.", true),
        Finding("visible_repair_evidence", "In this example, the original defect area is visible and appears patched. This does not establish structural repair quality.", demo = true),
        Finding("visible_defect_remains", "In this example, the pothole remains visible in the marked region of the completion photo.", demo = true)
    )
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
        PageHeader("The evidence loop", back)
        Pill("INTERACTIVE DEMO", Lilac)
        Title("Better questions.\nBetter evidence.")
        Body("Explore three scripted outcomes. These examples do not analyse your photos or call a model.")
        RoadArtwork(Modifier.fillMaxWidth().height(150.dp).clip(RoundedCornerShape(24.dp)).background(Panel))
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("Obstructed", "Visible repair", "Defect remains").forEachIndexed { index, label -> FilterChip(scenario == index, { scenario = index }, label = { Text(label) }) }
        }
        FindingCard(findings[scenario])
        Sheet { Eyebrow("THE VERIDEX DIFFERENCE", Lilac); Body("When evidence is unclear, ask for a specific missing view instead of forcing a yes/no verdict. Keep the original photo, the follow-up and the reasoning together.") }
        Action("Start a real case", Icons.Outlined.ArrowBack, onClick = back)
    }
}

@Composable fun ConnectionScreen(model: AppModel, language: String, setLanguage: (String) -> Unit, replayOnboarding: () -> Unit) {
    var url by rememberSaveable { mutableStateOf(model.store.baseUrl) }
    var validation by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).imePadding().padding(24.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
        Eyebrow("READY WHEN YOUR MODEL IS")
        Title("Connect the dots.")
        Body("Capture now. Connect your VERIDEX backend when it’s ready.")
        Sheet {
            Eyebrow(tr("language"), Mint)
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) { listOf("en" to "English", "kn" to "ಕನ್ನಡ", "hi" to "हिन्दी").forEach { (code, label) -> FilterChip(language == code, { setLanguage(code) }, label = { Text(label) }) } }
            OutlinedButton(replayOnboarding, Modifier.fillMaxWidth()) { Icon(Icons.Outlined.School, null); Spacer(Modifier.width(8.dp)); Text("View capture guide") }
        }
        Sheet {
            Icon(Icons.Outlined.Hub, null, tint = Mint, modifier = Modifier.size(32.dp))
            Text("Backend connection", fontSize = 21.sp, fontWeight = FontWeight.Medium)
            Body("Photos go to your backend. Your model’s secret API key stays on the server.")
            OutlinedTextField(url, { url = it; validation = "" }, Modifier.fillMaxWidth(), label = { Text("Backend URL") }, placeholder = { Text("https://api.example.com") }, singleLine = true, shape = RoundedCornerShape(14.dp), isError = validation.isNotBlank())
            if (validation.isNotBlank()) Text(validation, color = Amber, fontSize = 12.sp)
            Action("Save connection", Icons.Outlined.Link) {
                val clean = url.trim().trimEnd('/')
                val uri = runCatching { URI(clean) }.getOrNull()
                val local = uri?.host in listOf("10.0.2.2", "127.0.0.1", "localhost")
                if (clean.isNotEmpty() && (uri?.host.isNullOrBlank() || uri?.userInfo != null || !uri?.query.isNullOrBlank() || !uri?.fragment.isNullOrBlank() || !(uri?.scheme == "https" || BuildConfig.DEBUG && local && uri?.scheme == "http"))) {
                    validation = "Use an HTTPS URL, or a localhost/emulator HTTP address in this debug build."
                } else { model.configure(clean) }
            }
        }
        Sheet {
            Eyebrow("WHAT WORKS OFFLINE", Mint)
            Body("Camera capture, photo import, area marking, case history and the scripted demo. Uploads need a configured backend and a connection.")
        }
        if (BuildConfig.DEBUG) Sheet {
            Eyebrow("DEVELOPER SETUP", Lilac)
            Body("For the included local backend on an Android emulator, use http://10.0.2.2:8080. On a USB device, use adb reverse tcp:8080 tcp:8080 and http://127.0.0.1:8080.")
        }
        Body("VERIDEX · Prototype 0.2\nPhotos stay in private app storage. Uninstalling removes local cases. Live AI and reviewer accounts require a backend integration.")
    }
}
