"""Walidacja URL dla scrapera — ochrona przed SSRF i niezaufanymi domenami."""

import ipaddress
import socket
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Limity bezpieczeństwa
MAX_REDIRECTS = 3
MAX_URLS_PER_RUN = 20
CONNECT_TIMEOUT = 8        # sekundy
READ_TIMEOUT = 15           # sekundy
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB


def _is_private_or_loopback(hostname: str) -> bool:
    """Sprawdza czy hostname rozwiązuje się do adresu prywatnego/loopback."""
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC,
                                   socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in infos:
            ip_str = sockaddr[0]
            addr = ipaddress.ip_address(ip_str)
            if (addr.is_private or addr.is_loopback or addr.is_reserved
                    or addr.is_link_local or addr.is_multicast
                    or addr.is_unspecified):
                return True
    except (socket.gaierror, ValueError, OSError):
        # Nie można rozwiązać — traktujemy jako niebezpieczne
        return True
    return False


def validate_url(url: str, trusted_domains: list[str] | None = None) -> tuple[bool, str]:
    """Waliduje URL pod kątem bezpieczeństwa.

    Zwraca (is_valid, error_message). Jeśli valid → (True, "").
    """
    if not url or not isinstance(url, str):
        return False, "Pusty lub nieprawidłowy URL"

    url = url.strip()

    # 1. Schemat — tylko http/https
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, f"Niedozwolony schemat: {parsed.scheme!r} (dozwolone: http, https)"

    hostname = parsed.hostname
    if not hostname:
        return False, "Brak hostname w URL"

    # 2. Blokada jawnych adresów IP prywatnych / loopback / link-local
    hostname_lower = hostname.lower()

    # Literalne IP
    try:
        addr = ipaddress.ip_address(hostname_lower)
        if (addr.is_private or addr.is_loopback or addr.is_reserved
                or addr.is_link_local or addr.is_multicast
                or addr.is_unspecified):
            return False, f"Zablokowany adres IP: {hostname} (prywatny/loopback/zarezerwowany)"
    except ValueError:
        pass  # nie jest adresem IP, to domena — ok

    # Blokada znanych nazw prywatnych
    blocked_hostnames = {"localhost", "localhost.localdomain",
                         "ip6-localhost", "ip6-loopback"}
    if hostname_lower in blocked_hostnames:
        return False, f"Zablokowany hostname: {hostname}"

    # 3. Rozwiązanie DNS — sprawdź czy nie kieruje na adres prywatny (SSRF)
    if _is_private_or_loopback(hostname):
        return False, f"Hostname {hostname} rozwiązuje się do adresu prywatnego/loopback"

    # 4. Allowlist domen (jeśli skonfigurowana)
    if trusted_domains:
        if not _domain_in_allowlist(hostname_lower, trusted_domains):
            return False, (f"Domena {hostname} nie znajduje się na liście zaufanych. "
                           f"Dodaj ją w Ustawieniach → Zaufane domeny.")

    return True, ""


def _domain_in_allowlist(hostname: str, trusted_domains: list[str]) -> bool:
    """Sprawdza czy hostname pasuje do listy zaufanych domen.

    Akceptuje dokładne dopasowanie i subdomeny, np:
    trusted='reuters.com' pasuje do 'www.reuters.com' i 'reuters.com'
    """
    for td in trusted_domains:
        td = td.lower().strip()
        if not td:
            continue
        if hostname == td or hostname.endswith("." + td):
            return True
    return False


def validate_urls(urls: list[str],
                  trusted_domains: list[str] | None = None
                  ) -> tuple[list[str], list[str]]:
    """Waliduje listę URL-i. Zwraca (valid_urls, errors).

    Stosuje limit MAX_URLS_PER_RUN.
    """
    if not urls:
        return [], []

    valid = []
    errors = []

    if len(urls) > MAX_URLS_PER_RUN:
        errors.append(
            f"Przekroczono limit {MAX_URLS_PER_RUN} URL na jedno uruchomienie "
            f"(podano {len(urls)}). Nadmiarowe zostaną pominięte.")
        urls = urls[:MAX_URLS_PER_RUN]

    for url in urls:
        url = url.strip()
        if not url:
            continue
        ok, err = validate_url(url, trusted_domains)
        if ok:
            valid.append(url)
        else:
            msg = f"Odrzucono URL {url}: {err}"
            errors.append(msg)
            logger.warning(msg)

    return valid, errors
