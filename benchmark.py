import time
import re

class EpubReaderOrig:
    LINK_PATTERN = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
    PROTOCOL_PATTERN = re.compile(r'^https?://')
    SPACE_PATTERN = re.compile(r' +')

    def _pronounce_links(self, text):
        def replace_link(match):
            url = match.group(0)
            pronounceable = self.PROTOCOL_PATTERN.sub('', url)
            pronounceable = pronounceable.replace('.', ' dot ').replace('/', ' slash ').replace('-', ' hyphen ').replace('_', ' underscore ')
            return self.SPACE_PATTERN.sub(' ', pronounceable).strip()
        return self.LINK_PATTERN.sub(replace_link, text)

class EpubReaderOpt:
    LINK_PATTERN = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
    PROTOCOL_PATTERN = re.compile(r'^https?://')
    SPACE_PATTERN = re.compile(r' +')

    def _replace_link(self, match):
        url = match.group(0)
        pronounceable = self.PROTOCOL_PATTERN.sub('', url)
        pronounceable = pronounceable.replace('.', ' dot ').replace('/', ' slash ').replace('-', ' hyphen ').replace('_', ' underscore ')
        return self.SPACE_PATTERN.sub(' ', pronounceable).strip()

    def _pronounce_links(self, text):
        return self.LINK_PATTERN.sub(self._replace_link, text)

def run_bench():
    orig = EpubReaderOrig()
    opt = EpubReaderOpt()

    test_text = "Check out this link https://example.com/some/path?foo=bar and also www.google.com for more info. Another one: http://test-site.org/index_page.html"

    # Verify correctness
    assert orig._pronounce_links(test_text) == opt._pronounce_links(test_text)

    iterations = 100000

    start = time.perf_counter()
    for _ in range(iterations):
        orig._pronounce_links(test_text)
    orig_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        opt._pronounce_links(test_text)
    opt_time = time.perf_counter() - start

    print(f"Original time: {orig_time:.5f}s")
    print(f"Optimized time: {opt_time:.5f}s")
    if orig_time > 0:
        improvement = (orig_time - opt_time) / orig_time * 100
        print(f"Improvement: {improvement:.2f}%")

if __name__ == '__main__':
    run_bench()
