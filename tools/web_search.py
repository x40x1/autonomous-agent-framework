import requests
from bs4 import BeautifulSoup
import logging
import re
import time # Import time for potential sleep

# Add necessary imports
from .base_tool import BaseTool
# Import the search function from googlesearch
from googlesearch import search

logger = logging.getLogger(__name__)

MAX_SCRAPE_LENGTH = 4000 # Limit the amount of text scraped from a page
MAX_TOTAL_SCRAPED_LENGTH = 8000 # Limit total combined scraped text

def scrape_web_page(url: str, timeout: int = 10) -> str:
    """
    Scrapes the textual content from a given URL.
    Args:
        url: The URL to scrape.
        timeout: Request timeout in seconds.
    Returns:
        The scraped text content, or an error message.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # Check content type to avoid parsing images, PDFs, etc.
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            logger.warning(f"Skipping non-HTML/text content type '{content_type}' for URL: {url}")
            return f"Error: Content type '{content_type}' is not scrapable text/html."

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()

        # Get text content, trying common main content tags first
        main_content = soup.find('main') or soup.find('article') or soup.find('div', role='main') or soup.body
        if main_content:
             text = main_content.get_text(separator='\n', strip=True)
        else:
             text = soup.get_text(separator='\n', strip=True) # Fallback to whole body


        # Clean up excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text) # Collapse multiple blank lines
        text = text.strip()

        if len(text) > MAX_SCRAPE_LENGTH:
            logger.info(f"Scraped content truncated from {len(text)} to {MAX_SCRAPE_LENGTH} characters for {url}")
            text = text[:MAX_SCRAPE_LENGTH] + "..."

        if not text:
            return "Successfully accessed URL, but no significant text content found."

        return text

    except requests.exceptions.Timeout:
        logger.error(f"Timeout error while trying to scrape {url}")
        return f"Error: Timeout while trying to access {url}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during web scraping for {url}: {e}")
        # Provide specific feedback if possible (e.g., connection error, bad status)
        status_code = getattr(e.response, 'status_code', None)
        if status_code:
            return f"Error: Failed to access {url}. Status code: {status_code}"
        else:
            return f"Error: Could not access {url}. Reason: {e}"
    except Exception as e:
        logger.error(f"Unexpected error during web scraping for {url}: {e}", exc_info=True)
        return f"Error: An unexpected error occurred while scraping {url}."


# Define the WebSearchTool class using googlesearch
class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Performs a web search using Google. Input is the search query string. "
        "Returns a list of search results (title, URL, description). "
        "Also scrapes and includes the content of the top N results (configurable, default 3)."
    )

    def __init__(self, num_results: int = 10, num_results_to_scrape: int = 3, lang: str = "en", region: str = None, safe: str = "on", sleep_interval: int = 0):
        """
        Initializes the WebSearchTool using googlesearch-python.
        Args:
            num_results: The maximum number of search results links/descriptions to return (default: 10).
            num_results_to_scrape: The number of top results to scrape content from (default: 3).
            lang: Language code for search results (default: 'en').
            region: Country code for search results (default: None).
            safe: Safe search setting ('on' or None for off) (default: 'on').
            sleep_interval: Seconds to sleep between requests if num_results > 100 (default: 0).
        """
        self.num_results = num_results
        self.num_results_to_scrape = min(num_results_to_scrape, num_results) # Cannot scrape more than returned
        self.lang = lang
        self.region = region
        self.safe = safe # 'on' or None
        self.sleep_interval = sleep_interval
        logger.info(f"WebSearchTool (Google) initialized (num_results={num_results}, num_results_to_scrape={self.num_results_to_scrape}, lang={lang}, region={region}, safe={safe})")

    def execute(self, query: str) -> str:
        """
        Executes a Google search for the given query and scrapes top results.

        Args:
            query: The search query string.

        Returns:
            A string containing the search results and the scraped content of the top N results,
            or an error message if an error occurs.
        """
        if not query:
            return "Error: No search query provided."

        logger.info(f"Performing Google search for: '{query}' (returning {self.num_results} results, scraping top {self.num_results_to_scrape})")
        try:
            # Use advanced=True to get title, url, and description
            search_results = list(search(
                query,
                num_results=self.num_results,
                lang=self.lang,
                region=self.region,
                safe=self.safe,
                sleep_interval=self.sleep_interval,
                advanced=True # Get SearchResult objects
            ))

            if not search_results:
                return f"No search results found for '{query}'."

            output = f"Search results for '{query}':\n"
            urls_to_scrape = []
            for i, result in enumerate(search_results):
                # Access attributes of the SearchResult object
                title = getattr(result, 'title', 'N/A')
                url = getattr(result, 'url', 'N/A')
                description = getattr(result, 'description', 'N/A')

                output += f"{i+1}. {title}\n"
                output += f"   URL: {url}\n"
                output += f"   Description: {description}\n\n"

                if i < self.num_results_to_scrape and url != 'N/A':
                    urls_to_scrape.append(url)

            # Scrape the top N results
            scraped_content_combined = ""
            if urls_to_scrape:
                output += f"\n--- Content of Top {len(urls_to_scrape)} Result(s) ---\n"
                for i, url in enumerate(urls_to_scrape):
                    logger.info(f"Scraping result {i+1}: {url}")
                    scraped_content = scrape_web_page(url)
                    content_header = f"\n--- Scraped Content from Result {i+1} ({url}) ---\n"
                    scraped_content_combined += content_header + scraped_content + "\n"
                    # Check total length to avoid exceeding limits mid-scrape
                    if len(scraped_content_combined) > MAX_TOTAL_SCRAPED_LENGTH:
                        logger.warning(f"Stopping scraping early due to exceeding total length limit ({MAX_TOTAL_SCRAPED_LENGTH}).")
                        scraped_content_combined = scraped_content_combined[:MAX_TOTAL_SCRAPED_LENGTH] + "\n... (total scraped content truncated)"
                        break # Stop scraping more results

                output += scraped_content_combined
                output += "\n--- End of Scraped Content ---"

            # Limit overall output length (including search results list and scraped content)
            # Use a larger limit as scraped content can be long
            MAX_OVERALL_LENGTH = 15000
            if len(output) > MAX_OVERALL_LENGTH:
                 output = output[:MAX_OVERALL_LENGTH] + "\n... (overall output truncated)"

            return output.strip()

        # googlesearch doesn't specify exceptions well, catch general Exception
        # Rate limiting might manifest as HTTP errors within requests, which scrape_web_page handles,
        # but the search itself might raise others.
        except Exception as e:
            logger.error(f"Error during Google search for '{query}': {e}", exc_info=True)
            # Check if it looks like a rate limit error (often HTTP 429)
            if "429" in str(e):
                 return f"Error: Google search failed likely due to rate limiting. Please try again later or reduce request frequency. Details: {e}"
            return f"Error: An unexpected error occurred during Google search for '{query}': {e}"