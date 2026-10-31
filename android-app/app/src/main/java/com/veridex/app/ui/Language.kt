package com.veridex.app.ui

import androidx.compose.runtime.*

class Copy(private val language: String) {
    private val values = mapOf(
        "en" to mapOf("overview" to "Overview", "cases" to "My cases", "map" to "Map", "settings" to "Settings", "capture" to "Capture a pothole", "resume" to "Resume draft", "welcome" to "A photo starts it.\nProof completes it.", "start" to "Get started", "next" to "Next", "skip" to "Skip", "language" to "Language", "search" to "Search cases", "new_case" to "New case", "save" to "Save evidence", "camera" to "Camera", "location" to "Location", "review" to "Human review"),
        "kn" to mapOf("overview" to "ಮುಖಪುಟ", "cases" to "ನನ್ನ ಪ್ರಕರಣಗಳು", "map" to "ನಕ್ಷೆ", "settings" to "ಸೆಟ್ಟಿಂಗ್‌ಗಳು", "capture" to "ಗುಂಡಿಯ ಚಿತ್ರ ತೆಗೆಯಿರಿ", "resume" to "ಕರಡು ಮುಂದುವರಿಸಿ", "welcome" to "ಚಿತ್ರದಿಂದ ಆರಂಭ.\nಸಾಕ್ಷ್ಯದಿಂದ ಪೂರ್ಣ.", "start" to "ಪ್ರಾರಂಭಿಸಿ", "next" to "ಮುಂದೆ", "skip" to "ಬಿಟ್ಟುಬಿಡಿ", "language" to "ಭಾಷೆ", "search" to "ಪ್ರಕರಣ ಹುಡುಕಿ", "new_case" to "ಹೊಸ ಪ್ರಕರಣ", "save" to "ಸಾಕ್ಷ್ಯ ಉಳಿಸಿ", "camera" to "ಕ್ಯಾಮೆರಾ", "location" to "ಸ್ಥಳ", "review" to "ಮಾನವ ಪರಿಶೀಲನೆ"),
        "hi" to mapOf("overview" to "होम", "cases" to "मेरे मामले", "map" to "नक्शा", "settings" to "सेटिंग", "capture" to "गड्ढे की फोटो लें", "resume" to "ड्राफ्ट जारी रखें", "welcome" to "फोटो से शुरुआत।\nसबूत से पूर्णता।", "start" to "शुरू करें", "next" to "आगे", "skip" to "छोड़ें", "language" to "भाषा", "search" to "मामले खोजें", "new_case" to "नया मामला", "save" to "सबूत सहेजें", "camera" to "कैमरा", "location" to "स्थान", "review" to "मानव समीक्षा")
    )
    fun get(key: String) = values[language]?.get(key) ?: values.getValue("en")[key] ?: key
}
val LocalCopy = staticCompositionLocalOf { Copy("en") }
@Composable fun tr(key: String) = LocalCopy.current.get(key)
