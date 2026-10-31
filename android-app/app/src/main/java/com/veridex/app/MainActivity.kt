package com.veridex.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.veridex.app.ui.*

class MainActivity: ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT), navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT))
        setContent { VeridexTheme { VeridexApp() } }
    }
}

@Composable fun VeridexApp(model: AppModel = viewModel()) {
    var screen by rememberSaveable { mutableStateOf("home") }
    var caseId by rememberSaveable { mutableStateOf<String?>(null) }
    var photoPath by rememberSaveable { mutableStateOf("") }
    var photoSource by rememberSaveable { mutableStateOf("camera") }
    var attachId by rememberSaveable { mutableStateOf<String?>(null) }
    var language by rememberSaveable { mutableStateOf(model.store.language) }
    var onboarding by rememberSaveable { mutableStateOf(!model.store.onboardingComplete) }
    val cases by model.cases.collectAsStateWithLifecycle()
    val busy by model.busy.collectAsStateWithLifecycle()
    val message by model.message.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(message) { message?.let { snackbar.showSnackbar(it); model.clearMessage() } }
    fun goBack() { screen = when (screen) { "confirm" -> "camera"; "camera" -> if (attachId == null) "home" else "detail"; "detail" -> "cases"; else -> "home" } }
    BackHandler(screen != "home") { goBack() }
    fun capture(id: String?) { attachId = id; photoPath = ""; photoSource = "camera"; screen = "camera" }
    val topLevel = screen in listOf("home", "cases", "map", "settings")
    CompositionLocalProvider(LocalCopy provides Copy(language)) {
    if (onboarding) OnboardingScreen(language, { language = it; model.store.language = it }) { model.store.onboardingComplete = true; onboarding = false }
    else Scaffold(containerColor = Ink, snackbarHost = { SnackbarHost(snackbar) }, bottomBar = {
        if (topLevel) NavigationBar(containerColor = Ink, tonalElevation = 0.dp) {
            listOf(Triple("home", tr("overview"), Icons.Outlined.GridView), Triple("cases", tr("cases"), Icons.Outlined.FolderOpen), Triple("map", tr("map"), Icons.Outlined.Map), Triple("settings", tr("settings"), Icons.Outlined.Tune)).forEach { (route, label, icon) ->
                NavigationBarItem(selected = screen == route, onClick = { screen = route }, icon = { Icon(icon, label) }, label = { Text(label) }, colors = NavigationBarItemDefaults.colors(selectedIconColor = Mint, selectedTextColor = Mint, indicatorColor = Panel, unselectedIconColor = Muted, unselectedTextColor = Muted))
            }
        }
    }) { insets ->
        Box(Modifier.fillMaxSize().padding(insets)) {
            when (screen) {
                "home" -> HomeScreen(cases.filterNot { it.archived }, model.store.draft, { capture(null) }, {
                    model.store.draft?.let { draft -> photoPath = draft.path; photoSource = draft.source; attachId = draft.existingCaseId; screen = "confirm" }
                }, { model.discardDraft() }, { caseId = it; screen = "detail" }, { screen = "cases" }, { screen = "demo" })
                "cases" -> CasesScreen(cases, { capture(null) }, { caseId = it; screen = "detail" })
                "map" -> MapScreen(cases) { caseId = it; screen = "detail" }
                "settings" -> ConnectionScreen(model, language, { language = it; model.store.language = it }, { onboarding = true })
                "camera" -> CaptureScreen(attachId?.let { id -> cases.find { it.id == id } }, { goBack() }, { path, source -> photoPath = path; photoSource = source; model.beginDraft(path, attachId, source); screen = "confirm" }, model::notify)
                "confirm" -> ConfirmScreen(photoPath, photoSource, attachId?.let { id -> cases.find { it.id == id } }, busy, { goBack() }, model::notify) { location, note, region, latitude, longitude, accuracy ->
                    model.save(photoPath, location, note, region, attachId, photoSource, latitude, longitude, accuracy) { caseId = it; screen = "detail" }
                }
                "detail" -> cases.find { it.id == caseId }?.let { item ->
                    DetailScreen(item, busy, { goBack() }, { capture(item.id) }, { model.upload(item.id) }, { model.review(item.id) }, { model.rename(item.id, it) }, { model.archive(item.id) }, { model.delete(item.id); screen = "cases" }, { model.remind(item.id, it) })
                }
                "demo" -> DemoScreen { goBack() }
            }
        }
    }
    }
}
