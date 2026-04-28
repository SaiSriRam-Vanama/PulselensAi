"""
Web Scraping Module
Scrapes publicly available website signals for startup health analysis
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re
from collections import Counter


class WebsiteScraper:
    """Scrapes website signals for analysis"""
    
    def __init__(self, timeout=15):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def scrape_website(self, url):
        """
        Scrape all relevant signals from a website
        
        Args:
            url (str): Website URL
            
        Returns:
            dict: Scraped data including all signals
        """
        try:
            # Get main page
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code >= 400:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}'
                }
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract all signals
            signals = {
                'success': True,
                'last_modified': self._extract_last_modified(response),
                'internal_pages': self._count_internal_pages(soup, url),
                'blog_dates': self._extract_blog_dates(soup, url),
                'update_frequency': None,  # Will be calculated in mining
                'content_activity': None,  # Will be calculated in mining
                'scraped_at': datetime.now().isoformat()
            }
            
            return signals
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Timeout'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Connection failed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _extract_last_modified(self, response):
        """Extract last modified date from HTTP headers"""
        last_modified = response.headers.get('Last-Modified')
        
        if last_modified:
            try:
                # Parse HTTP date format
                dt = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
                return dt.isoformat()
            except:
                pass
        
        return None
    
    def _count_internal_pages(self, soup, base_url):
        """Count number of internal pages/links"""
        internal_links = set()
        base_domain = urlparse(base_url).netloc
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Check if internal link
            if parsed.netloc == base_domain or parsed.netloc == '':
                # Normalize URL (remove fragments and query params for counting)
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                internal_links.add(normalized)
        
        return len(internal_links)
    
    def _extract_blog_dates(self, soup, base_url):
        """Extract publish dates from blog posts/articles"""
        dates = []
        
        # Strategy 1: Look for common date meta tags
        date_meta_tags = [
            'article:published_time',
            'datePublished',
            'publishdate',
            'date',
            'DC.date.issued'
        ]
        
        for meta_name in date_meta_tags:
            meta_tags = soup.find_all('meta', attrs={'property': meta_name})
            meta_tags += soup.find_all('meta', attrs={'name': meta_name})
            
            for tag in meta_tags:
                content = tag.get('content', '')
                parsed_date = self._parse_date(content)
                if parsed_date:
                    dates.append(parsed_date)
        
        # Strategy 2: Look for time tags with datetime attribute
        time_tags = soup.find_all('time', attrs={'datetime': True})
        for tag in time_tags:
            parsed_date = self._parse_date(tag['datetime'])
            if parsed_date:
                dates.append(parsed_date)
        
        # Strategy 3: Try to find dates in common blog patterns
        # Look for blog/news/articles links
        blog_patterns = ['/blog', '/news', '/articles', '/press']
        internal_links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(pattern in href.lower() for pattern in blog_patterns):
                full_url = urljoin(base_url, href)
                internal_links.append(full_url)
        
        # Scrape dates from first few blog pages
        for blog_url in internal_links[:5]:  # Limit to 5 to avoid too many requests
            try:
                blog_dates = self._scrape_page_dates(blog_url)
                dates.extend(blog_dates)
            except:
                continue
        
        # Strategy 4: Text-based date extraction (last resort)
        text_dates = self._extract_dates_from_text(soup.get_text())
        dates.extend(text_dates)
        
        # Remove duplicates and sort
        dates = list(set(dates))
        dates.sort(reverse=True)
        
        return dates[:20]  # Return top 20 most recent
    
    def _scrape_page_dates(self, url):
        """Scrape dates from a specific page"""
        dates = []
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code < 400:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for time tags
                time_tags = soup.find_all('time', attrs={'datetime': True})
                for tag in time_tags:
                    parsed_date = self._parse_date(tag['datetime'])
                    if parsed_date:
                        dates.append(parsed_date)
                
                # Look for date patterns in text
                text_dates = self._extract_dates_from_text(soup.get_text())
                dates.extend(text_dates)
        except:
            pass
        
        return dates
    
    def _extract_dates_from_text(self, text):
        """Extract dates from text using regex patterns"""
        dates = []
        
        # Pattern 1: YYYY-MM-DD
        pattern1 = r'\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])\b'
        matches1 = re.findall(pattern1, text)
        for match in matches1:
            try:
                date_str = f"{match[0]}-{match[1]}-{match[2]}"
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                dates.append(dt.isoformat())
            except:
                pass
        
        # Pattern 2: Month DD, YYYY
        pattern2 = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b'
        matches2 = re.findall(pattern2, text, re.IGNORECASE)
        for match in matches2:
            try:
                date_str = f"{match[0]} {match[1]}, {match[2]}"
                dt = datetime.strptime(date_str, '%B %d, %Y')
                dates.append(dt.isoformat())
            except:
                pass
        
        return dates[:10]  # Limit text-extracted dates
    
    def _parse_date(self, date_string):
        """Parse various date formats to ISO format"""
        if not date_string:
            return None
        
        # Common date formats
        formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%Y-%m-%dT%H:%M:%SZ',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_string.strip(), fmt)
                return dt.isoformat()
            except:
                continue
        
        return None
