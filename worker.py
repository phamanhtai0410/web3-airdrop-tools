import os
import sys
import time
import json
import logging
import random
import redis
from datetime import datetime
from typing import Dict, Any, Optional

# Import our modules
from account_manager import AccountManager, Account
from proxy_manager import ProxyManager, Proxy

# Configure logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=f"{log_dir}/worker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

class AirdropWorker:
    def __init__(self):
        self.account_manager = AccountManager()
        self.proxy_manager = ProxyManager()
        self.redis = redis.Redis(host='redis', port=6379, db=0)
        self.worker_id = f"worker-{random.randint(1000, 9999)}"
        logging.info(f"Worker initialized with ID: {self.worker_id}")
        
        # Initialize browser automation components here
        # self.browser = BrowserAutomation(headless=True)
        
    def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task from the queue"""
        task_type = task_data.get('type')
        logging.info(f"Processing task: {task_type}")
        
        result = {
            'worker_id': self.worker_id,
            'task_id': task_data.get('task_id'),
            'type': task_type,
            'success': False,
            'message': '',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if task_type == 'create_account':
                result.update(self._create_account(task_data))
            elif task_type == 'register_platform':
                result.update(self._register_platform(task_data))
            elif task_type == 'airdrop_participation':
                result.update(self._participate_airdrop(task_data))
            else:
                result['message'] = f"Unknown task type: {task_type}"
                logging.warning(result['message'])
        except Exception as e:
            logging.error(f"Error processing task: {str(e)}", exc_info=True)
            result['success'] = False
            result['message'] = f"Error: {str(e)}"
        
        return result
    
    def _create_account(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new account"""
        email_domain = task_data.get('email_domain', 'gmail.com')
        use_proxy = task_data.get('use_proxy', True)
        
        # Get a proxy if needed
        proxy = None
        if use_proxy:
            proxy = self.proxy_manager.get_proxy()
            if not proxy:
                return {
                    'success': False,
                    'message': 'No proxies available'
                }
        
        # Generate account details
        username = f"user{int(time.time())}{random.randint(100, 999)}"
        email = f"{username}@{email_domain}"
        
        # Create account in the manager
        account = self.account_manager.create_account(
            email=email,
            proxy=proxy.address if proxy else None
        )
        
        # Here you would implement the actual browser automation
        # to register the Google account
        # For now, we'll simulate success
        success = random.random() < 0.9
        
        return {
            'success': success,
            'message': 'Account created successfully' if success else 'Failed to create account',
            'account_email': email,
            'account_password': account.password
        }
    
    def _register_platform(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register an account on a platform"""
        email = task_data.get('email')
        platform = task_data.get('platform')
        
        if not email or not platform:
            return {
                'success': False,
                'message': 'Missing email or platform'
            }
        
        # Get the account
        account = self.account_manager.get_account(email)
        if not account:
            return {
                'success': False,
                'message': f'Account not found: {email}'
            }
        
        # Get a proxy if account has one configured
        proxy = None
        if account.proxy:
            proxy_address = account.proxy
            # Parse proxy address to get components
            proxy_parts = proxy_address.replace("://", ":").split(":")
            if len(proxy_parts) >= 3:
                ip = proxy_parts[1].split("@")[-1]  # Handle auth
                port = int(proxy_parts[2])
                proxy = Proxy(ip=ip, port=port)
        
        # This is where you would implement the browser automation
        # to register on the specific platform
        # For now, we'll simulate success
        success = random.random() < 0.8
        
        if success:
            platform_username = f"{account.email.split('@')[0]}_{platform}"
            self.account_manager.update_platform_status(
                email=account.email,
                platform=platform,
                username=platform_username,
                registered=True
            )
        else:
            if proxy:
                self.proxy_manager.report_proxy_failure(proxy)
        
        return {
            'success': success,
            'message': f'Successfully registered on {platform}' if success else f'Failed to register on {platform}',
            'platform': platform,
            'platform_username': platform_username if success else None
        }
    
    def _participate_airdrop(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Participate in an airdrop"""
        email = task_data.get('email')
        airdrop_name = task_data.get('airdrop_name')
        platform = task_data.get('platform')
        actions = task_data.get('actions', [])
        
        if not email or not airdrop_name or not platform:
            return {
                'success': False,
                'message': 'Missing required task data'
            }
        
        # Get the account
        account = self.account_manager.get_account(email)
        if not account:
            return {
                'success': False,
                'message': f'Account not found: {email}'
            }
        
        # Check if account is registered on the platform
        if platform not in account.platforms or not account.platforms[platform]["registered"]:
            return {
                'success': False,
                'message': f'Account not registered on {platform}'
            }
        
        # This is where you would implement the browser automation
        # to complete the airdrop actions
        # For now, we'll simulate success
        success = random.random() < 0.75
        
        if success:
            # Update account notes
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            note = f"{timestamp}: Participated in {airdrop_name} airdrop on {platform} ({', '.join(actions)})"
            if account.notes:
                account.notes += f"\n{note}"
            else:
                account.notes = note
            
            # Save account updates
            self.account_manager.save_accounts()
        
        return {
            'success': success,
            'message': f'Successfully participated in {airdrop_name}' if success else f'Failed to participate in {airdrop_name}',
            'airdrop_name': airdrop_name,
            'platform': platform,
            'actions_completed': actions if success else []
        }
    
    def run(self):
        """Main worker loop"""
        logging.info(f"Worker {self.worker_id} starting up")
        
        while True:
            try:
                # Try to get a task from the queue
                task_data_raw = self.redis.blpop('task_queue', timeout=5)
                
                if task_data_raw:
                    _, task_json = task_data_raw
                    task_data = json.loads(task_json)
                    
                    # Process the task
                    result = self.process_task(task_data)
                    
                    # Publish the result
                    self.redis.rpush('result_queue', json.dumps(result))
                    logging.info(f"Task completed: {result['type']} - Success: {result['success']}")
                    
                    # Add a small delay between tasks
                    time.sleep(random.uniform(1, 3))
                else:
                    # No tasks in queue, sleep for a bit
                    time.sleep(5)
            
            except Exception as e:
                logging.error(f"Error in worker loop: {str(e)}", exc_info=True)
                time.sleep(30)  # Sleep longer on error


if __name__ == "__main__":
    worker = AirdropWorker()
    worker.run()