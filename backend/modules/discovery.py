"""
Website Discovery Module — Robust Multi-Strategy Discovery
==========================================================
Strategy order:
  1. Multi-TLD domain brute-force (30+ TLDs and slug variants)
  2. DuckDuckGo HTML search with strict filtering
  3. Bing search fallback with strict filtering
  4. Google Custom Search (no-API, lite scrape) as last resort

Key fix: search-engine results that point back to a search-engine
domain (duckduckgo.com, bing.com, google.com, etc.) are EXCLUDED.
Only domains that contain a word from the startup name are accepted.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus
import re
import time


# Domains that should NEVER be returned as a discovered startup website
BLOCKED_DOMAINS = {
    'duckduckgo.com', 'google.com', 'bing.com', 'yahoo.com',
    'baidu.com', 'ask.com', 'aol.com', 'yandex.com',
    'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'youtube.com', 'wikipedia.org', 'wikimedia.org',
    'reddit.com', 'quora.com', 'medium.com',
    'crunchbase.com', 'bloomberg.com', 'techcrunch.com',
    'glassdoor.com', 'indeed.com', 'zoominfo.com',
    'pinterest.com', 'tumblr.com', 'github.com',
    'amazon.com', 'ebay.com', 'shopify.com',
    'wordpress.com', 'blogspot.com', 'wix.com',
}

# Full set of TLDs to try in brute-force mode
TLDS = [
    'com', 'io', 'co', 'net', 'org', 'biz', 'app', 'tech',
    'ai', 'in', 'us', 'co.in', 'co.uk', 'info', 'xyz', 'dev',
    'solutions', 'services', 'digital', 'software', 'cloud',
]


class WebsiteDiscovery:
    """Discovers official website for a given startup name"""

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def discover_website(self, startup_name):
        """
        Multi-strategy website discovery.

        Returns:
            dict: { 'success', 'website', 'method', 'message', 'candidates_tried' }
        """
        candidates_tried = []

        # ── Strategy 1: Brute-force domain variants ────────────────────────
        result = self._try_domain_variants(startup_name, candidates_tried)
        if result:
            return {
                'success': True,
                'website': result,
                'method': 'domain_bruteforce',
                'message': f'Website discovered via domain pattern: {result}',
                'candidates_tried': candidates_tried
            }

        # ── Strategy 2: DuckDuckGo HTML search (strictly filtered) ─────────
        result = self._search_engine(
            startup_name,
            engine='duckduckgo',
            candidates_tried=candidates_tried
        )
        if result:
            return {
                'success': True,
                'website': result,
                'method': 'duckduckgo_search',
                'message': f'Website discovered via DuckDuckGo: {result}',
                'candidates_tried': candidates_tried
            }

        # ── Strategy 3: Bing search ─────────────────────────────────────────
        result = self._search_engine(
            startup_name,
            engine='bing',
            candidates_tried=candidates_tried
        )
        if result:
            return {
                'success': True,
                'website': result,
                'method': 'bing_search',
                'message': f'Website discovered via Bing: {result}',
                'candidates_tried': candidates_tried
            }

        return {
            'success': False,
            'website': None,
            'method': 'none',
            'message': 'Could not discover website automatically. Please provide the URL manually.',
            'candidates_tried': candidates_tried
        }

    def validate_website(self, url):
        """Validate if a website is reachable"""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            return {
                'reachable':   response.status_code < 400,
                'status_code': response.status_code,
                'final_url':   response.url,
                'message':     'Website is reachable' if response.status_code < 400 else 'Website returned error'
            }
        except requests.exceptions.Timeout:
            return {'reachable': False, 'status_code': None, 'final_url': url, 'message': 'Request timeout'}
        except requests.exceptions.ConnectionError:
            return {'reachable': False, 'status_code': None, 'final_url': url, 'message': 'Connection failed'}
        except Exception as e:
            return {'reachable': False, 'status_code': None, 'final_url': url, 'message': f'Error: {str(e)}'}

    # ──────────────────────────────────────────────────────────────────────────
    # Strategy 1: Domain Brute-Force
    # ──────────────────────────────────────────────────────────────────────────

    def _try_domain_variants(self, startup_name, candidates_tried):
        """
        Build and probe every plausible domain for the startup name.
        Priority: full name → without generic suffixes (Inc, Ltd, Technologies…)
        """
        slugs = self._build_slugs(startup_name)

        for slug in slugs:
            for tld in TLDS:
                for prefix in ['', 'www.']:
                    url = f'https://{prefix}{slug}.{tld}'
                    candidates_tried.append(url)
                    if self._is_valid_startup_url(url, startup_name):
                        return url

        return None

    def _build_slugs(self, startup_name):
        """
        Generate domain slug variations from a startup name.
        Example: "LoopCon Technologies" →
            ['loopcontechnologies', 'loopcon', 'loopcontech']
        """
        # 1. Full name slug
        clean_full = re.sub(r'[^a-zA-Z0-9\s]', '', startup_name.lower()).strip()
        full_slug  = clean_full.replace(' ', '')

        # 2. Remove common business suffixes
        generic_suffixes = [
            'technologies', 'technology', 'solutions', 'services',
            'systems', 'software', 'digital', 'consulting', 'labs',
            'studio', 'studios', 'works', 'ventures', 'group',
            'corporation', 'corp', 'incorporated', 'inc', 'limited',
            'ltd', 'llc', 'pvt', 'private', 'enterprises', 'global',
            'international', 'innovations', 'innovation'
        ]
        words = clean_full.split()
        stripped_words = [w for w in words if w not in generic_suffixes]

        slugs = [full_slug]

        if stripped_words and stripped_words != words:
            short_slug = ''.join(stripped_words)
            if short_slug and short_slug != full_slug:
                slugs.append(short_slug)

            # Also first word + first letter of each remaining word
            if len(stripped_words) > 1:
                abbrev = stripped_words[0] + ''.join(w[0] for w in stripped_words[1:])
                slugs.append(abbrev)

            # Prefix + short form of suffix, e.g. "loopcontech"
            if len(stripped_words) >= 2:
                partial = stripped_words[0] + stripped_words[1][:4]
                slugs.append(partial)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for s in slugs:
            if s and s not in seen:
                seen.add(s)
                unique.append(s)

        return unique

    # ──────────────────────────────────────────────────────────────────────────
    # Strategy 2/3: Search Engine Scraping (with strict filtering)
    # ──────────────────────────────────────────────────────────────────────────

    def _search_engine(self, startup_name, engine, candidates_tried):
        """Scrape search results and return the best matching URL."""
        try:
            query = f'"{startup_name}" official website'
            if engine == 'duckduckgo':
                search_url = f'https://html.duckduckgo.com/html/?q={quote_plus(query)}'
            else:  # bing
                search_url = f'https://www.bing.com/search?q={quote_plus(query)}'

            time.sleep(1)  # polite delay
            response = requests.get(
                search_url,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            urls = self._extract_urls_from_soup(soup, engine)

            for url in urls:
                candidates_tried.append(url)
                if self._is_valid_startup_url(url, startup_name):
                    return url

        except Exception:
            pass

        return None

    def _extract_urls_from_soup(self, soup, engine):
        """Extract candidate URLs from search result page."""
        urls = []

        if engine == 'duckduckgo':
            # DuckDuckGo's result links are in <a class="result__a">
            for a in soup.find_all('a', class_='result__a'):
                href = a.get('href', '')
                if href.startswith('http'):
                    urls.append(href)
            # Also check result__url spans
            for span in soup.find_all('a', class_='result__url'):
                href = span.get('href', '')
                if href.startswith('http'):
                    urls.append(href)
                # DuckDuckGo sometimes just shows text as URL
                text = span.get_text(strip=True)
                if text and '.' in text and not text.startswith('http'):
                    urls.append('https://' + text)

        elif engine == 'bing':
            for h2 in soup.find_all('h2'):
                a = h2.find('a')
                if a and a.get('href', '').startswith('http'):
                    urls.append(a['href'])
            for li in soup.find_all('li', class_='b_algo'):
                a = li.find('a')
                if a and a.get('href', '').startswith('http'):
                    urls.append(a['href'])

        # Normalise to base URLs (scheme + netloc only)
        base_urls = []
        seen = set()
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    if base not in seen:
                        seen.add(base)
                        base_urls.append(base)
            except Exception:
                continue

        return base_urls

    # ──────────────────────────────────────────────────────────────────────────
    # URL Validation
    # ──────────────────────────────────────────────────────────────────────────

    def _is_valid_startup_url(self, url, startup_name):
        """
        A URL is accepted only if:
        1. Its domain is NOT in the blocked list
        2. Its domain contains at least one significant word from the startup name
        3. The URL is actually reachable (HTTP < 400)
        """
        if not self._domain_matches_startup(url, startup_name):
            return False
        return self._probe_url(url)

    def _domain_matches_startup(self, url, startup_name):
        """Check that the domain contains at least one key word from the startup name."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')

            # Reject blocked domains
            for blocked in BLOCKED_DOMAINS:
                if domain == blocked or domain.endswith('.' + blocked):
                    return False

            # Build significant keywords (≥4 chars, not generic suffixes)
            _generic = {
                'technologies', 'technology', 'solutions', 'services',
                'systems', 'software', 'digital', 'consulting', 'labs',
                'studio', 'studios', 'works', 'ventures', 'group',
                'corporation', 'corp', 'incorporated', 'inc', 'limited',
                'ltd', 'llc', 'pvt', 'private', 'enterprises', 'global',
                'international', 'innovations', 'innovation', 'official',
                'website', 'site', 'web', 'home', 'page', 'the', 'and',
            }
            words = re.findall(r'[a-z]+', startup_name.lower())
            keywords = [w for w in words if len(w) >= 3 and w not in _generic]

            if not keywords:
                # If no keywords remain, check full-name slug
                slug = re.sub(r'[^a-z0-9]', '', startup_name.lower())
                return slug in domain

            # At least one keyword must appear in the domain
            domain_stripped = re.sub(r'[^a-z0-9]', '', domain)
            return any(kw in domain_stripped for kw in keywords)

        except Exception:
            return False

    def _probe_url(self, url):
        """Quick HTTP HEAD probe to check reachability."""
        try:
            resp = requests.head(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            return resp.status_code < 400
        except Exception:
            # Try GET as fallback (some servers reject HEAD)
            try:
                resp = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True   # don't download entire body
                )
                resp.close()
                return resp.status_code < 400
            except Exception:
                return False
