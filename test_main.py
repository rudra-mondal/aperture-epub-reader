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

class TestSplitIntoSentences(unittest.TestCase):
    def setUp(self):
        # We don't really need to instantiate EpubReader if we call the method on the class
        # But let's see if we can instantiate it with mocks
        try:
            self.reader = EpubReader()
        except Exception:
            # If instantiation fails due to some complex PyQt logic, we'll use None as self
            self.reader = EpubReader
            pass

    def test_empty_string(self):
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, ""), [])
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, None), [])

    def test_single_sentence(self):
        text = "This is a single sentence."
        expected = ["This is a single sentence."]
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, text), expected)

    def test_multiple_sentences_period(self):
        text = "First sentence. Second sentence. Third sentence."
        expected = ["First sentence.", "Second sentence.", "Third sentence."]
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, text), expected)

    def test_multiple_sentences_mixed_punctuation(self):
        text = "Is this a question? Yes, it is! Awesome."
        expected = ["Is this a question?", "Yes, it is!", "Awesome."]
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, text), expected)

    def test_multiple_spaces(self):
        text = "Sentence one.    Sentence two. \t Sentence three."
        expected = ["Sentence one.", "Sentence two.", "Sentence three."]
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, text), expected)

    def test_no_trailing_punctuation(self):
        text = "This sentence has no punctuation"
        expected = ["This sentence has no punctuation"]
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, text), expected)

    def test_extra_whitespace_around(self):
        text = "  \n  First. Second. \n "
        expected = ["First.", "Second."]
        self.assertEqual(EpubReader._split_into_sentences(EpubReader, text), expected)


if __name__ == '__main__':
    unittest.main()
