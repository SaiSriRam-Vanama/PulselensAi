"""
Social Intelligence Scraper Module
Discovers official social profiles and scrapes public activity/engagement signals.
"""

import json
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class SocialScraper:
    """Scrapes social media activity signals from public pages."""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.platform_domains = {
            'linkedin': ['linkedin.com/company', 'linkedin.com/in', 'linkedin.com/showcase'],
            'twitter': ['twitter.com/', 'x.com/'],
            'instagram': ['instagram.com/'],
            'facebook': ['facebook.com/']
        }

    def scrape_social_data(self, website_url):
        """
        Discover and scrape social media activity from public pages.

        Returns:
            dict: Social intelligence payload
        """
        try:
            discovered = self.discover_social_links(website_url)
            validated = self.validate_social_links(discovered.get('social_links', {}))

            platform_data = {}
            all_timestamps = []
            all_engagement = []

            for platform, social_url in validated.items():
                scraped = self._scrape_platform_public_data(platform, social_url)
                platform_data[platform] = scraped
                all_timestamps.extend(scraped.get('recent_post_timestamps', []))
                all_engagement.extend(scraped.get('engagement_events', []))

            return {
                'success': True,
                'website_url': website_url,
                'social_links': discovered.get('social_links', {}),
                'validated_links': validated,
                'platform_data': platform_data,
                'all_post_timestamps': all_timestamps,
                'all_engagement_events': all_engagement,
                'scraped_at': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'social_links': {},
                'validated_links': {},
                'platform_data': {},
                'all_post_timestamps': [],
                'all_engagement_events': []
            }

    def discover_social_links(self, website_url):
        """Extract social profile links, prioritizing website footer."""
        social_links = {}

        response = requests.get(
            website_url,
            headers=self.headers,
            timeout=self.timeout,
            allow_redirects=True
        )

        if response.status_code >= 400:
            return {
                'success': False,
                'social_links': {},
                'error': f'Website HTTP {response.status_code}'
            }

        soup = BeautifulSoup(response.text, 'html.parser')

        footer_candidates = soup.find_all('footer')
        if not footer_candidates:
            footer_candidates = soup.select('[id*=footer], [class*=footer]')

        link_elements = []
        for section in footer_candidates:
            link_elements.extend(section.find_all('a', href=True))

        if not link_elements:
            link_elements = soup.find_all('a', href=True)

        for link in link_elements:
            href = (link.get('href') or '').strip()
            if not href:
                continue

            full_url = urljoin(website_url, href)
            normalized = self._normalize_url(full_url)
            platform = self._detect_platform(normalized)

            if platform and platform not in social_links:
                social_links[platform] = normalized

        return {
            'success': True,
            'social_links': social_links,
            'count': len(social_links)
        }

    def validate_social_links(self, social_links):
        """Validate social URLs by domain and public reachability."""
        valid = {}

        for platform, url in social_links.items():
            if not self._is_valid_platform_url(platform, url):
                continue

            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                if response.status_code < 400:
                    valid[platform] = url
            except Exception:
                continue

        return valid

    def _scrape_platform_public_data(self, platform, url):
        """Scrape timestamps and engagement hints from public platform pages."""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )

            if response.status_code >= 400:
                return {
                    'platform': platform,
                    'url': url,
                    'reachable': False,
                    'recent_post_timestamps': [],
                    'engagement_events': []
                }

            soup = BeautifulSoup(response.text, 'html.parser')

            timestamps = self._extract_timestamps(soup, response.text)
            engagement = self._extract_engagement_events(soup.get_text(' '), timestamps)

            return {
                'platform': platform,
                'url': url,
                'reachable': True,
                'recent_post_timestamps': timestamps[:40],
                'engagement_events': engagement[:60]
            }

        except Exception:
            return {
                'platform': platform,
                'url': url,
                'reachable': False,
                'recent_post_timestamps': [],
                'engagement_events': []
            }

    def _extract_timestamps(self, soup, html_text):
        """Extract post timestamps from structured and unstructured markup."""
        timestamps = []

        for time_tag in soup.find_all('time'):
            dt_value = time_tag.get('datetime') or time_tag.get_text(strip=True)
            parsed = self._parse_date(dt_value)
            if parsed:
                timestamps.append(parsed)

        for meta in soup.find_all('meta'):
            candidate = meta.get('content', '')
            prop = (meta.get('property') or meta.get('name') or '').lower()
            if 'published' in prop or 'modified' in prop or 'date' in prop:
                parsed = self._parse_date(candidate)
                if parsed:
                    timestamps.append(parsed)

        for script in soup.find_all('script', type='application/ld+json'):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue

            self._collect_dates_from_json(data, timestamps)

        iso_matches = re.findall(
            r'20\d{2}-[01]\d-[0-3]\d(?:[T\s][0-2]\d:[0-5]\d:[0-5]\d(?:Z|[+-][0-2]\d:?\d{2})?)?',
            html_text
        )
        for match in iso_matches[:120]:
            parsed = self._parse_date(match)
            if parsed:
                timestamps.append(parsed)

        unique = sorted(set(timestamps), reverse=True)
        return unique

    def _collect_dates_from_json(self, data, collector):
        if isinstance(data, dict):
            for key, value in data.items():
                if key in {'datePublished', 'dateCreated', 'dateModified', 'uploadDate'} and isinstance(value, str):
                    parsed = self._parse_date(value)
                    if parsed:
                        collector.append(parsed)
                else:
                    self._collect_dates_from_json(value, collector)
        elif isinstance(data, list):
            for item in data:
                self._collect_dates_from_json(item, collector)

    def _extract_engagement_events(self, text, timestamps):
        """Extract engagement counts from publicly visible text patterns."""
        events = []

        if not text:
            return events

        pattern = re.compile(
            r'([0-9]+(?:\.[0-9]+)?\s*[kKmM]?)\s*(likes?|comments?|replies|shares|retweets?|reposts?)'
        )
        matches = pattern.findall(text)

        normalized_counts = [self._parse_count(value) for value, _ in matches]
        normalized_counts = [count for count in normalized_counts if count is not None]

        for idx, count in enumerate(normalized_counts[:60]):
            timestamp = timestamps[idx] if idx < len(timestamps) else None
            events.append({
                'timestamp': timestamp,
                'engagement': count
            })

        return events

    def _parse_count(self, value):
        token = (value or '').strip().lower().replace(',', '')
        if not token:
            return None

        multiplier = 1
        if token.endswith('k'):
            multiplier = 1000
            token = token[:-1]
        elif token.endswith('m'):
            multiplier = 1000000
            token = token[:-1]

        try:
            return int(float(token) * multiplier)
        except Exception:
            return None

    def _detect_platform(self, url):
        lower_url = url.lower()
        for platform, patterns in self.platform_domains.items():
            if any(pattern in lower_url for pattern in patterns):
                return platform
        return None

    def _is_valid_platform_url(self, platform, url):
        lower_url = url.lower()
        patterns = self.platform_domains.get(platform, [])
        return any(pattern in lower_url for pattern in patterns)

    def _normalize_url(self, url):
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        return f"{parsed.scheme}://{parsed.netloc}{path}" if path else f"{parsed.scheme}://{parsed.netloc}"

    def _parse_date(self, date_string):
        if not date_string:
            return None

        raw = date_string.strip()
        raw = raw.replace('Z', '+00:00')

        formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%b %d, %Y',
            '%B %d, %Y'
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.isoformat()
            except Exception:
                continue

        try:
            return datetime.fromisoformat(raw).isoformat()
        except Exception:
            return None
