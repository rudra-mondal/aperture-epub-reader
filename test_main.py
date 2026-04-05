import sys
from unittest.mock import MagicMock

# Mocking dependencies
mock_modules = [
    'ebooklib', 'ebooklib.epub', 'bs4', 'torch', 'kokoro', 'sounddevice', 'numpy',
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
    'PyQt6.QtCore', 'PyQt6.QtGui'
]

for module in mock_modules:
    sys.modules[module] = MagicMock()

# Specifically mock some classes that might be used for inheritance or as base classes
class MockQObject:
    def __init__(self, *args, **kwargs): pass
sys.modules['PyQt6.QtCore'].QObject = MockQObject
sys.modules['PyQt6.QtCore'].pyqtSignal = MagicMock

class MockQMainWindow:
    def __init__(self, *args, **kwargs): pass
sys.modules['PyQt6.QtWidgets'].QMainWindow = MockQMainWindow

class MockQWebEnginePage:
    def __init__(self, *args, **kwargs): pass
sys.modules['PyQt6.QtWebEngineCore'].QWebEnginePage = MockQWebEnginePage

# Now import the class to test
from main import EpubReader
import unittest

class TestPronounceSpecialChars(unittest.TestCase):
    def setUp(self):
        # We don't really need to instantiate EpubReader if we call the method on the class
        # But let's see if we can instantiate it with mocks
        try:
            self.reader = EpubReader()
        except Exception:
            # If instantiation fails due to some complex PyQt logic, we'll use None as self
            self.reader = None

    def test_greater_than(self):
        text = "a > b"
        expected = "a is greater than b"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_greater_than_no_spaces(self):
        text = "a>b"
        expected = "a>b"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_less_than(self):
        text = "a < b"
        expected = "a is less than b"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_less_than_no_spaces(self):
        text = "a<b"
        expected = "a<b"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_plus(self):
        text = "1+1"
        expected = "1 plus 1"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_equals(self):
        text = "1=1"
        expected = "1 equals 1"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_minus(self):
        text = "5 - 3"
        expected = "5 minus 3"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_minus_no_spaces(self):
        text = "5-3"
        expected = "5-3"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_mixed(self):
        text = "1 + 1 = 2 > 0"
        # Since replacements are literal, "1 + 1" becomes "1  plus  1"
        expected = "1  plus  1  equals  2 is greater than 0"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_no_special_chars(self):
        text = "hello world"
        expected = "hello world"
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_empty_string(self):
        text = ""
        expected = ""
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

    def test_multiple_occurrences(self):
        text = "+ and + and ="
        expected = " plus  and  plus  and  equals "
        self.assertEqual(EpubReader._pronounce_special_chars(self.reader, text), expected)

class TestGetMimeType(unittest.TestCase):
    def setUp(self):
        try:
            self.reader = EpubReader()
        except Exception:
            self.reader = None

    def test_jpeg(self):
        self.assertEqual(EpubReader._get_mime_type(self.reader, "image.jpg"), "image/jpeg")
        self.assertEqual(EpubReader._get_mime_type(self.reader, "image.jpeg"), "image/jpeg")

    def test_png(self):
        self.assertEqual(EpubReader._get_mime_type(self.reader, "image.png"), "image/png")

    def test_gif(self):
        self.assertEqual(EpubReader._get_mime_type(self.reader, "image.gif"), "image/gif")

    def test_svg(self):
        self.assertEqual(EpubReader._get_mime_type(self.reader, "image.svg"), "image/svg+xml")
        self.assertEqual(EpubReader._get_mime_type(self.reader, "image.svgz"), "image/svg+xml")

    def test_case_insensitive(self):
        self.assertEqual(EpubReader._get_mime_type(self.reader, "IMAGE.JPG"), "image/jpeg")
        self.assertEqual(EpubReader._get_mime_type(self.reader, "image.PNG"), "image/png")

    def test_fallback(self):
        self.assertEqual(EpubReader._get_mime_type(self.reader, "document.pdf"), "application/octet-stream")
        self.assertEqual(EpubReader._get_mime_type(self.reader, "archive.zip"), "application/octet-stream")
        self.assertEqual(EpubReader._get_mime_type(self.reader, "no_extension_file"), "application/octet-stream")


if __name__ == '__main__':
    unittest.main()
