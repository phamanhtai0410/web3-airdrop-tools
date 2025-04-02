import json
import os
import logging
import random
import string
import time
import re
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
import hashlib
import base64
import secrets

@dataclass
class Account:
    email: str
    password: str
    recovery_email: Optional[str] = None
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    created_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    platforms: Dict[str, Dict[str, Any]] = None
    notes: str = ""
    password_hash: Optional[str] = None
    
    def __post_init__(self):
        # Initialize platforms if None
        if self.platforms is None:
            self.platforms = {
                "twitter": {"username": "", "registered": False, "last_activity": None},
                "telegram": {"username": "", "registered": False, "last_activity": None},
                "discord": {"username": "", "registered": False, "last_activity": None}
            }
        
        # Hash password if not already hashed
        if not self.password_hash:
            # Store the hash instead of the actual password
            self.password_hash = self._hash_password(self.password)
            
    def _hash_password(self, password: str) -> str:
        """Create a secure hash of the password"""
        salt = secrets.token_bytes(16)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return base64.b64encode(salt + key).decode('utf-8')
    
    def verify_password(self, password: str) -> bool:
        """Verify if the provided password is correct"""
        if not self.password_hash:
            return False
            
        try:
            stored = base64.b64decode(self.password_hash)
            salt, key = stored[:16], stored[16:]
            new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return new_key == key
        except:
            return False


class AccountManager:
    def __init__(self, storage_file="accounts.json", encryption_key=None):
        self.storage_file = storage_file
        self.accounts: List[Account] = []
        self.encryption_key = encryption_key or os.environ.get("ACCOUNT_ENCRYPTION_KEY")
        self.setup_logging()
        self.load_accounts()
        
    def setup_logging(self):
        """Set up logging for account operations"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        logging.basicConfig(
            filename=f"{log_dir}/account_manager_{datetime.now().strftime('%Y%m%d')}.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def load_accounts(self):
        """Load accounts from storage file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.accounts = []
                    for acc_data in data:
                        # Handle the transition from old format to new format
                        if 'password_hash' not in acc_data and 'password' in acc_data:
                            # Keep password temporarily for conversion
                            password = acc_data['password']
                            account = Account(**acc_data)
                            # Verify the password was properly hashed
                            if not account.verify_password(password):
                                # If conversion failed, fix it
                                account.password_hash = account._hash_password(password)
                        else:
                            account = Account(**acc_data)
                        self.accounts.append(account)
                logging.info(f"Loaded {len(self.accounts)} accounts from storage")
            else:
                logging.info("No existing account storage found. Starting fresh.")
        except Exception as e:
            logging.error(f"Error loading accounts: {str(e)}")
            # Create backup of corrupted file if it exists
            if os.path.exists(self.storage_file):
                backup_file = f"{self.storage_file}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                try:
                    os.rename(self.storage_file, backup_file)
                    logging.info(f"Created backup of corrupted account file: {backup_file}")
                except:
                    logging.error("Failed to create backup of corrupted file")
    
    def save_accounts(self):
        """Save accounts to storage file"""
        try:
            # Create a temporary file first
            temp_file = f"{self.storage_file}.tmp"
            with open(temp_file, 'w') as f:
                # Convert accounts to dict and ensure sensitive data is protected
                account_data = []
                for acc in self.accounts:
                    acc_dict = asdict(acc)
                    # Remove plaintext password before storing
                    if 'password' in acc_dict:
                        del acc_dict['password']
                    account_data.append(acc_dict)
                
                json.dump(account_data, f, indent=4)
            
            # Atomically replace the original file
            os.replace(temp_file, self.storage_file)
            logging.info(f"Saved {len(self.accounts)} accounts to storage")
        except Exception as e:
            logging.error(f"Error saving accounts: {str(e)}")
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    def generate_password(self, length=16):
        """Generate a strong random password"""
        # Include uppercase, lowercase, digits, and special characters
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special = "!@#$%^&*"
        
        # Ensure at least one of each character type
        password = [
            random.choice(uppercase),
            random.choice(lowercase),
            random.choice(digits),
            random.choice(special)
        ]
        
        # Fill the rest randomly
        all_chars = uppercase + lowercase + digits + special
        password.extend(random.choice(all_chars) for _ in range(length - 4))
        
        # Shuffle the password
        random.shuffle(password)
        return ''.join(password)
    
    def create_account(self, email=None, password=None, recovery_email=None, proxy=None):
        """Create a new account entry"""
        if email and not self.validate_email(email):
            logging.error(f"Invalid email format: {email}")
            raise ValueError(f"Invalid email format: {email}")
            
        if recovery_email and not self.validate_email(recovery_email):
            logging.error(f"Invalid recovery email format: {recovery_email}")
            raise ValueError(f"Invalid recovery email format: {recovery_email}")
        
        if not email:
            # Generate a random email if none provided
            username = ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
            email = f"{username}@example.com"
        
        # Check if account already exists
        if self.get_account(email):
            logging.warning(f"Account already exists: {email}")
            raise ValueError(f"Account already exists: {email}")
        
        if not password:
            password = self.generate_password()
            
        account = Account(
            email=email,
            password=password,  # Will be hashed in __post_init__
            recovery_email=recovery_email,
            proxy=proxy,
            user_agent=self._get_random_user_agent()
        )
        
        self.accounts.append(account)
        self.save_accounts()
        logging.info(f"Created new account: {email}")
        return account
    
    def _get_random_user_agent(self):
        """Get a random user agent string"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
        ]
        return random.choice(user_agents)
    
    def update_platform_status(self, email, platform, username, registered=True):
        """Update platform registration status for an account"""
        for account in self.accounts:
            if account.email == email:
                if platform in account.platforms:
                    account.platforms[platform]["username"] = username
                    account.platforms[platform]["registered"] = registered
                    account.platforms[platform]["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    account.platforms[platform] = {
                        "username": username,
                        "registered": registered,
                        "last_activity": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                self.save_accounts()
                logging.info(f"Updated {platform} status for {email}")
                return True
        logging.warning(f"Account not found: {email}")
        return False
    
    def get_accounts_by_platform(self, platform, registered_only=True):
        """Get all accounts registered on a specific platform"""
        result = []
        for account in self.accounts:
            if platform in account.platforms:
                if not registered_only or account.platforms[platform]["registered"]:
                    result.append(account)
        return result
    
    def get_account(self, email):
        """Get account by email"""
        for account in self.accounts:
            if account.email == email:
                return account
        return None
    
    def delete_account(self, email):
        """Delete an account"""
        for i, account in enumerate(self.accounts):
            if account.email == email:
                del self.accounts[i]
                self.save_accounts()
                logging.info(f"Deleted account: {email}")
                return True
        logging.warning(f"Account not found for deletion: {email}")
        return False
    
    def bulk_create_accounts(self, count=5, domain="example.com", with_proxy=False, proxy_list=None):
        """Create multiple accounts at once"""
        created = []
        
        for i in range(count):
            try:
                # Generate unique username to avoid collisions
                timestamp = int(time.time() * 1000)
                random_suffix = ''.join(random.choice(string.ascii_lowercase) for _ in range(4))
                username = f"user{timestamp}{random_suffix}"
                email = f"{username}@{domain}"
                password = self.generate_password()
                
                proxy = None
                if with_proxy and proxy_list:
                    proxy = random.choice(proxy_list)
                    
                account = self.create_account(
                    email=email,
                    password=password,
                    proxy=proxy
                )
                created.append(account)
                
                # Small delay to avoid possible issues
                time.sleep(0.5)
            except Exception as e:
                logging.error(f"Error creating account #{i}: {str(e)}")
            
        return created
        
    def search_accounts(self, query=None, platform=None, registered_only=False):
        """Search accounts by various criteria"""
        results = []
        
        for account in self.accounts:
            # Skip if platform is specified and account isn't registered on it
            if platform:
                if (platform not in account.platforms or 
                    (registered_only and not account.platforms[platform]["registered"])):
                    continue
                    
            # Skip if query doesn't match
            if query:
                query = query.lower()
                if not (query in account.email.lower() or 
                        (account.notes and query in account.notes.lower())):
                    # Check platform usernames
                    found = False
                    for p, details in account.platforms.items():
                        if details["username"] and query in details["username"].lower():
                            found = True
                            break
                    if not found:
                        continue
            
            results.append(account)
            
        return results