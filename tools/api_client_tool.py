import logging
import requests
import json
import time
from typing import Dict, Any, Optional

from .base_tool import BaseTool
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

class APIClientTool(BaseTool):
    name = "api_client"
    description = (
        "Makes HTTP requests to REST APIs. "
        "Input is a dictionary with: 'method' (GET, POST, etc.), 'url' (API endpoint), "
        "'headers' (optional HTTP headers), 'params' (optional URL parameters), "
        "and 'data' (optional request body). "
        "Returns the API response as text."
    )

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initializes the APIClientTool.
        
        Args:
            timeout: Request timeout in seconds.
            max_retries: Number of retries for failed requests.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        logger.info(f"APIClientTool initialized with timeout={timeout}s, max_retries={max_retries}")
    
    def execute(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, 
                params: Optional[Dict[str, Any]] = None, data: Optional[Any] = None) -> str:
        """
        Makes an HTTP request to the specified API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            url: API endpoint URL.
            headers: Optional HTTP headers.
            params: Optional URL parameters.
            data: Optional request body data.
            
        Returns:
            The API response as text.
        """
        attempts = 0
        last_error = None

        # If data is provided and is not a string, assume it's JSON serializable
        request_data = data if isinstance(data, str) else None
        json_data = data if not isinstance(data, str) else None

        while attempts < self.max_retries:
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=request_data,
                    json=json_data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.text
            except RequestException as e:
                attempts += 1
                last_error = e
                logger.error(f"Attempt {attempts} failed for {method} {url}: {e}")
                if attempts < self.max_retries:
                    time.sleep(1)  # wait for 1 second before retrying
        
        return f"Failed after {self.max_retries} attempts. Last error: {last_error}"
