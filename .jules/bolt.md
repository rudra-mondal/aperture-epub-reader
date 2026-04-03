## 2025-02-12 - [Eager ML Model Initialization]
**Learning:** Eagerly initializing machine learning models (like Kokoro TTS pipelines) on application startup blocks the main UI thread, slowing down startup time significantly, and wastes memory for models that might not be used.
**Action:** Use lazy initialization for heavy ML models. Instantiate them only when the user explicitly requests the feature (e.g., clicking "Read Aloud") to improve app startup time and reduce base memory footprint.
