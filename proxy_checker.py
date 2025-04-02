import os
import time
import json
import logging
import random
import redis
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional

from proxy_manager import ProxyManager, Proxy

# Configure logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=f"{log_dir}/proxy_checker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

class ProxyChecker:
    def __init__(self, 
                 check_interval: int = 3600, 
                 max_fails: int = 5,
                 test_urls: List[str] = None,
                 timeout: int = 10,
                 threads: int = 10):
        self.proxy_manager = ProxyManager()
        self.redis = redis.Redis(host='redis', port=6379, db=0)
        self.check_interval = check_interval  # How often to check proxies (seconds)
        self.max_fails = max_fails  # Maximum fails before removing a proxy
        self.timeout = timeout  # Request timeout in seconds
        self.threads = threads  # Number of threads for parallel checking
        
        # Test URLs
        self.test_urls = test_urls or [
            "https://www.google.com",
            "https://www.twitter.com",
            "https://www.amazon.com",
            "https://www.apple.com",
            "https://www.reddit.com"
        ]
        
        logging.info(f"Proxy Checker initialized")
    
    def check_proxy(self, proxy: Proxy) -> bool:
        """Check if a proxy is working by testing with multiple URLs"""
        working_count = 0
        total_urls = len(self.test_urls)
        
        for url in self.test_urls:
            try:
                # Try to connect through the proxy
                response = requests.get(
                    url,
                    proxies={
                        "http": proxy.address,
                        "https": proxy.address
                    },
                    timeout=self.timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                )
                
                if response.status_code == 200:
                    working_count += 1
                    # We don't need to check all URLs if some are working
                    if working_count >= max(1, total_urls // 3):  
                        return True
            except:
                # Ignore connection errors
                pass
        
        # If we got here, not enough URLs worked
        return False
    
    def check_all_proxies(self):
        """Check all proxies in parallel using a thread pool"""
        proxies = self.proxy_manager.proxies
        
        if not proxies:
            logging.warning("No proxies found to check")
            return
        
        logging.info(f"Checking {len(proxies)} proxies...")
        start_time = time.time()
        working = 0
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            # Map proxies to check_proxy tasks
            results = list(executor.map(self.check_proxy, proxies))
            
            # Process results
            for i, is_working in enumerate(results):
                proxy = proxies[i]
                if is_working:
                    working += 1
                    # Reset fail count for working proxies
                    proxy.fail_count = 0
                else:
                    proxy.fail_count += 1
                    logging.warning(f"Proxy {proxy.ip}:{proxy.port} failed (count: {proxy.fail_count})")
        
        # Save updated proxy statuses
        self.proxy_manager.save_proxies()
        
        # Remove failed proxies
        removed = self.proxy_manager.remove_failed_proxies(self.max_fails)
        
        duration = time.time() - start_time
        logging.info(f"Proxy check completed in {duration:.2f} seconds. Working: {working}/{len(proxies)}, Removed: {removed}")
        
        # Publish results to Redis for monitoring
        self.redis.set('proxy_stats', json.dumps({
            'total': len(proxies),
            'working': working,
            'removed': removed,
            'last_check': datetime.now().isoformat()
        }))
    
    def import_from_redis(self):
        """Import proxies from Redis if available"""
        try:
            proxy_list = self.redis.get('import_proxies')
            if proxy_list:
                proxies_text = proxy_list.decode('utf-8')
                added = self.proxy_manager.bulk_add_from_text(proxies_text)
                if added > 0:
                    logging.info(f"Imported {added} proxies from Redis")
                    # Clear the import list after successful import
                    self.redis.delete('import_proxies')
        except Exception as e:
            logging.error(f"Error importing proxies from Redis: {str(e)}")
    
    def run(self):
        """Main checker loop"""
        logging.info("Proxy Checker starting up")
        
        while True:
            try:
                # Import any new proxies
                self.import_from_redis()
                
                # Check all proxies
                self.check_all_proxies()
                
                # Sleep until next check
                logging.info(f"Next check in {self.check_interval} seconds")
                time.sleep(self.check_interval)
            
            except Exception as e:
                logging.error(f"Error in proxy checker: {str(e)}", exc_info=True)
                time.sleep(300)  # Sleep for 5 minutes on error


if __name__ == "__main__":
    checker = ProxyChecker()
    checker.run()