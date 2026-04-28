"""
Hiring Intelligence Scraper Module
Discovers and scrapes hiring-related pages from startup websites
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re


class HiringScraper:
    """Scrapes hiring/job listing information from startup websites"""
    
    def __init__(self, timeout=15):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # Common hiring page patterns
        self.hiring_patterns = [
            'careers', 'jobs', 'work-with-us', 'join-us', 'join-our-team',
            'opportunities', 'hiring', 'openings', 'positions', 'employment',
            'job-openings', 'career', 'apply', 'recruitment', 'vacancies'
        ]
    
    def scrape_hiring_data(self, website_url):
        """
        Main method to scrape hiring intelligence from a website
        
        Args:
            website_url (str): Main website URL
            
        Returns:
            dict: Hiring data including job listings and metrics
        """
        try:
            # Step 1: Discover hiring pages
            hiring_pages = self._discover_hiring_pages(website_url)
            
            if not hiring_pages:
                return {
                    'success': True,
                    'hiring_pages_found': 0,
                    'hiring_pages': [],
                    'open_positions': 0,
                    'job_listings': [],
                    'message': 'No hiring pages found'
                }
            
            # Step 2: Scrape job listings from discovered pages
            all_job_listings = []
            
            for page_url in hiring_pages[:5]:  # Limit to 5 pages to avoid overload
                try:
                    jobs = self._scrape_job_listings(page_url)
                    all_job_listings.extend(jobs)
                except Exception as e:
                    continue
            
            # Remove duplicates based on title
            unique_jobs = self._deduplicate_jobs(all_job_listings)
            
            return {
                'success': True,
                'hiring_pages_found': len(hiring_pages),
                'hiring_pages': hiring_pages,
                'open_positions': len(unique_jobs),
                'job_listings': unique_jobs,
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'hiring_pages_found': 0,
                'hiring_pages': [],
                'open_positions': 0,
                'job_listings': []
            }
    
    def _discover_hiring_pages(self, website_url):
        """Discover hiring/career pages from the main website"""
        hiring_pages = []
        
        try:
            response = requests.get(
                website_url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code >= 400:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            base_domain = urlparse(website_url).netloc
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                full_url = urljoin(website_url, link['href'])
                link_domain = urlparse(full_url).netloc
                
                # Check if it's an internal link matching hiring patterns
                if link_domain == base_domain or link_domain == '':
                    for pattern in self.hiring_patterns:
                        if pattern in href:
                            normalized_url = self._normalize_url(full_url)
                            if normalized_url not in hiring_pages:
                                hiring_pages.append(normalized_url)
                            break
            
            return hiring_pages
            
        except Exception as e:
            return []
    
    def _scrape_job_listings(self, page_url):
        """Scrape individual job listings from a hiring page"""
        job_listings = []
        
        try:
            response = requests.get(
                page_url,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code >= 400:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Strategy 1: Look for common job listing structures
            job_containers = self._find_job_containers(soup)
            
            for container in job_containers:
                job = self._extract_job_info(container)
                if job:
                    job_listings.append(job)
            
            # Strategy 2: Text-based extraction if no structured data found
            if len(job_listings) == 0:
                job_listings = self._extract_jobs_from_text(soup)
            
            return job_listings
            
        except Exception as e:
            return []
    
    def _find_job_containers(self, soup):
        """Find HTML containers that likely contain job listings"""
        containers = []
        
        # Common class patterns for job listings
        job_class_patterns = [
            'job', 'position', 'opening', 'vacancy', 'career', 'listing',
            'opportunity', 'role', 'posting'
        ]
        
        # Search for divs/articles/sections with job-related classes
        for tag in ['div', 'article', 'section', 'li']:
            for element in soup.find_all(tag):
                class_str = ' '.join(element.get('class', [])).lower()
                id_str = element.get('id', '').lower()
                
                for pattern in job_class_patterns:
                    if pattern in class_str or pattern in id_str:
                        containers.append(element)
                        break
        
        return containers[:50]  # Limit to prevent excessive processing
    
    def _extract_job_info(self, container):
        """Extract job information from a container element"""
        job = {}
        
        # Extract title (usually in h1-h4 or with specific class)
        title = None
        for heading in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'a']):
            text = heading.get_text(strip=True)
            if text and len(text) > 5 and len(text) < 150:
                title = text
                break
        
        if not title:
            return None
        
        job['title'] = title
        
        # Extract category/department
        category = self._extract_category(container)
        if category:
            job['category'] = category
        
        # Extract date if available
        posted_date = self._extract_date(container)
        if posted_date:
            job['posted_date'] = posted_date
        
        # Extract location if available
        location = self._extract_location(container)
        if location:
            job['location'] = location
        
        return job
    
    def _extract_category(self, container):
        """Extract job category/department"""
        # Look for common category indicators
        category_keywords = ['department', 'team', 'category', 'type']
        
        for element in container.find_all(['span', 'div', 'p']):
            class_str = ' '.join(element.get('class', [])).lower()
            
            for keyword in category_keywords:
                if keyword in class_str:
                    text = element.get_text(strip=True)
                    if text and len(text) < 50:
                        return text
        
        return None
    
    def _extract_date(self, container):
        """Extract posting date"""
        # Look for date patterns
        date_pattern = r'\b(202[0-9])[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])\b'
        
        text = container.get_text()
        match = re.search(date_pattern, text)
        
        if match:
            try:
                date_str = match.group(0)
                return date_str
            except:
                pass
        
        # Look for relative dates
        relative_patterns = [
            r'(\d+)\s+day[s]?\s+ago',
            r'(\d+)\s+week[s]?\s+ago',
            r'(\d+)\s+month[s]?\s+ago'
        ]
        
        for pattern in relative_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return text[match.start():match.end()]
        
        return None
    
    def _extract_location(self, container):
        """Extract job location"""
        location_keywords = ['location', 'remote', 'hybrid', 'office']
        
        for element in container.find_all(['span', 'div', 'p']):
            class_str = ' '.join(element.get('class', [])).lower()
            text = element.get_text(strip=True).lower()
            
            for keyword in location_keywords:
                if keyword in class_str or keyword in text:
                    location_text = element.get_text(strip=True)
                    if location_text and len(location_text) < 100:
                        return location_text
        
        return None
    
    def _extract_jobs_from_text(self, soup):
        """Extract job listings from text when no structured data is found"""
        job_listings = []
        
        # Look for text patterns that indicate job titles
        text = soup.get_text()
        
        # Common job title patterns
        job_title_patterns = [
            r'(?:^|\n)([A-Z][a-zA-Z\s]+(?:Engineer|Developer|Manager|Designer|Analyst|Specialist|Lead|Director|Coordinator))',
            r'(?:^|\n)([A-Z][a-zA-Z\s]+(?:- Full Time|-Part Time|- Remote))'
        ]
        
        for pattern in job_title_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:20]:  # Limit to 20
                title = match.strip()
                if len(title) > 5 and len(title) < 100:
                    job_listings.append({'title': title})
        
        return job_listings
    
    def _deduplicate_jobs(self, job_listings):
        """Remove duplicate job listings"""
        seen_titles = set()
        unique_jobs = []
        
        for job in job_listings:
            title = job.get('title', '').lower().strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def _normalize_url(self, url):
        """Normalize URL by removing fragments and query params for deduplication"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
