import sys
import os
import json
import re
import time
import traceback
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import base64
import urllib.parse

# --- TTS & Audio Imports ---
import torch
from kokoro import KPipeline
import sounddevice as sd
import numpy as np
import queue
import threading


from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
                             QFileDialog, QStackedWidget, QLabel, QSplitter,
                             QComboBox, QSlider, QMessageBox, QFrame)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import Qt, QUrl, QEvent, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QDesktopServices

# --- Constants ---
LIBRARY_FILE = "library.json"

ALL_VOICES_DATA = {
    "af_alloy": {"name": "Alloy (US Female)", "lang_code": "a"},
    "af_heart": {"name": "Heart (US Female)", "lang_code": "a"},
    "af_nova": {"name": "Nova (US Female)", "lang_code": "a"},
    "am_echo": {"name": "Echo (US Male)", "lang_code": "a"},
    "am_onyx": {"name": "Onyx (US Male)", "lang_code": "a"},
    "bf_fable": {"name": "Fable (UK Female)", "lang_code": "b"},
    "bm_lewis": {"name": "Lewis (UK Male)", "lang_code": "b"},
}
DEFAULT_VOICE_KEY = "af_heart"
KOKORO_SAMPLE_RATE = 24000

# --- TTS Worker (Producer-Consumer Model) ---
class TTSWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    highlight_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pipeline = None
        self.tts_text_map = []
        self.voice = ""
        self.speed = 1.0
        self._is_running = False
        self._is_paused = False
        self.audio_queue = queue.Queue(maxsize=10)

    def configure(self, pipeline, tts_text_map, voice, speed):
        self.pipeline = pipeline
        self.tts_text_map = tts_text_map
        self.voice = voice
        self.speed = speed

    def _producer(self):
        try:
            for chunk_id, text_to_speak in self.tts_text_map:
                if not self._is_running:
                    break
                generator = self.pipeline(text_to_speak, voice=self.voice, speed=self.speed)
                for _, _, audio_chunk in generator:
                    if not self._is_running:
                        break
                    if audio_chunk is not None:
                        self.audio_queue.put((chunk_id, np.asarray(audio_chunk)))
                if not self._is_running:
                    break
        except Exception as e:
            traceback.print_exc()
            self.error.emit(f"Error during TTS generation: {e}")
        finally:
            self.audio_queue.put((None, None))

    def run(self):
        self._is_running = True
        self._is_paused = False
        producer_thread = threading.Thread(target=self._producer)
        producer_thread.daemon = True
        producer_thread.start()

        last_highlighted_id = None
        while self._is_running:
            try:
                chunk_id, chunk_audio = self.audio_queue.get(timeout=1)
                if chunk_id is None:
                    break

                if chunk_id != last_highlighted_id:
                    self.highlight_requested.emit(chunk_id)
                    last_highlighted_id = chunk_id

                while self._is_paused and self._is_running:
                    time.sleep(0.1)

                if not self._is_running:
                    break

                sd.play(chunk_audio, KOKORO_SAMPLE_RATE, blocking=True)
            except queue.Empty:
                if not producer_thread.is_alive():
                    break

        self.highlight_requested.emit(None)
        self._is_running = False
        self.finished.emit()

    def stop(self):
        self._is_running = False
        self._is_paused = False
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        self.audio_queue.put((None, None))
        sd.stop()

    def pause(self):
        self._is_paused = True
        sd.stop()

    def resume(self):
        self._is_paused = False

# --- Main Application Window ---
class EpubReader(QMainWindow):
    class CustomWebEnginePage(QWebEnginePage):
        internal_link_clicked = pyqtSignal(int)
        def __init__(self, parent, href_map):
            super().__init__(parent)
            self.href_map = href_map
        def acceptNavigationRequest(self, url, _type, isMainFrame):
            if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                if (scheme := url.scheme()) in ['http', 'https']:
                    QDesktopServices.openUrl(url)
                    return False
                if (path := url.path().lstrip('/')) in self.href_map:
                    self.internal_link_clicked.emit(self.href_map[path])
                    return False
            return True

    ACRONYMS = {'USA', 'UK', 'EU', 'UN', 'NASA', 'FBI', 'CIA', 'CEO', 'CFO', 'CTO', 'NFL', 'NBA', 'MLB', 'NHL', 'ESPN', 'NATO', 'UNESCO', 'WHO', 'FAQ', 'DIY', 'AI', 'VR', 'AR', 'URL', 'HTTP', 'HTTPS', 'WWW', 'PDF', 'EPUB'}

    def _split_into_sentences(self, text):
        if not text:
            return []
        sentences = re.split(r'(?<=[.?!])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def _prepare_content_for_tts(self, soup):
        if not (body := soup.find('body')):
            return []
        
        tts_text_map = []
        sentence_index = 0
        
        for element in body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote']):
            # FIX: Use separator=" " to preserve spaces between inline tags like <b> and <i>.
            original_text = element.get_text(separator=" ", strip=True)
            if not original_text:
                continue

            sentences = self._split_into_sentences(original_text)
            
            if sentences:
                element.clear()
                
                for sentence_text in sentences:
                    sentence_id = f"tts-sentence-{sentence_index}"
                    
                    formatted_text = self._pronounce_links(sentence_text)
                    formatted_text = self._pronounce_special_chars(formatted_text)
                    formatted_text = self._handle_uppercase_phrases(formatted_text)
                    
                    if formatted_text:
                        tts_text_map.append((sentence_id, formatted_text))
                        
                        span_tag = soup.new_tag('span', id=sentence_id)
                        span_tag.string = sentence_text + " "
                        element.append(span_tag)
                        
                        sentence_index += 1
                        
        return tts_text_map

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aperture EPUB Reader")
        self.setGeometry(100, 100, 1200, 800)
        
        self.library_data = {}
        self.current_book = None
        self.current_book_path = ""
        self.spine = []
        self.href_map = {}
        self.items_by_href = {}
        self.current_chapter_index = 0
        
        self.kokoro_pipelines = {}
        self.tts_thread = None
        self.tts_worker = None
        self.is_tts_paused = False
        self.tts_text_map = []
        self.last_highlighted_id = None
        
        self.initialize_kokoro()
        
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)
        self.setup_library_view()
        self.setup_reading_view()
        self.load_library()
        self.central_widget.setCurrentWidget(self.library_view_widget)

    def keyPressEvent(self, event: QEvent):
        """Handle key presses for chapter navigation."""
        # This event is only processed when the reading view is active.
        if self.central_widget.currentWidget() == self.reading_view_widget:
            key = event.key()
            if key == Qt.Key.Key_Right:
                self.next_chapter()
            elif key == Qt.Key.Key_Left:
                self.prev_chapter()

        # Call the base class implementation to handle other keys.
        super().keyPressEvent(event)

    def setup_library_view(self):
        self.library_view_widget = QWidget()
        layout = QVBoxLayout(self.library_view_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("My Library")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        
        self.library_list = QListWidget()
        self.library_list.setStyleSheet("QListWidget { border: 1px solid #ccc; border-radius: 5px; }")
        self.library_list.itemDoubleClicked.connect(self.open_book_from_library)
        
        add_button = QPushButton("Add Book to Library")
        add_button.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        add_button.clicked.connect(self.add_book_to_library)
        
        layout.addWidget(title)
        layout.addWidget(self.library_list)
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.central_widget.addWidget(self.library_view_widget)

    def setup_reading_view(self):
        self.reading_view_widget = QWidget()
        main_layout = QHBoxLayout(self.reading_view_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        toc_widget = QWidget()
        toc_layout = QVBoxLayout(toc_widget)
        toc_title = QLabel("Table of Contents")
        toc_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.toc_list = QListWidget()
        self.toc_list.itemClicked.connect(self.toc_item_clicked)
        back_to_library_button = QPushButton("← Back to Library")
        back_to_library_button.clicked.connect(self.show_library_view)
        toc_layout.addWidget(back_to_library_button)
        toc_layout.addWidget(toc_title)
        toc_layout.addWidget(self.toc_list)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0,0,0,0)
        content_layout.setSpacing(0)
        
        self.web_view = QWebEngineView()
        custom_page = self.CustomWebEnginePage(self.web_view, self.href_map)
        custom_page.internal_link_clicked.connect(self.load_chapter)
        self.web_view.setPage(custom_page)
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        
        control_bar_widget = QWidget()
        control_bar_widget.setStyleSheet("background-color: #f0f0f0; border-top: 1px solid #d0d0d0;")
        controls_layout = QHBoxLayout(control_bar_widget)
        controls_layout.setContentsMargins(5, 3, 5, 3)
        controls_layout.setSpacing(8)

        prev_button = QPushButton("‹ Previous")
        prev_button.clicked.connect(self.prev_chapter)
        next_button = QPushButton("Next ›")
        next_button.clicked.connect(self.next_chapter)

        self.play_pause_button = QPushButton("▶ Read Aloud")
        self.play_pause_button.setFixedWidth(100)
        self.play_pause_button.clicked.connect(self.toggle_read_aloud)
        self.stop_button = QPushButton("■")
        self.stop_button.setFixedWidth(30)
        self.stop_button.clicked.connect(self.stop_read_aloud)
        self.stop_button.setEnabled(False)
        
        self.voice_combo = QComboBox()
        for key, data in ALL_VOICES_DATA.items():
            self.voice_combo.addItem(data['name'], key)
        if (default_idx := self.voice_combo.findData(DEFAULT_VOICE_KEY)) != -1:
            self.voice_combo.setCurrentIndex(default_idx)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 20)
        self.speed_slider.setValue(10)
        self.speed_slider.setFixedWidth(100)
        self.speed_label = QLabel(f"{self.speed_slider.value()/10:.1f}x")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"{v/10:.1f}x"))

        controls_layout.addWidget(prev_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.stop_button)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        controls_layout.addWidget(separator)
        controls_layout.addWidget(QLabel("Voice:"))
        controls_layout.addWidget(self.voice_combo)
        controls_layout.addWidget(self.speed_label)
        controls_layout.addWidget(self.speed_slider)
        controls_layout.addStretch()
        controls_layout.addWidget(next_button)
        
        content_layout.addWidget(self.web_view, 1)
        content_layout.addWidget(control_bar_widget, 0)
        
        splitter.addWidget(toc_widget)
        splitter.addWidget(content_widget)
        splitter.setSizes([300, 900])
        main_layout.addWidget(splitter)
        self.central_widget.addWidget(self.reading_view_widget)

    def toggle_read_aloud(self):
        if self.tts_thread and self.tts_thread.isRunning():
            if self.is_tts_paused:
                self.tts_worker.resume()
                self.play_pause_button.setText("❚❚ Pause")
                self.is_tts_paused = False
            else:
                self.tts_worker.pause()
                self.play_pause_button.setText("▶ Resume")
                self.is_tts_paused = True
            return

        if not self.tts_text_map:
            QMessageBox.information(self, "Nothing to Read", "There is no readable text in the current chapter.")
            return

        voice_key = self.voice_combo.currentData()
        if (lang_code := ALL_VOICES_DATA[voice_key]["lang_code"]) not in self.kokoro_pipelines:
            QMessageBox.critical(self, "TTS Engine Error", f"TTS engine for language '{lang_code}' not loaded.")
            return
            
        self.tts_thread = QThread()
        self.tts_worker = TTSWorker()
        self.tts_worker.highlight_requested.connect(self.update_text_highlight)
        self.tts_worker.configure(self.kokoro_pipelines[lang_code], self.tts_text_map, voice_key, self.speed_slider.value() / 10.0)
        self.tts_worker.moveToThread(self.tts_thread)
        self.tts_thread.started.connect(self.tts_worker.run)
        self.tts_worker.finished.connect(self.on_tts_finished)
        self.tts_worker.error.connect(self.on_tts_error)
        self.tts_thread.start()
        
        self.play_pause_button.setText("❚❚ Pause")
        self.stop_button.setEnabled(True)
        self.voice_combo.setEnabled(False)
        self.speed_slider.setEnabled(False)

    def stop_read_aloud(self):
        if self.tts_worker:
            self.tts_worker.stop()

    def on_tts_finished(self):
        if self.tts_thread and self.tts_thread.isRunning():
            self.tts_thread.quit()
            self.tts_thread.wait()
            
        self.tts_thread = None
        self.tts_worker = None
        self.is_tts_paused = False
        self.update_text_highlight(None)
        
        self.play_pause_button.setText("▶ Read Aloud")
        self.stop_button.setEnabled(False)
        self.voice_combo.setEnabled(True)
        self.speed_slider.setEnabled(True)

    def on_tts_error(self, message):
        QMessageBox.critical(self, "Read Aloud Error", message)
        self.on_tts_finished()

    def update_text_highlight(self, new_id):
        if new_id == self.last_highlighted_id:
            return

        if self.last_highlighted_id:
            js_code_remove = f"document.getElementById('{self.last_highlighted_id}').classList.remove('reading-highlight');"
            self.web_view.page().runJavaScript(js_code_remove)
        
        if new_id:
            # FIX: Wrap JS in a block scope to prevent "Identifier has already been declared" error.
            js_code_add = f"""
                {{
                    let el = document.getElementById('{new_id}');
                    if (el) {{
                        el.classList.add('reading-highlight');
                        el.scrollIntoView({{behavior: 'smooth', block: 'center', inline: 'nearest'}});
                    }}
                }}
            """
            self.web_view.page().runJavaScript(js_code_add)
        
        self.last_highlighted_id = new_id

    def load_chapter(self, index):
        self.stop_read_aloud()
        
        if not (0 <= index < len(self.spine)):
            return
            
        self.current_chapter_index = index
        item_id = self.spine[index][0]
        chapter_item = self.current_book.get_item_with_id(item_id)
        if not chapter_item:
            return
        
        html_content = chapter_item.get_content().decode('utf-8', 'ignore')
        soup = BeautifulSoup(html_content, 'html.parser')

        for img_tag in soup.find_all('img'):
            if not (img_src := img_tag.get('src')):
                continue
            img_path = urllib.parse.urljoin(chapter_item.get_name(), urllib.parse.unquote(img_src))
            if img_path in self.items_by_href:
                img_item = self.items_by_href[img_path]
                img_data = img_item.get_content()
                mime = self._get_mime_type(img_item.get_name())
                b64 = base64.b64encode(img_data).decode('utf-8')
                img_tag['src'] = f"data:{mime};base64,{b64}"
        
        for s in soup(['style', 'link', 'script']):
            s.decompose()
        
        self.tts_text_map = self._prepare_content_for_tts(soup)

        style_tag = soup.new_tag('style')
        style_tag.string = """
            body { 
                font-family: 'Georgia', serif; line-height: 1.6; font-size: 18px; 
                padding: 2em; background-color: #fdf6e3; color: #586e75; max-width: 800px; margin: 0 auto;
            }
            h1, h2, h3 { 
                font-family: 'Helvetica Neue', sans-serif; font-weight: bold; color: #073642;
            }
            img, svg { 
                max-width: 100%; height: auto; display: block; margin: 1em auto; border-radius: 5px;
            }
            .reading-highlight { 
                background-color: rgba(255, 229, 102, 0.7);
                transition: background-color 0.3s;
                border-radius: 3px;
            }
        """
        if soup.head:
            soup.head.append(style_tag)
        
        self.web_view.setHtml(str(soup))
        self.save_progress()
        self.update_toc_selection()
        
    def _pronounce_links(self, text):
        def replace_link(match):
            url = match.group(0)
            pronounceable = re.sub(r'^https?://', '', url)
            pronounceable = pronounceable.replace('.', ' dot ').replace('/', ' slash ').replace('-', ' hyphen ').replace('_', ' underscore ')
            return re.sub(r' +', ' ', pronounceable).strip()
        return re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', replace_link, text)

    def _pronounce_special_chars(self, text):
        replacements = {' > ': ' is greater than ', ' < ': ' is less than ', '+': ' plus ', '=': ' equals ', ' - ': ' minus '}
        for char, spoken in replacements.items():
            text = text.replace(char, spoken)
        return text

    def _handle_uppercase_phrases(self, text):
        lines = text.split('\n')
        processed_lines = []
        for line in lines:
            words = line.split(' ')
            uppercase_words = [w for w in words if w.isupper() and len(w) > 1]
            if len(uppercase_words) > 2:
                processed_words = []
                for word in words:
                    clean_word = re.sub(r'[.,!?;:]$', '', word)
                    if clean_word.isupper() and len(clean_word) > 1 and clean_word not in self.ACRONYMS:
                        processed_words.append(word.title())
                    else:
                        processed_words.append(word)
                processed_lines.append(' '.join(processed_words))
            else:
                processed_lines.append(line)
        return '\n'.join(processed_lines)

    def initialize_kokoro(self):
        print("Initializing Kokoro TTS engines...")
        active_lang_codes = sorted(list(set(v["lang_code"] for v in ALL_VOICES_DATA.values())))
        for lc in active_lang_codes:
            try:
                print(f"Loading pipeline for language code: '{lc}'...")
                self.kokoro_pipelines[lc] = KPipeline(lang_code=lc)
                print(f" -> Pipeline for '{lc}' OK.")
            except Exception as e:
                print(f"ERROR: Failed to initialize Kokoro for lang '{lc}'. Error: {e}")
        print("Kokoro initialization complete.")

    def open_book_from_library(self, item):
        self.stop_read_aloud()
        book_id = item.data(Qt.ItemDataRole.UserRole)
        book_data = self.library_data[book_id]
        self.current_book_path = book_data['path']
        try:
            self.current_book = epub.read_epub(self.current_book_path)
            self.spine = self.current_book.spine
            self.href_map = {item.get_name(): i for i, id in enumerate(self.spine) if (item := self.current_book.get_item_with_id(id[0]))}
            self.items_by_href = {item.get_name(): item for item in self.current_book.get_items()}
            self.web_view.page().href_map = self.href_map
            self.populate_toc()
            self.current_chapter_index = book_data.get('last_position', 0)
            self.load_chapter(self.current_chapter_index)
            self.central_widget.setCurrentWidget(self.reading_view_widget)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open EPUB.\n\nError: {e}")
            print(f"Error: {e}")

    def show_library_view(self):
        self.stop_read_aloud()
        self.central_widget.setCurrentWidget(self.library_view_widget)

    def closeEvent(self, event):
        self.stop_read_aloud()
        self.save_progress()
        event.accept()

    def load_library(self):
        if os.path.exists(LIBRARY_FILE):
            with open(LIBRARY_FILE, 'r') as f:
                self.library_data = json.load(f)
        self.update_library_list()

    def save_library(self):
        with open(LIBRARY_FILE, 'w') as f:
            json.dump(self.library_data, f, indent=4)

    def add_book_to_library(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Add EPUB", "", "EPUB Files (*.epub)")
        if file_path:
            try:
                book = epub.read_epub(file_path)
                title = "Unknown Title"
                if book.get_metadata('DC', 'title'):
                    title = book.get_metadata('DC', 'title')[0][0]
                book_id = os.path.basename(file_path)
                if book_id not in self.library_data:
                    self.library_data[book_id] = {"path": file_path, "title": title, "last_position": 0}
                    self.save_library()
                    self.update_library_list()
            except Exception as e:
                print(f"Error adding book: {e}")

    def update_library_list(self):
        self.library_list.clear()
        for book_id, data in self.library_data.items():
            item = QListWidgetItem(data['title'])
            item.setData(Qt.ItemDataRole.UserRole, book_id)
            self.library_list.addItem(item)

    def populate_toc(self):
        self.toc_list.clear()
        if not self.current_book:
            return
        for toc_item in self.current_book.toc:
            self._add_toc_item(toc_item)

    def _add_toc_item(self, toc_item, level=0):
        if isinstance(toc_item, tuple):
            link, children = toc_item
            self._add_link_to_toc(link, level)
            for child in children:
                self._add_toc_item(child, level + 1)
        else:
            self._add_link_to_toc(toc_item, level)

    def _add_link_to_toc(self, link, level):
        item = QListWidgetItem("    " * level + link.title)
        href = link.href.split('#')[0]
        if href in self.href_map:
            item.setData(Qt.ItemDataRole.UserRole, self.href_map[href])
            self.toc_list.addItem(item)

    def toc_item_clicked(self, item):
        if (index := item.data(Qt.ItemDataRole.UserRole)) is not None:
            self.load_chapter(index)

    def _get_mime_type(self, filename):
        fn_lower = filename.lower()
        if fn_lower.endswith(('.jpg', '.jpeg')): return 'image/jpeg'
        if fn_lower.endswith('.png'): return 'image/png'
        if fn_lower.endswith('.gif'): return 'image/gif'
        if fn_lower.endswith(('.svg', '.svgz')): return 'image/svg+xml'
        return 'application/octet-stream'

    def next_chapter(self):
        if self.current_chapter_index < len(self.spine) - 1:
            self.load_chapter(self.current_chapter_index + 1)

    def prev_chapter(self):
        if self.current_chapter_index > 0:
            self.load_chapter(self.current_chapter_index - 1)

    def save_progress(self):
        if self.current_book_path:
            if (book_id := os.path.basename(self.current_book_path)) in self.library_data:
                self.library_data[book_id]['last_position'] = self.current_chapter_index
                self.save_library()

    def update_toc_selection(self):
        self.toc_list.setCurrentRow(-1)
        for i in range(self.toc_list.count()):
            item = self.toc_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.current_chapter_index:
                item.setSelected(True)
                self.toc_list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
                break

if __name__ == "__main__":
    app = QApplication(sys.argv)
    reader = EpubReader()
    reader.show()
    sys.exit(app.exec())