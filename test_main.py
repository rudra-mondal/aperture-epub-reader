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
        try:
            self.reader = EpubReader()
        except Exception:
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

class TestPronounceLinks(unittest.TestCase):
    def setUp(self):
        # Instead of MagicMock(spec=EpubReader), let's use a simple object that has the _replace_link method
        class SimpleReader:
            def _replace_link(self, match):
                return EpubReader._replace_link(self, match)
        self.reader = SimpleReader()

    def test_http_url(self):
        text = "Visit http://example.com"
        expected = "Visit example dot com"
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_https_url(self):
        text = "Secure site at https://www.example.com"
        expected = "Secure site at www dot example dot com"
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_www_url(self):
        text = "Go to www.example.com"
        expected = "Go to www dot example dot com"
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_url_with_path_and_hyphens(self):
        text = "Read more at https://example.com/my-page/info"
        expected = "Read more at example dot com slash my hyphen page slash info"
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_url_with_underscores(self):
        text = "Check http://example.com/my_page_info"
        expected = "Check example dot com slash my underscore page underscore info"
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_multiple_urls(self):
        text = "Link one: http://example.com and Link two: www.test.org/page"
        expected = "Link one: example dot com and Link two: www dot test dot org slash page"
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_no_urls(self):
        text = "Just some normal text with no links."
        expected = "Just some normal text with no links."
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_empty_string(self):
        text = ""
        expected = ""
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

    def test_url_in_quotes(self):
        text = 'Here is a link "http://example.com".'
        expected = 'Here is a link "example dot com".'
        self.assertEqual(EpubReader._pronounce_links(self.reader, text), expected)

class TestPrepareContentForTTSMocked(unittest.TestCase):
    def test_prepare_content_for_tts_calls_get_text_with_separator(self):
        reader_mock = MagicMock(spec=EpubReader)
        soup_mock = MagicMock()
        body_mock = MagicMock()
        element_mock = MagicMock()

        soup_mock.find.return_value = body_mock
        body_mock.find_all.return_value = [element_mock]

        # Mocking get_text to return a string
        element_mock.get_text.return_value = "Hello world ."

        # Mocking other patterns/methods
        reader_mock.CLEAN_SPACING_PATTERN = EpubReader.CLEAN_SPACING_PATTERN
        reader_mock._split_into_sentences.return_value = ["Hello world."]
        reader_mock._pronounce_links.side_effect = lambda x: x
        reader_mock._pronounce_special_chars.side_effect = lambda x: x
        reader_mock._handle_uppercase_phrases.side_effect = lambda x: x

        EpubReader._prepare_content_for_tts(reader_mock, soup_mock)

        element_mock.get_text.assert_called_with(separator=" ", strip=True)

class TestSanitization(unittest.TestCase):
    def test_sanitize_decomposes_dangerous_tags(self):
        soup_mock = MagicMock()
        dangerous_tag = MagicMock()
        # Mocking soup(dangerous_tags) which is used in _sanitize_soup
        soup_mock.return_value = [dangerous_tag]

        # find_all(True) should return tags to check for attributes
        # We'll return an empty list here to focus on decomposition
        soup_mock.find_all.return_value = []

        EpubReader._sanitize_soup(soup_mock)

        # Check that soup was called with the list of dangerous tags
        soup_mock.assert_called()
        args, _ = soup_mock.call_args
        self.assertIn('script', args[0])
        self.assertIn('iframe', args[0])

        # Check that decompose was called on the tag returned by soup(dangerous_tags)
        dangerous_tag.decompose.assert_called()

    def test_sanitize_strips_event_handlers(self):
        soup_mock = MagicMock()
        # Mock soup(dangerous_tags) to return nothing
        soup_mock.return_value = []

        tag_with_events = MagicMock()
        tag_with_events.attrs = {'onclick': 'evil()', 'onmouseover': 'evil()', 'class': 'safe'}

        soup_mock.find_all.return_value = [tag_with_events]

        EpubReader._sanitize_soup(soup_mock)

        self.assertNotIn('onclick', tag_with_events.attrs)
        self.assertNotIn('onmouseover', tag_with_events.attrs)
        self.assertIn('class', tag_with_events.attrs)

    def test_sanitize_strips_javascript_uris(self):
        soup_mock = MagicMock()
        soup_mock.return_value = []

        tag_with_js_uri = MagicMock()
        tag_with_js_uri.attrs = {
            'href': 'javascript:alert(1)',
            'src': '  JAVASCRIPT:evil() ',
            'action': '/safe'
        }

        soup_mock.find_all.return_value = [tag_with_js_uri]

        EpubReader._sanitize_soup(soup_mock)

        self.assertNotIn('href', tag_with_js_uri.attrs)
        self.assertNotIn('src', tag_with_js_uri.attrs)
        self.assertEqual(tag_with_js_uri.attrs['action'], '/safe')

class TestSentenceSplit(unittest.TestCase):
    def test_basic_split(self):
        text = "Hello world. How are you?"
        expected = ["Hello world.", "How are you?"]
        self.assertEqual(EpubReader._split_into_sentences(text), expected)

    def test_abbreviation_mr(self):
        text = "Mr. Smith went home."
        expected = ["Mr. Smith went home."]
        self.assertEqual(EpubReader._split_into_sentences(text), expected)

    def test_acronym_usa(self):
        text = "The U.S.A. is a country."
        expected = ["The U.S.A. is a country."]
        self.assertEqual(EpubReader._split_into_sentences(text), expected)

    def test_multiple_punctuation(self):
        text = "Wait! What? No way."
        expected = ["Wait!", "What?", "No way."]
        self.assertEqual(EpubReader._split_into_sentences(text), expected)

    def test_ellipsis(self):
        text = "An ellipsis... is tricky."
        expected = ["An ellipsis... is tricky."]
        self.assertEqual(EpubReader._split_into_sentences(text), expected)

    def test_multiple_spaces(self):
        text = "Sentence one.    Sentence two."
        expected = ["Sentence one.", "Sentence two."]
        self.assertEqual(EpubReader._split_into_sentences(text), expected)

    def test_empty_input(self):
        self.assertEqual(EpubReader._split_into_sentences(""), [])
        self.assertEqual(EpubReader._split_into_sentences(None), [])

    def test_trailing_spaces(self):
        text = "  Hello world.  "
        expected = ["Hello world."]
        self.assertEqual(EpubReader._split_into_sentences(text), expected)

if __name__ == '__main__':
    unittest.main()
