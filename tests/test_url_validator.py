"""Testy jednostkowe walidatora URL (A2).

Pokrywa: allowlist, blokadę prywatnych IP, schemat, SSRF, limity.
Łącznie 28 testów.
"""

import unittest
from unittest.mock import patch
from modules.url_validator import validate_url, validate_urls, _domain_in_allowlist

# Helper: mockujemy DNS resolve żeby publiczne domeny nie były blokowane
# w środowisku bez dostępu do internetu
_PUBLIC_DNS = [(2, 1, 0, "", ("93.184.216.34", 0))]  # przykładowy publiczny IP


def _mock_public_dns(*args, **kwargs):
    """Symuluje rozwiązanie DNS na publiczny adres IP."""
    return _PUBLIC_DNS


class TestSchemeValidation(unittest.TestCase):
    """Walidacja schematu URL."""

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_https_allowed(self, _):
        ok, _ = validate_url("https://reuters.com/article")
        self.assertTrue(ok)

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_http_allowed(self, _):
        ok, _ = validate_url("http://reuters.com/article")
        self.assertTrue(ok)

    def test_ftp_blocked(self):
        ok, err = validate_url("ftp://evil.com/file")
        self.assertFalse(ok)
        self.assertIn("schemat", err.lower())

    def test_javascript_blocked(self):
        ok, err = validate_url("javascript:alert(1)")
        self.assertFalse(ok)

    def test_file_blocked(self):
        ok, err = validate_url("file:///etc/passwd")
        self.assertFalse(ok)

    def test_data_uri_blocked(self):
        ok, _ = validate_url("data:text/html,<h1>hi</h1>")
        self.assertFalse(ok)


class TestPrivateIPBlocking(unittest.TestCase):
    """Blokada adresów prywatnych, loopback, link-local."""

    def test_localhost_blocked(self):
        ok, err = validate_url("http://localhost/admin")
        self.assertFalse(ok)
        self.assertIn("localhost", err.lower())

    def test_127_0_0_1_blocked(self):
        ok, err = validate_url("http://127.0.0.1/admin")
        self.assertFalse(ok)

    def test_0_0_0_0_blocked(self):
        ok, err = validate_url("http://0.0.0.0/")
        self.assertFalse(ok)

    def test_10_network_blocked(self):
        ok, err = validate_url("http://10.0.0.1/internal")
        self.assertFalse(ok)

    def test_172_16_blocked(self):
        ok, err = validate_url("http://172.16.0.1/")
        self.assertFalse(ok)

    def test_192_168_blocked(self):
        ok, err = validate_url("http://192.168.1.1/")
        self.assertFalse(ok)

    def test_ipv6_loopback_blocked(self):
        ok, err = validate_url("http://[::1]/")
        self.assertFalse(ok)

    def test_link_local_169_254_blocked(self):
        """Blokada AWS metadata endpoint (169.254.169.254)."""
        ok, err = validate_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(ok)

    def test_fc00_ipv6_blocked(self):
        """Blokada unique-local IPv6 (fc00::/7)."""
        ok, err = validate_url("http://[fc00::1]/")
        self.assertFalse(ok)


class TestAllowlist(unittest.TestCase):
    """Allowlist zaufanych domen."""

    TRUSTED = ["reuters.com", "bankier.pl", "finance.yahoo.com"]

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_exact_match(self, _):
        ok, _ = validate_url("https://reuters.com/article", self.TRUSTED)
        self.assertTrue(ok)

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_subdomain_match(self, _):
        ok, _ = validate_url("https://www.reuters.com/article", self.TRUSTED)
        self.assertTrue(ok)

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_untrusted_domain_blocked(self, _):
        ok, err = validate_url("https://evil.com/phish", self.TRUSTED)
        self.assertFalse(ok)
        self.assertIn("zaufanych", err.lower())

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_no_allowlist_allows_all_public(self, _):
        ok, _ = validate_url("https://anysite.com/page", None)
        self.assertTrue(ok)

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_deep_subdomain_allowed(self, _):
        ok, _ = validate_url("https://a.b.c.bankier.pl/article", self.TRUSTED)
        self.assertTrue(ok)


class TestDomainInAllowlist(unittest.TestCase):
    """Helper _domain_in_allowlist."""

    def test_subdomain(self):
        self.assertTrue(_domain_in_allowlist("www.reuters.com", ["reuters.com"]))

    def test_deep_subdomain(self):
        self.assertTrue(_domain_in_allowlist("a.b.c.reuters.com", ["reuters.com"]))

    def test_no_match(self):
        self.assertFalse(_domain_in_allowlist("evil.com", ["reuters.com"]))

    def test_partial_no_match(self):
        # "fakerreuters.com" nie powinno pasować do "reuters.com"
        self.assertFalse(_domain_in_allowlist("fakerreuters.com", ["reuters.com"]))

    def test_exact_match(self):
        self.assertTrue(_domain_in_allowlist("reuters.com", ["reuters.com"]))

    def test_empty_allowlist(self):
        self.assertFalse(_domain_in_allowlist("reuters.com", []))


class TestEdgeCases(unittest.TestCase):
    """Przypadki brzegowe."""

    def test_empty_url(self):
        ok, _ = validate_url("")
        self.assertFalse(ok)

    def test_none_url(self):
        ok, _ = validate_url(None)
        self.assertFalse(ok)

    def test_no_hostname(self):
        ok, _ = validate_url("https://")
        self.assertFalse(ok)

    def test_whitespace_url(self):
        ok, _ = validate_url("   ")
        self.assertFalse(ok)


class TestValidateUrls(unittest.TestCase):
    """Batch validate_urls z limitem MAX_URLS_PER_RUN."""

    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_mixed_urls(self, _):
        urls = [
            "https://reuters.com/article",
            "ftp://bad.com/file",
            "http://127.0.0.1/admin",
        ]
        valid, errors = validate_urls(urls, ["reuters.com"])
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0], "https://reuters.com/article")
        self.assertEqual(len(errors), 2)

    @patch("modules.url_validator.MAX_URLS_PER_RUN", 3)
    @patch("modules.url_validator.socket.getaddrinfo", side_effect=_mock_public_dns)
    def test_url_limit_exceeded(self, _):
        urls = [f"https://reuters.com/{i}" for i in range(5)]
        valid, errors = validate_urls(urls, ["reuters.com"])
        self.assertLessEqual(len(valid), 3)
        self.assertTrue(any("limit" in e.lower() for e in errors))

    def test_empty_list(self):
        valid, errors = validate_urls([])
        self.assertEqual(valid, [])
        self.assertEqual(errors, [])


class TestSSRFDnsRebind(unittest.TestCase):
    """Symulacja DNS resolve na adres prywatny (SSRF via DNS rebinding)."""

    @patch("modules.url_validator.socket.getaddrinfo")
    def test_dns_resolves_to_private(self, mock_dns):
        mock_dns.return_value = [(2, 1, 0, "", ("127.0.0.1", 0))]
        ok, err = validate_url("https://evil-rebind.com/steal")
        self.assertFalse(ok)
        self.assertIn("prywatnego", err.lower())

    @patch("modules.url_validator.socket.getaddrinfo")
    def test_dns_resolves_to_10_network(self, mock_dns):
        mock_dns.return_value = [(2, 1, 0, "", ("10.0.0.5", 0))]
        ok, err = validate_url("https://sneaky.com/internal")
        self.assertFalse(ok)

    @patch("modules.url_validator.socket.getaddrinfo")
    def test_dns_resolve_failure_blocked(self, mock_dns):
        """DNS failure = traktujemy jako niebezpieczne."""
        import socket
        mock_dns.side_effect = socket.gaierror("DNS failed")
        ok, err = validate_url("https://nonexistent.example.com/page")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
