import requests
from bs4 import BeautifulSoup
import re
import json
import logging
import random
import time
from urllib.parse import urlparse, parse_qs, urljoin
from fake_useragent import UserAgent
import cloudscraper

logger = logging.getLogger(__name__)

# Initialize cloudscraper
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'mobile': False
    }
)

def get_headers():
    """Get random headers to avoid detection."""
    try:
        ua = UserAgent()
        user_agent = ua.random
    except:
        user_agent = random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        ])

    return {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'dnt': '1',
        'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
    }

def expand_shortened_url(url):
    """Expand shortened Amazon URL to full URL."""
    try:
        # Create a session with cloudscraper
        session = scraper.create_scraper()
        
        # First try to get the final URL
        response = session.head(url, allow_redirects=True)
        expanded_url = response.url
        
        # If we got a mission/campaign page, try to extract the actual product URL
        if 'mission' in expanded_url or 'campaign' in expanded_url:
            # Get the full page content
            response = session.get(url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try to find product link
            product_link = None
            
            # Method 1: Look for canonical link
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical and 'dp/' in canonical['href']:
                product_link = canonical['href']
            
            # Method 2: Look for product URL in meta tags
            if not product_link:
                meta_url = soup.find('meta', {'property': 'og:url'})
                if meta_url and 'dp/' in meta_url['content']:
                    product_link = meta_url['content']
            
            # Method 3: Look for product link in the page
            if not product_link:
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    if '/dp/' in href:
                        product_link = urljoin('https://www.amazon.in', href)
                        break
            
            if product_link:
                expanded_url = product_link

        logger.info(f"Expanded URL: {expanded_url}")
        return expanded_url
    except Exception as e:
        logger.error(f"Error expanding URL: {e}")
        return url

def extract_asin(url):
    """Extract ASIN from Amazon URL."""
    try:
        # First expand the URL if it's shortened
        if 'amzn.to' in url:
            url = expand_shortened_url(url)
            logger.info(f"Working with expanded URL: {url}")
        
        # Try to find ASIN in URL path
        path_match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if path_match:
            return path_match.group(1)
        
        # Try to find ASIN in query parameters
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        if 'asin' in query_params:
            return query_params['asin'][0]
        
        return None
    except Exception as e:
        logger.error(f"Error extracting ASIN: {e}")
        return None

def clean_price(price_str):
    """Clean price string to standard format."""
    if not price_str:
        return None
    price = re.sub(r'[^\d.]', '', price_str)
    return f"₹{price}"

def extract_discount(current_price, original_price):
    """Calculate discount percentage."""
    if not current_price or not original_price:
        return None
    
    try:
        current = float(re.sub(r'[^\d.]', '', current_price))
        original = float(re.sub(r'[^\d.]', '', original_price))
        if original > 0:
            discount = ((original - current) / original) * 100
            return f"{int(discount)}%"
    except:
        pass
    return None

def get_product_details(url, max_retries=3):
    """Fetch product details from Amazon URL."""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Expand shortened URL if necessary
            if 'amzn.to' in url:
                url = expand_shortened_url(url)
                logger.info(f"Expanded URL for scraping (attempt {attempt + 1}): {url}")

            # Add affiliate tag if not present
            if 'tag=' not in url:
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}tag=krunalweb20-21"

            # Add some randomized delay to appear more human-like
            time.sleep(random.uniform(2, 4))

            # Create a new scraper session for each attempt
            session = scraper.create_scraper()
            
            # Make the request using cloudscraper
            response = session.get(url)
            logger.info(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                raise Exception(f"Failed to fetch page. Status code: {response.status_code}")

            # Parse the content
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Debug log for title element
            title_elem = soup.select_one('#productTitle')
            if not title_elem:
                # Try alternative title selectors
                title_elem = (
                    soup.select_one('h1.product-title') or
                    soup.select_one('h1[data-test-id="product-title"]') or
                    soup.select_one('.product-title-word-break')
                )
            
            logger.info(f"Title element found: {title_elem is not None}")
            
            # Extract product details with logging
            title = title_elem.text.strip() if title_elem else None
            logger.info(f"Extracted title: {title}")

            if not title:
                raise Exception("Failed to extract product title")

            # Try multiple price selectors with logging
            price = None
            price_selectors = [
                '.a-price .a-offscreen',
                '#priceblock_ourprice',
                '#priceblock_dealprice',
                '.a-price-whole',
                '.a-color-price'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price = price_elem.text.strip()
                    logger.info(f"Found price with selector {selector}: {price}")
                    break

            # Get original price
            original_price = None
            original_price_selectors = [
                '.a-text-strike',
                '#priceblock_listprice',
                '.a-price.a-text-price span[aria-hidden="true"]',
                '.a-text-price'
            ]
            
            for selector in original_price_selectors:
                original_price_elem = soup.select_one(selector)
                if original_price_elem:
                    original_price = original_price_elem.text.strip()
                    logger.info(f"Found original price: {original_price}")
                    break

            # Get rating
            rating = None
            rating_selectors = [
                'span[data-hook="rating-out-of-text"]',
                '.a-icon-star .a-icon-alt',
                '#acrPopover .a-color-base'
            ]
            
            for selector in rating_selectors:
                rating_elem = soup.select_one(selector)
                if rating_elem:
                    rating_text = rating_elem.text.strip()
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    if rating_match:
                        rating = rating_match.group(1)
                        logger.info(f"Found rating: {rating}")
                        break

            # Get reviews count
            reviews = None
            reviews_selectors = [
                '#acrCustomerReviewText',
                'span[data-hook="total-review-count"]',
                '#reviewsMedley .a-color-secondary'
            ]
            
            for selector in reviews_selectors:
                reviews_elem = soup.select_one(selector)
                if reviews_elem:
                    reviews_text = reviews_elem.text.strip()
                    reviews_match = re.search(r'(\d+(?:,\d+)*)', reviews_text)
                    if reviews_match:
                        reviews = reviews_match.group(1)
                        logger.info(f"Found reviews: {reviews}")
                        break

            # Get description and features
            description = None
            features = []
            
            # Try to get description
            description_selectors = [
                '#feature-bullets .a-list-item',
                '#productDescription p',
                '#product-description',
                '.a-spacing-mini:not(.a-spacing-top-small)'
            ]
            
            for selector in description_selectors:
                desc_elems = soup.select(selector)
                if desc_elems:
                    description = ' '.join([elem.text.strip() for elem in desc_elems[:2]])
                    logger.info(f"Found description: {description[:100]}...")
                    break

            # Get features
            feature_selectors = [
                '#feature-bullets .a-list-item',
                '.a-unordered-list .a-list-item'
            ]
            
            for selector in feature_selectors:
                feature_elems = soup.select(selector)
                for elem in feature_elems[:4]:
                    feature_text = elem.text.strip()
                    if feature_text and len(feature_text) > 5:
                        features.append(feature_text)
                if features:
                    logger.info(f"Found {len(features)} features")
                    break

            # Get product image
            image_url = None
            image_selectors = [
                '#imgBlkFront',
                '#landingImage',
                '#main-image',
                '.a-dynamic-image',
                '#imgTagWrapperId img',
                '.image-wrapper img',
                '.a-stretch-horizontal img',
                'img[data-old-hires]',
                'img[data-a-dynamic-image]'
            ]
            
            for selector in image_selectors:
                image_elems = soup.select(selector)
                for image_elem in image_elems:
                    # Try different image attributes in order of preference
                    for attr in ['data-old-hires', 'data-a-dynamic-image', 'src']:
                        if attr in image_elem.attrs:
                            if attr == 'data-a-dynamic-image':
                                try:
                                    # Parse the JSON string to get the highest resolution image
                                    image_data = json.loads(image_elem[attr])
                                    if image_data:
                                        # Get the URL with the highest resolution
                                        image_url = max(image_data.items(), key=lambda x: x[1][0] if isinstance(x[1], list) else 0)[0]
                                        break
                                except:
                                    continue
                            else:
                                image_url = image_elem[attr]
                                # Remove low-quality indicators
                                if '_SL160_' in image_url:
                                    image_url = image_url.replace('_SL160_', '_SL500_')
                                elif '_SY' in image_url or '_SX' in image_url:
                                    # Replace with higher resolution
                                    image_url = re.sub(r'_(SY|SX)\d+_', '_SL500_', image_url)
                                break
                    
                    if image_url:
                        # Ensure absolute URL and HTTPS
                        image_url = urljoin(url, image_url)
                        if image_url.startswith('http://'):
                            image_url = 'https://' + image_url[7:]
                        logger.info(f"Found image URL: {image_url}")
                        break
                
                if image_url:
                    break

            # Clean and format the data
            price = clean_price(price) if price else None
            original_price = clean_price(original_price) if original_price else None
            discount = extract_discount(price, original_price) if price and original_price else None

            # Create product data dictionary
            product_data = {
                'title': title,
                'price': price,
                'original_price': original_price,
                'discount': discount,
                'rating': rating,
                'reviews': reviews,
                'description': description,
                'features': features,
                'image_url': image_url,
                'link': url
            }

            # Filter out None values
            product_data = {k: v for k, v in product_data.items() if v is not None}
            
            # Validate essential fields
            if not product_data.get('title') or not product_data.get('price'):
                raise Exception("Missing essential product data (title or price)")
            
            logger.info(f"Successfully extracted product data: {json.dumps(product_data, indent=2)}")
            return product_data

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt + 1} failed: {last_error}")
            
            # Add increasing delay between retries
            if attempt < max_retries - 1:
                time.sleep(random.uniform(3 * (attempt + 1), 6 * (attempt + 1)))
    
    logger.error(f"All {max_retries} attempts failed. Last error: {last_error}")
    return None

def is_valid_amazon_url(url):
    """Check if URL is a valid Amazon product URL."""
    try:
        # Handle shortened URLs
        if 'amzn.to' in url:
            expanded_url = expand_shortened_url(url)
            logger.info(f"Validating expanded URL: {expanded_url}")
            parsed_url = urlparse(expanded_url)
        else:
            parsed_url = urlparse(url)
            
        is_valid = (
            ('amazon.in' in parsed_url.netloc or 'amzn.to' in parsed_url.netloc) and
            (
                'dp/' in url or 
                'gp/product/' in url or 
                'amzn.to' in url
            )
        )
        
        logger.info(f"URL validation result: {is_valid}")
        return is_valid
    except Exception as e:
        logger.error(f"Error validating URL: {e}")
        return False 