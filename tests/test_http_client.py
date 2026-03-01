"""Tests for http_client — URL masking and safe_get behavior."""

import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.http_client import _mask_url


class TestMaskUrl(unittest.TestCase):

    def test_masks_apiKey(self):
        url = "https://api.example.com/v2/data?q=test&apiKey=secret123456789"
        masked = _mask_url(url)
        self.assertNotIn("secret123456789", masked)
        self.assertIn("secr***", masked)

    def test_masks_api_key_underscore(self):
        url = "https://api.example.com/?api_key=abcdef123456"
        masked = _mask_url(url)
        self.assertNotIn("abcdef123456", masked)
        self.assertIn("abcd***", masked)

    def test_masks_token(self):
        url = "https://api.example.com/?token=mytoken12345"
        masked = _mask_url(url)
        self.assertNotIn("mytoken12345", masked)

    def test_preserves_non_sensitive_params(self):
        url = "https://api.example.com/?q=test&language=en&apiKey=secret123"
        masked = _mask_url(url)
        self.assertIn("q=test", masked)
        self.assertIn("language=en", masked)
        self.assertNotIn("secret123", masked)

    def test_short_key_fully_masked(self):
        url = "https://api.example.com/?key=abc"
        masked = _mask_url(url)
        self.assertIn("key=***", masked)

    def test_no_sensitive_params(self):
        url = "https://api.example.com/data?q=hello&page=1"
        self.assertEqual(_mask_url(url), url)

    def test_multiple_sensitive_params(self):
        url = "https://x.com/?apiKey=secret1234&token=tok999888"
        masked = _mask_url(url)
        self.assertNotIn("secret1234", masked)
        self.assertNotIn("tok999888", masked)


if __name__ == "__main__":
    unittest.main()
