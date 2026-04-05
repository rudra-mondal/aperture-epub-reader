import sys
import timeit
from unittest.mock import MagicMock

# Mocking dependencies
mock_modules = [
    'ebooklib', 'ebooklib.epub', 'bs4', 'torch', 'kokoro', 'sounddevice', 'numpy',
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
    'PyQt6.QtCore', 'PyQt6.QtGui'
]
for module in mock_modules:
    sys.modules[module] = MagicMock()

# Specifically mock some classes
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

from main import EpubReader

def benchmark():
    text = "The value of x > y and a < b, also 1 + 1 = 2 - 0."

    # run 100000 times
    def run_benchmark():
        for _ in range(100000):
            EpubReader._pronounce_special_chars(None, text)

    # Warmup
    run_benchmark()

    start_time = timeit.default_timer()
    run_benchmark()
    end_time = timeit.default_timer()

    print(f"Baseline Time taken for 100,000 iterations: {end_time - start_time:.6f} seconds")

if __name__ == '__main__':
    benchmark()
