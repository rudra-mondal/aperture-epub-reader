import sys
import os
import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import base64
import urllib.parse

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, 
                             QFileDialog, QStackedWidget, QLabel, QSplitter)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import Qt, QUrl, QEvent, pyqtSignal
from PyQt6.QtGui import QDesktopServices # NEW: For opening external links

# --- Constants ---
LIBRARY_FILE = "library.json"

# --- Main Application Window ---
class EpubReader(QMainWindow):
    
    # --- NEW: Custom Web Engine Page for Link Handling ---
    class CustomWebEnginePage(QWebEnginePage):
        # Signal to request loading an internal chapter by its spine index
        internal_link_clicked = pyqtSignal(int)

        def __init__(self, parent, href_map):
            super().__init__(parent)
            self.href_map = href_map

        def acceptNavigationRequest(self, url, _type, isMainFrame):
            # We only care about clicks on links
            if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                scheme = url.scheme()
                
                # Case 1: External Link (e.g., http, https)
                if scheme in ['http', 'https']:
                    QDesktopServices.openUrl(url)
                    return False # Tell the view not to handle it
                
                # Case 2: Internal Link
                # The path might have a leading slash, remove it for lookup
                path = url.path().lstrip('/')
                
                # Find the target chapter in our href->index map
                if path in self.href_map:
                    self.internal_link_clicked.emit(self.href_map[path])
                    return False # We handled it, so stop the view from navigating

            # For all other cases (initial load, etc.), allow navigation
            return True
    # --- END of Custom Class ---


    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aperture EPUB Reader")
        self.setGeometry(100, 100, 1200, 800)

        # Data Members
        self.library_data = {}
        self.current_book = None
        self.current_book_path = ""
        self.spine = []
        self.href_map = {}
        self.items_by_href = {}
        self.current_chapter_index = 0

        # UI Setup
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)
        self.setup_library_view()
        self.setup_reading_view() # This will now use the custom page
        self.load_library()
        self.central_widget.setCurrentWidget(self.library_view_widget)

    def keyPressEvent(self, event: QEvent):
        # This function remains unchanged
        if self.central_widget.currentWidget() == self.reading_view_widget:
            if event.key() == Qt.Key.Key_Right: self.next_chapter()
            elif event.key() == Qt.Key.Key_Left: self.prev_chapter()
        super().keyPressEvent(event)

    def setup_library_view(self):
        # This function remains unchanged
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
        # This function is slightly modified to use the custom page
        self.reading_view_widget = QWidget()
        main_layout = QHBoxLayout(self.reading_view_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Table of Contents Panel (unchanged)
        toc_widget = QWidget()
        toc_layout = QVBoxLayout(toc_widget)
        toc_layout.setContentsMargins(10, 10, 10, 10)
        toc_title = QLabel("Table of Contents")
        toc_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.toc_list = QListWidget()
        self.toc_list.itemClicked.connect(self.toc_item_clicked)
        back_to_library_button = QPushButton("← Back to Library")
        back_to_library_button.clicked.connect(self.show_library_view)
        toc_layout.addWidget(back_to_library_button)
        toc_layout.addWidget(toc_title)
        toc_layout.addWidget(self.toc_list)
        
        # Content Panel
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0,0,0,0)
        content_layout.setSpacing(0)
        
        self.web_view = QWebEngineView()
        
        # --- MODIFICATION: Set our custom page on the web view ---
        # Pass the href_map so the page knows how to resolve internal links
        custom_page = self.CustomWebEnginePage(self.web_view, self.href_map)
        custom_page.internal_link_clicked.connect(self.load_chapter) # Connect signal to our method
        self.web_view.setPage(custom_page)
        # --- END OF MODIFICATION ---
        
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        
        # Navigation buttons (unchanged)
        nav_layout = QHBoxLayout()
        prev_button = QPushButton("‹ Previous")
        prev_button.clicked.connect(self.prev_chapter)
        next_button = QPushButton("Next ›")
        next_button.clicked.connect(self.next_chapter)
        nav_layout.addWidget(prev_button)
        nav_layout.addStretch()
        nav_layout.addWidget(next_button)
        
        content_layout.addWidget(self.web_view)
        content_layout.addLayout(nav_layout)
        
        splitter.addWidget(toc_widget)
        splitter.addWidget(content_widget)
        splitter.setSizes([300, 900])
        main_layout.addWidget(splitter)
        self.central_widget.addWidget(self.reading_view_widget)

    def open_book_from_library(self, item):
        # --- MODIFICATION: Update the href_map on the custom page when a new book is opened ---
        book_id = item.data(Qt.ItemDataRole.UserRole)
        book_data = self.library_data[book_id]
        self.current_book_path = book_data['path']
        try:
            self.current_book = epub.read_epub(self.current_book_path)
            self.spine = self.current_book.spine
            
            self.href_map = {item.get_name(): i for i, item_id in enumerate(self.spine) if (item := self.current_book.get_item_with_id(item_id[0]))}
            self.items_by_href = {item.get_name(): item for item in self.current_book.get_items()}
            
            # CRITICAL: Update the map in our existing custom page object
            self.web_view.page().href_map = self.href_map

            self.populate_toc()
            self.current_chapter_index = book_data.get('last_position', 0)
            self.load_chapter(self.current_chapter_index)
            self.central_widget.setCurrentWidget(self.reading_view_widget)
        except Exception as e:
            print(f"Error opening book: {e}")
    
    # --- All other methods below remain unchanged ---

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
                if book.get_metadata('DC', 'title'): title = book.get_metadata('DC', 'title')[0][0]
                book_id = os.path.basename(file_path)
                if book_id not in self.library_data:
                    self.library_data[book_id] = {"path": file_path, "title": title, "last_position": 0}
                    self.save_library()
                    self.update_library_list()
            except Exception as e: print(f"Error adding book: {e}")

    def update_library_list(self):
        self.library_list.clear()
        for book_id, data in self.library_data.items():
            item = QListWidgetItem(data['title'])
            item.setData(Qt.ItemDataRole.UserRole, book_id)
            self.library_list.addItem(item)
            
    def show_library_view(self):
        self.central_widget.setCurrentWidget(self.library_view_widget)

    def populate_toc(self):
        self.toc_list.clear()
        if not self.current_book: return
        for toc_item in self.current_book.toc: self._add_toc_item(toc_item)

    def _add_toc_item(self, toc_item, level=0):
        if isinstance(toc_item, tuple):
            link, children = toc_item
            self._add_link_to_toc(link, level)
            for child in children: self._add_toc_item(child, level + 1)
        else: self._add_link_to_toc(toc_item, level)

    def _add_link_to_toc(self, link, level):
        indent = "    " * level
        item = QListWidgetItem(indent + link.title)
        href = link.href.split('#')[0]
        if href in self.href_map:
            index = self.href_map[href]
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.toc_list.addItem(item)
    
    def toc_item_clicked(self, item):
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is not None: self.load_chapter(index)

    def load_chapter(self, index):
        if not (0 <= index < len(self.spine)): return
        self.current_chapter_index = index
        item_id = self.spine[index][0]
        chapter_item = self.current_book.get_item_with_id(item_id)
        if not chapter_item: return
        html_content = chapter_item.get_content().decode('utf-8', 'ignore')
        soup = BeautifulSoup(html_content, 'html.parser')
        for img_tag in soup.find_all('img'):
            img_src = img_tag.get('src')
            if not img_src: continue
            base_path = chapter_item.get_name()
            img_path = urllib.parse.urljoin(base_path, urllib.parse.unquote(img_src))
            if img_path in self.items_by_href:
                img_item = self.items_by_href[img_path]
                img_data = img_item.get_content()
                mime_type = self._get_mime_type(img_item.get_name())
                base64_data = base64.b64encode(img_data).decode('utf-8')
                img_tag['src'] = f"data:{mime_type};base64,{base64_data}"
        for s in soup(['style', 'link']): s.decompose()
        style_tag = soup.new_tag('style')
        style_tag.string = """
            body { font-family: 'Georgia', serif; line-height: 1.6; font-size: 18px; 
                   padding: 2em; background-color: #fdf6e3; color: #586e75; max-width: 800px; margin: 0 auto; }
            h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: bold; color: #073642; }
            img, svg { max-width: 100%; height: auto; display: block; margin: 1em auto; border-radius: 5px; }
        """
        soup.head.append(style_tag)
        self.web_view.setHtml(str(soup))
        self.save_progress()
        self.update_toc_selection()
    
    def _get_mime_type(self, filename):
        if filename.lower().endswith(('.jpg', '.jpeg')): return 'image/jpeg'
        if filename.lower().endswith('.png'): return 'image/png'
        if filename.lower().endswith('.gif'): return 'image/gif'
        if filename.lower().endswith(('.svg', '.svgz')): return 'image/svg+xml'
        return 'application/octet-stream'

    def next_chapter(self):
        if self.current_chapter_index < len(self.spine) - 1: self.load_chapter(self.current_chapter_index + 1)

    def prev_chapter(self):
        if self.current_chapter_index > 0: self.load_chapter(self.current_chapter_index - 1)

    def save_progress(self):
        if self.current_book_path:
            book_id = os.path.basename(self.current_book_path)
            if book_id in self.library_data:
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
                
    def closeEvent(self, event):
        self.save_progress()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    reader = EpubReader()
    reader.show()
    sys.exit(app.exec())