import os
import json
import logging
import time
import random
import argparse
import redis
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import our modules
from account_manager import AccountManager, Account
from proxy_manager import ProxyManager, Proxy

class AirdropOrchestrator:
    def __init__(self, headless: bool = True, proxy_enabled: bool = True):
        self.account_manager = AccountManager()
        self.proxy_manager = ProxyManager()
        self.headless = headless
        self.proxy_enabled = proxy_enabled
        
        # Connect to Redis
        self.redis = redis.Redis(host='redis', port=6379, db=0)
        
        # Set up logging
        self.setup_logging()
        
    def setup_logging(self):
        """Set up logging"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = f"{log_dir}/airdrop_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Also log to console
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)
        
        logging.info("AirdropOrchestrator initialized")
    
    def enqueue_task(self, task_type: str, task_data: Dict[str, Any]) -> str:
        """Add a task to the queue"""
        task_id = str(uuid.uuid4())
        
        # Add basic task info
        task = {
            'task_id': task_id,
            'type': task_type,
            'timestamp': datetime.now().isoformat(),
            **task_data
        }
        
        # Add to queue
        self.redis.rpush('task_queue', json.dumps(task))
        logging.info(f"Enqueued task: {task_type} (ID: {task_id})")
        
        return task_id
    
    def wait_for_results(self, task_ids: List[str], timeout: int = 300) -> List[Dict[str, Any]]:
        """Wait for results from specific tasks"""
        results = []
        start_time = time.time()
        pending_ids = set(task_ids)
        
        logging.info(f"Waiting for {len(task_ids)} tasks to complete")
        
        while pending_ids and time.time() - start_time < timeout:
            # Check if there are results
            result_data = self.redis.lrange('result_queue', 0, -1)
            
            for result_json in result_data:
                try:
                    result = json.loads(result_json)
                    if result.get('task_id') in pending_ids:
                        results.append(result)
                        pending_ids.remove(result.get('task_id'))
                        # Remove this result from the queue
                        self.redis.lrem('result_queue', 0, result_json)
                except:
                    pass
            
            if pending_ids:
                # Still waiting for results
                time.sleep(1)
        
        if pending_ids:
            logging.warning(f"Timed out waiting for {len(pending_ids)} tasks")
        
        return results
    
    def create_accounts(self, count: int = 5, domain: str = "gmail.com") -> List[Account]:
        """Create Google accounts"""
        logging.info(f"Creating {count} accounts with domain {domain}...")
        
        task_ids = []
        for i in range(count):
            task_id = self.enqueue_task('create_account', {
                'email_domain': domain,
                'use_proxy': self.proxy_enabled
            })
            task_ids.append(task_id)
        
        # Wait for results
        results = self.wait_for_results(task_ids)
        
        created_accounts = []
        for result in results:
            if result.get('success'):
                email = result.get('account_email')
                account = self.account_manager.get_account(email)
                if account:
                    created_accounts.append(account)
                    logging.info(f"Account created: {email}")
                else:
                    logging.warning(f"Account created but not found in manager: {email}")
            else:
                logging.error(f"Failed to create account: {result.get('message')}")
        
        return created_accounts
    
    def register_accounts(self, platforms: List[str]) -> Dict[str, int]:
        """Register all accounts on specified platforms"""
        accounts = self.account_manager.accounts
        logging.info(f"Registering {len(accounts)} accounts on {len(platforms)} platforms")
        
        results_by_platform = {platform: 0 for platform in platforms}
        task_ids = []
        
        # Queue registration tasks for each account on each platform
        for account in accounts:
            for platform in platforms:
                # Skip if already registered
                if platform in account.platforms and account.platforms[platform]["registered"]:
                    logging.info(f"Account {account.email} already registered on {platform}, skipping")
                    results_by_platform[platform] += 1
                    continue
                
                task_id = self.enqueue_task('register_platform', {
                    'email': account.email,
                    'platform': platform
                })
                task_ids.append(task_id)
        
        # Wait for results
        results = self.wait_for_results(task_ids)
        
        # Process results
        for result in results:
            if result.get('success'):
                platform = result.get('platform')
                if platform in results_by_platform:
                    results_by_platform[platform] += 1
        
        return results_by_platform
    
    def participate_in_airdrop(self, airdrop_name: str, platform: str, actions: List[str]) -> List[Account]:
        """Participate in an airdrop with all eligible accounts"""
        # Get accounts registered on the platform
        accounts = self.account_manager.get_accounts_by_platform(platform, registered_only=True)
        
        if not accounts:
            logging.warning(f"No accounts registered on {platform}. Cannot participate in airdrop.")
            return []
        
        logging.info(f"Participating in {airdrop_name} airdrop with {len(accounts)} accounts")
        
        task_ids = []
        for account in accounts:
            task_id = self.enqueue_task('airdrop_participation', {
                'email': account.email,
                'airdrop_name': airdrop_name,
                'platform': platform,
                'actions': actions
            })
            task_ids.append(task_id)
        
        # Wait for results
        results = self.wait_for_results(task_ids)
        
        # Process results
        participated = []
        for result in results:
            if result.get('success'):
                email = result.get('email')
                account = self.account_manager.get_account(email)
                if account:
                    participated.append(account)
        
        logging.info(f"Successfully participated in {airdrop_name} with {len(participated)} accounts")
        return participated
    
    def monitor_queues(self):
        """Monitor task and result queues"""
        task_count = self.redis.llen('task_queue')
        result_count = self.redis.llen('result_queue')
        
        logging.info(f"Queue status: {task_count} pending tasks, {result_count} results")
        
        # Get proxy stats if available
        proxy_stats_json = self.redis.get('proxy_stats')
        if proxy_stats_json:
            try:
                proxy_stats = json.loads(proxy_stats_json)
                logging.info(f"Proxy stats: {proxy_stats.get('working', 0)}/{proxy_stats.get('total', 0)} working, Last check: {proxy_stats.get('last_check', 'unknown')}")
            except:
                pass
        
        return {
            'tasks': task_count,
            'results': result_count
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Airdrop Orchestrator")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--no-proxy", action="store_true", help="Disable proxy usage")
    parser.add_argument("--create", type=int, help="Create N new accounts")
    parser.add_argument("--register", action="store_true", help="Register accounts on platforms")
    parser.add_argument("--platforms", type=str, default="twitter,telegram,discord", help="Platforms to register on")
    parser.add_argument("--airdrop", type=str, help="Participate in specified airdrop")
    parser.add_argument("--monitor", action="store_true", help="Monitor queue status")
    
    args = parser.parse_args()
    
    orchestrator = AirdropOrchestrator(
        headless=args.headless,
        proxy_enabled=not args.no_proxy
    )
    
    if args.create:
        accounts = orchestrator.create_accounts(count=args.create)
        print(f"Created {len(accounts)} accounts:")
        for account in accounts:
            print(f"- {account.email} (Password: {account.password})")
    
    if args.register:
        platforms = args.platforms.split(",")
        results = orchestrator.register_accounts(platforms)
        print(f"Registration results:")
        for platform, count in results.items():
            print(f"- {platform}: {count} accounts registered")
    
    if args.airdrop:
        # For simplicity, we assume the airdrop is on Twitter
        platform = "twitter"
        actions = ["follow", "retweet", "like"]
        accounts = orchestrator.participate_in_airdrop(args.airdrop, platform, actions)
        print(f"Participated in {args.airdrop} airdrop with {len(accounts)} accounts")
    
    if args.monitor or (not args.create and not args.register and not args.airdrop):
        # If no specific action is requested, default to monitoring
        while True:
            orchestrator.monitor_queues()
            print("Press Ctrl+C to stop monitoring")
            time.sleep(10)