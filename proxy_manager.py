import json
import logging
import time
import requests
import threading
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import os

@dataclass
class Proxy:
    ip: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    country: Optional[str] = None
    last_used: Optional[float] = None
    fail_count: int = 0
    last_checked: Optional[float] = None
    is_working: bool = False
    response_time: Optional[float] = None
    
    @property
    def address(self) -> str:
        """Get full proxy address"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.ip}:{self.port}"
        return f"{self.protocol}://{self.ip}:{self.port}"
    
    @property
    def selenium_proxy(self) -> Dict[str, Dict[str, str]]:
        """Get proxy in format for Selenium"""
        return {
            "proxy": {
                "proxyType": "manual",
                "httpProxy": f"{self.ip}:{self.port}",
                "sslProxy": f"{self.ip}:{self.port}",
                "noProxy": "localhost,127.0.0.1"
            }
        }
    
    @property
    def playwright_proxy(self) -> Dict[str, str]:
        """Get proxy in format for Playwright"""
        if self.username and self.password:
            return {
                "server": f"{self.protocol}://{self.ip}:{self.port}",
                "username": self.username,
                "password": self.password
            }
        return {"server": f"{self.protocol}://{self.ip}:{self.port}"}
    
    def mark_used(self):
        """Mark proxy as recently used"""
        self.last_used = time.time()
    
    def mark_failed(self):
        """Mark proxy as failed"""
        self.fail_count += 1
        
    def mark_success(self):
        """Mark proxy as successfully used"""
        self.fail_count = max(0, self.fail_count - 1)  # Decrease fail count on success
        
    def set_check_result(self, is_working: bool, response_time: Optional[float] = None):
        """Set the result of a proxy check"""
        self.is_working = is_working
        self.last_checked = time.time()
        self.response_time = response_time
        if not is_working:
            self.fail_count += 1
        else:
            self.fail_count = 0  # Reset fail count if working


class ProxyManager:
    def __init__(self, proxy_file: str = "proxies.json", min_reuse_delay: int = 300):
        self.proxy_file = proxy_file
        self.proxies: List[Proxy] = []
        self.min_reuse_delay = min_reuse_delay  # Minimum time in seconds before reusing a proxy
        self._lock = threading.RLock()  # Thread-safe operations
        self.load_proxies()
    
    def load_proxies(self):
        """Load proxies from file"""
        with self._lock:
            try:
                if os.path.exists(self.proxy_file):
                    with open(self.proxy_file, 'r') as f:
                        data = json.load(f)
                    
                    self.proxies = []
                    for proxy_data in data:
                        self.proxies.append(Proxy(**proxy_data))
                    
                    logging.info(f"Loaded {len(self.proxies)} proxies")
                else:
                    logging.warning(f"Proxy file {self.proxy_file} not found. Starting with empty list.")
            except Exception as e:
                logging.error(f"Error loading proxies: {str(e)}")
                # Try to recover from backup if it exists
                backup_file = f"{self.proxy_file}.bak"
                if os.path.exists(backup_file):
                    try:
                        with open(backup_file, 'r') as f:
                            data = json.load(f)
                        self.proxies = [Proxy(**proxy_data) for proxy_data in data]
                        logging.info(f"Recovered {len(self.proxies)} proxies from backup")
                    except:
                        logging.error("Failed to recover from backup file")
    
    def save_proxies(self):
        """Save proxies to file"""
        with self._lock:
            try:
                # First create a backup of the current file if it exists
                if os.path.exists(self.proxy_file):
                    backup_file = f"{self.proxy_file}.bak"
                    try:
                        with open(self.proxy_file, 'r') as src, open(backup_file, 'w') as dst:
                            dst.write(src.read())
                    except:
                        logging.warning("Failed to create backup before saving")
                
                # Now save the new data
                with open(self.proxy_file, 'w') as f:
                    json.dump([asdict(proxy) for proxy in self.proxies], f, indent=4)
                logging.info(f"Saved {len(self.proxies)} proxies")
            except Exception as e:
                logging.error(f"Error saving proxies: {str(e)}")
    
    def parse_proxy_string(self, proxy_str: str) -> Tuple[str, int, Optional[str], Optional[str]]:
        """Parse a proxy string in various formats"""
        # Try to match protocol://[username:password@]ip:port
        full_pattern = r'^(?:(?P<protocol>https?|socks[45])://)?(?:(?P<username>[^:@]+):(?P<password>[^@]+)@)?(?P<ip>[0-9a-zA-Z\.\-]+):(?P<port>\d+)$'
        match = re.match(full_pattern, proxy_str)
        
        if match:
            protocol = match.group('protocol') or 'http'
            username = match.group('username')
            password = match.group('password')
            ip = match.group('ip')
            port = int(match.group('port'))
            return ip, port, username, password, protocol
            
        # Try simpler ip:port pattern
        simple_pattern = r'^(?P<ip>[0-9a-zA-Z\.\-]+):(?P<port>\d+)$'
        match = re.match(simple_pattern, proxy_str)
        
        if match:
            ip = match.group('ip')
            port = int(match.group('port'))
            return ip, port, None, None, 'http'
            
        raise ValueError(f"Invalid proxy format: {proxy_str}")
    
    def add_proxy(self, ip: str, port: int, username: Optional[str] = None, 
                 password: Optional[str] = None, protocol: str = "http", 
                 country: Optional[str] = None) -> Proxy:
        """Add a new proxy"""
        with self._lock:
            # Check if proxy already exists
            for proxy in self.proxies:
                if proxy.ip == ip and proxy.port == port:
                    # Update existing proxy
                    if username:
                        proxy.username = username
                    if password:
                        proxy.password = password
                    if protocol:
                        proxy.protocol = protocol
                    if country:
                        proxy.country = country
                    
                    self.save_proxies()
                    logging.info(f"Updated existing proxy {ip}:{port}")
                    return proxy
            
            # Add new proxy
            proxy = Proxy(
                ip=ip,
                port=port,
                username=username,
                password=password,
                protocol=protocol,
                country=country
            )
            self.proxies.append(proxy)
            self.save_proxies()
            logging.info(f"Added new proxy {ip}:{port}")
            return proxy
    
    def get_proxy(self, country: Optional[str] = None, max_fails: int = 3, 
                 protocol: Optional[str] = None, working_only: bool = True) -> Optional[Proxy]:
        """Get a proxy that hasn't been used recently"""
        with self._lock:
            now = time.time()
            available_proxies = []
            
            for p in self.proxies:
                # Skip if proxy doesn't match criteria
                if p.fail_count >= max_fails:
                    continue
                if working_only and p.last_checked and not p.is_working:
                    continue
                if country and p.country != country:
                    continue
                if protocol and p.protocol != protocol:
                    continue
                if p.last_used and (now - p.last_used) <= self.min_reuse_delay:
                    continue
                
                available_proxies.append(p)
            
            if not available_proxies:
                # Fallback: if no working proxies, try any that meet the criteria
                if working_only:
                    return self.get_proxy(country, max_fails, protocol, False)
                logging.warning("No available proxies found")
                return None
            
            # Sort by fail count and last used time
            available_proxies.sort(key=lambda x: (x.fail_count, x.last_used or 0))
            proxy = available_proxies[0]  # Get the best proxy
            
            proxy.mark_used()
            self.save_proxies()
            return proxy
    
    def report_proxy_result(self, proxy: Proxy, success: bool):
        """Report a proxy success or failure"""
        with self._lock:
            for p in self.proxies:
                if p.ip == proxy.ip and p.port == proxy.port:
                    if success:
                        p.mark_success()
                        logging.info(f"Proxy {p.ip}:{p.port} used successfully")
                    else:
                        p.mark_failed()
                        logging.warning(f"Marked proxy {p.ip}:{p.port} as failed (count: {p.fail_count})")
                    
                    self.save_proxies()
                    break
    
    def test_proxy(self, proxy: Proxy, test_url: str = "https://www.google.com", 
                  timeout: int = 10) -> bool:
        """Test if a proxy is working"""
        start_time = time.time()
        try:
            response = requests.get(
                test_url,
                proxies={
                    "http": proxy.address,
                    "https": proxy.address
                },
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )
            response_time = time.time() - start_time
            success = response.status_code == 200
            
            with self._lock:
                # Update proxy status
                proxy.set_check_result(success, response_time)
                self.save_proxies()
                
            return success
        except Exception as e:
            response_time = time.time() - start_time
            
            with self._lock:
                # Update proxy status
                proxy.set_check_result(False, response_time)
                self.save_proxies()
                
            return False
    
    def bulk_add_from_text(self, text: str, protocol: str = "http", test_proxies: bool = False) -> int:
        """Add multiple proxies from text in various formats"""
        added = 0
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            try:
                # Try to parse the proxy string
                ip, port, username, password, detected_protocol = self.parse_proxy_string(line)
                
                # Use detected protocol if available, otherwise use provided default
                actual_protocol = detected_protocol or protocol
                
                proxy = self.add_proxy(
                    ip=ip,
                    port=port,
                    username=username,
                    password=password,
                    protocol=actual_protocol
                )
                
                if test_proxies:
                    working = self.test_proxy(proxy)
                    if working:
                        logging.info(f"Added working proxy: {ip}:{port}")
                    else:
                        logging.warning(f"Added non-working proxy: {ip}:{port}")
                
                added += 1
            except Exception as e:
                logging.error(f"Failed to parse proxy: {line}. Error: {str(e)}")
        
        self.save_proxies()
        logging.info(f"Added {added} proxies")
        return added
    
    def remove_failed_proxies(self, max_fails: int = 5) -> int:
        """Remove proxies that have failed too many times"""
        with self._lock:
            before_count = len(self.proxies)
            self.proxies = [p for p in self.proxies if p.fail_count < max_fails]
            removed = before_count - len(self.proxies)
            if removed > 0:
                logging.info(f"Removed {removed} failed proxies")
                self.save_proxies()
            return removed
    
    def get_proxy_stats(self) -> Dict[str, int]:
        """Get statistics about proxy availability"""
        with self._lock:
            total = len(self.proxies)
            working = sum(1 for p in self.proxies if p.is_working)
            available = sum(1 for p in self.proxies if p.is_working and (not p.last_used or time.time() - p.last_used > self.min_reuse_delay))
            failing = sum(1 for p in self.proxies if p.fail_count > 0)
            
            return {
                "total": total,
                "working": working,
                "available": available,
                "failing": failing
            }
    
    def export_working_proxies(self, format: str = "plain") -> str:
        """Export working proxies in different formats"""
        result = []
        with self._lock:
            working_proxies = [p for p in self.proxies if p.is_working]
            
            if format == "plain":
                for proxy in working_proxies:
                    if proxy.username and proxy.password:
                        result.append(f"{proxy.ip}:{proxy.port}:{proxy.username}:{proxy.password}")
                    else:
                        result.append(f"{proxy.ip}:{proxy.port}")
                return "\n".join(result)
            
            elif format == "json":
                return json.dumps([asdict(p) for p in working_proxies], indent=2)
            
            elif format == "curl":
                return "\n".join([f"--proxy {p.address}" for p in working_proxies])
            
            else:
                raise ValueError(f"Unknown export format: {format}")
        

# Example to create initial proxy list
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = ProxyManager()
    
    # Example: Add some free proxies for testing
    sample_proxies = """
    203.24.108.171:80
    45.77.177.53:8888
    51.79.145.53:3128
    34.142.51.21:443
    203.23.106.192:80
    """
    
    manager.bulk_add_from_text(sample_proxies)
    print(f"Added sample proxies. Total proxies: {len(manager.proxies)}")
    
    # Test getting a proxy
    proxy = manager.get_proxy()
    if proxy:
        print(f"Got proxy: {proxy.address}")
        working = manager.test_proxy(proxy)
        print(f"Proxy working: {working}")