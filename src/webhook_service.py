import logging
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class WebhookService:
    """
    Handles asynchronous webhook notifications with retry logic.
    """
    def __init__(self, max_workers=2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def send_webhook(self, url: str, payload: dict, retries: int = 3):
        """
        Schedule a webhook to be sent asynchronously.
        """
        self.executor.submit(self._send_webhook_task, url, payload, retries)

    def _send_webhook_task(self, url: str, payload: dict, retries: int):
        """
        Internal task to send webhook with exponential backoff.
        """
        attempt = 0
        while attempt < retries:
            try:
                logger.info(f"Sending webhook to {url} (Attempt {attempt + 1})")
                response = requests.post(url, json=payload, timeout=10)
                
                if 200 <= response.status_code < 300:
                    logger.info(f"Webhook delivered successfully to {url}")
                    return
                else:
                    logger.warning(f"Webhook failed with status {response.status_code}: {response.text}")
            
            except Exception as e:
                logger.warning(f"Webhook connection error: {e}")

            attempt += 1
            if attempt < retries:
                sleep_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s...
                time.sleep(sleep_time)

        logger.error(f"Failed to deliver webhook to {url} after {retries} attempts")
