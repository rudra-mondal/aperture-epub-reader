<p align="center"><img width="128" height="128" alt="Aperture logo" src="https://github.com/user-attachments/assets/ca4671d7-e745-4efd-9e88-2911afe9def9" /></p>

# Aperture EPUB Reader

**Aperture is a modern, feature-rich desktop EPUB reader built with Python and PyQt6, focusing on a clean reading experience and powerful, integrated [Kokoro](https://github.com/hexgrad/kokoro) Text-to-Speech (TTS) capabilities.**

Aperture allows you to manage a local library of EPUB files, read them in a beautifully styled, distraction-free view, and listen to your books with high-quality, natural-sounding voices. Its core strength lies in its intelligent TTS engine that highlights text as it's spoken, providing an immersive read-aloud experience.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/Qt-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)

---

<h3 align="center"><i>👇 Here is a quick look 👇</i></h3>

<p align="center">
<img width="800" alt="Screenshot 2025-08-01 175219" src="https://github.com/user-attachments/assets/36f94e76-79a2-43b4-b756-28a16ee62117" />
</p>

<h4 align="center"><i>Aperture's main reading interface</i></h4>

## ✨ Key Features

Aperture is more than just a file viewer; it's a complete reading environment.

#### 📚 Library Management
- **Persistent Library:** Your collection of books is saved locally in a `library.json` file, so they're always there when you open the app.
- **Easy Import:** Add new `.epub` files to your library with a simple file dialog.
- **Progress Saving:** Aperture automatically remembers the last chapter you were reading for each book and returns you to it.

#### 📖 Core Reading Experience
- **Clean, Customizable UI:** A clutter-free reading pane with custom styling for comfortable, long-form reading.
- **Table of Contents (TOC):** Easily navigate your book with a clickable, hierarchical TOC.
- **Chapter Navigation:** Move between chapters using "Next" and "Previous" buttons or the `Left` and `Right` arrow keys.
- **Image & Link Handling:**
    - Properly displays embedded images from the EPUB file.
    - Internal links (e.g., footnotes) navigate within the app.
    - External web links open securely in your system's default browser.

#### 🔊 Advanced Text-to-Speech (TTS)
- **High-Quality Voices:** Powered by the `kokoro-tts` library, offering a selection of natural-sounding male and female voices (US & UK accents).
- **Real-time Sentence Highlighting:** The exact sentence being read is highlighted in the reader view, helping you follow along.
- **Smooth Scrolling:** The view automatically scrolls to keep the highlighted sentence in focus.
- **Playback Controls:** Full control with **Play/Pause/Resume** and **Stop** functionality.
- **Adjustable Speed:** Fine-tune the reading speed from 0.5x to 2.0x to match your preference.

#### 🧠 Smart Content Handling
- **Intelligent Text Preparation:** Before TTS, the text is processed for better pronunciation:
    - **Links:** URLs like `https://example.com` are read as "example dot com".
    - **Acronyms:** Common acronyms (e.g., NASA, FBI) are preserved, while other all-caps phrases are converted to title case to avoid unnatural shouting.
    - **Special Characters:** Symbols like `>` or `-` are verbalized (e.g., "is greater than", "minus").
- **Robust & Responsive:** TTS processing runs in a separate thread, ensuring the application UI remains fast and responsive at all times, even when generating audio for long chapters.

---

## 🛠️ Installation

Follow these steps to get Aperture running on your local machine.

#### Prerequisites
- **Python 3.9+**
- **Git**

#### 1. Clone the Repository
First, clone the project from GitHub:
```bash
git clone https://github.com/rudra-mondal/aperture-epub-reader.git
cd aperture-epub-reader
```

#### 2. Create a Virtual Environment (Recommended)
It's best practice to create a virtual environment to manage project dependencies.
```bash
# On macOS and Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
.\venv\Scripts\activate
```

#### 3. Install Dependencies
Install all the required Python libraries using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```
> **Note on PyTorch:** The `kokoro-tts` library depends on PyTorch. The command above will install the standard CPU version. If you have a compatible NVIDIA GPU and want to leverage it, you may need to install a specific version of PyTorch by following the official instructions at [pytorch.org](https://pytorch.org/get-started/locally/).

---

## 🚀 Usage

1.  **Run the application:**
    ```bash
    python main.py
    ```

2.  **Add a Book:**
    - On the "My Library" screen, click the "Add Book to Library" button.
    - Select a `.epub` file from your computer.

3.  **Open a Book:**
    - Double-click on any book title in your library to open the reading view.

4.  **Read and Navigate:**
    - Use the Table of Contents on the left to jump to specific chapters.
    - Use the "Next" / "Previous" buttons or the `Left` / `Right` arrow keys to move between chapters.

5.  **Use Text-to-Speech:**
    - **Select Voice & Speed:** Choose your desired voice and playback speed from the control bar at the bottom.
    - **▶ Read Aloud:** Click this to start the TTS. The button will change to "❚❚ Pause".
    - **❚❚ Pause / ▶ Resume:** Click to pause or resume playback.
    - **■ Stop:** Click to stop playback completely and reset the TTS.

---

## 🔧 Technical Deep Dive

- **Framework:** The application is built with **PyQt6**, a comprehensive set of Python bindings for Qt v6.
- **UI Structure:**
    - A `QStackedWidget` is used to switch between the main library view and the reader view.
    - The reader view uses a `QSplitter` to provide a resizable pane for the TOC and the content.
- **EPUB Parsing:** The **`ebooklib`** library is used to parse `.epub` files, extract content, metadata, images, and the table of contents.
- **Content Rendering:**
    - Chapter content (XHTML) is rendered in a **`QWebEngineView`** (based on the Chromium engine).
    - Before rendering, the HTML is processed with **`BeautifulSoup4`** to:
        - Inject custom CSS for styling.
        - Embed images as base64 data URIs to make them self-contained.
        - Wrap each sentence in a `<span id="tts-sentence-X">...</span>` tag. This ID is the key to enabling the real-time highlighting feature.
- **TTS Architecture (Producer-Consumer Model):**
    - To prevent the UI from freezing during audio generation, TTS operates on a background `QThread`.
    - **`TTSWorker` (Producer):** This object runs on the background thread. It iterates through the prepared text chunks, uses `kokoro-tts` to generate audio data, and puts the audio (`numpy` array) and its corresponding sentence ID into a shared `queue.Queue`.
    - **`TTSWorker` (Consumer):** The main loop of the worker's `run` method retrieves audio chunks from the queue. It emits a signal to the main thread to highlight the new sentence ID, then plays the audio using **`sounddevice`**. This model ensures a smooth, continuous stream of audio and highlighting.

---

## 🤝 Contributing

Contributions are welcome! If you have ideas for new features, bug fixes, or improvements, please feel free to:
1.  **Fork** the repository.
2.  Create a new **branch** (`git checkout -b feature/YourAmazingFeature`).
3.  **Commit** your changes (`git commit -m 'Add some AmazingFeature'`).
4.  **Push** to the branch (`git push origin feature/YourAmazingFeature`).
5.  Open a **Pull Request**.

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

This project would not be possible without the incredible open-source libraries it's built upon:
- [PyQt6](https://riverbankcomputing.com/software/pyqt/)
- [kokoro-tts](https://github.com/TaylorAI/kokoro-tts)
- [ebooklib](https://github.com/aerkalov/ebooklib)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [NumPy](https://numpy.org/)
- [SoundDevice](https://python-sounddevice.readthedocs.io/)

---
