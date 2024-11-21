import json
from datetime import datetime, timedelta
import secrets
import string
import hashlib
import uuid
import streamlit as st
import base64


class PasswordManager:
    def __init__(self):
        # Get API keys and their metadata from secrets
        self.api_keys = st.secrets.get("api_keys", {})
        self.api_metadata = st.secrets.get(
            "api_metadata", {})  # Add metadata section
        self.daily_limit = st.secrets.get(
            "settings", {}).get("daily_limit", 100)

        # Initialize usage tracking in session state
        if 'usage_stats' not in st.session_state:
            st.session_state.usage_stats = {}
            for key in self.api_keys:
                st.session_state.usage_stats[key] = {
                    'daily_usage': {},
                    'total_usage': 0,
                    'last_used': None
                }

    def verify_password(self, password):
        """Verify if password exists and not expired"""
        current_date = datetime.now().strftime("%Y-%m-%d")

        for key_name, api_key in self.api_keys.items():
            if api_key == password:
                # Check expiration if set
                if key_name in self.api_metadata:
                    expiry_date = self.api_metadata[key_name].get('expires')
                    if expiry_date and expiry_date < current_date:
                        return False
                return True
        return False

    def track_usage(self, password, text_length, ip_address):
        """Track API key usage"""
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Find the key in secrets
        for key_name, api_key in self.api_keys.items():
            if api_key == password:
                stats = st.session_state.usage_stats[key_name]

                # Initialize daily usage if needed
                if current_date not in stats['daily_usage']:
                    stats['daily_usage'][current_date] = 0

                # Check daily limit
                if stats['daily_usage'][current_date] >= self.daily_limit:
                    return False

                # Update usage
                stats['daily_usage'][current_date] += 1
                stats['total_usage'] += 1
                stats['last_used'] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S")
                return True

        return False

    def get_user_stats(self, password):
        """Get user statistics"""
        for key_name, api_key in self.api_keys.items():
            if api_key == password:
                stats = st.session_state.usage_stats[key_name]
                today = datetime.now().strftime("%Y-%m-%d")
                return {
                    "total_usage": stats['total_usage'],
                    "today_usage": stats['daily_usage'].get(today, 0),
                    "daily_limit": self.daily_limit,
                    "remaining_today": self.daily_limit - stats['daily_usage'].get(today, 0),
                    "last_used": stats['last_used']
                }
        return None

    def get_usage_stats(self):
        """Get overall usage statistics"""
        total_passwords = len(self.api_keys)
        active_passwords = sum(1 for key in self.api_metadata
                               if not self.api_metadata[key].get('expires') or
                               self.api_metadata[key].get('expires') >= datetime.now().strftime("%Y-%m-%d"))

        return {
            'total_passwords': total_passwords,
            'active_passwords': active_passwords,
            'last_modified': datetime.now().strftime("%Y-%m-%d")
        }

    def list_all_passwords(self):
        """List all passwords with their details"""
        password_list = []
        current_date = datetime.now().strftime("%Y-%m-%d")

        for key_name, api_key in self.api_keys.items():
            stats = st.session_state.usage_stats.get(key_name, {})
            metadata = self.api_metadata.get(key_name, {})

            password_info = {
                'key_name': key_name,
                'password': api_key,
                'created': metadata.get('created', 'Unknown'),
                'expires': metadata.get('expires', 'Never'),
                'days_valid': metadata.get('days_valid', 'Unknown'),
                'usage_count': stats.get('total_usage', 0),
                'last_used': stats.get('last_used', 'Never'),
                'is_expired': metadata.get('expires', 'Never') < current_date if metadata.get('expires') else False
            }
            password_list.append(password_info)

        return password_list

    def get_recent_activity(self):
        """Get recent password usage activity"""
        activity = []
        for key_name, api_key in self.api_keys.items():
            stats = st.session_state.usage_stats[key_name]
            if stats.get('last_used'):
                activity.append({
                    'password': f"...{api_key[-4:]}",  # Show only last 4 chars
                    'last_used': stats['last_used'],
                    'usage_count': stats['total_usage'],
                    'expires': self.api_metadata[key_name].get('expires', 'Never')
                })
        return sorted(activity, key=lambda x: x['last_used'] if x['last_used'] else '', reverse=True)[:10]

    def get_system_health(self):
        """Get system health metrics"""
        try:
            import time
            start = time.time()
            # Test API response time
            import translators.server as tss
            tss.bing("test", to_language="en")
            api_time = time.time() - start

            total_usage = sum(stats['total_usage']
                              for stats in st.session_state.usage_stats.values())
            success_rate = "100.0%" if total_usage == 0 else f"{100.0:.1f}%"

            return {
                'api_response_time': f"{api_time:.2f}s",
                'success_rate': success_rate,
                'error_rate': "0.0%"
            }
        except Exception as e:
            return {
                'api_response_time': 'N/A',
                'success_rate': 'N/A',
                'error_rate': 'N/A'
            }

    def add_password(self, days_valid=30, prefix="tr"):
        """Generate a new password and add it to secrets"""
        try:
            # Get current timestamp for both key and metadata
            current_time = datetime.now()
            timestamp = current_time.strftime("%y%m%d")
            created_date = current_time.strftime("%Y-%m-%d")

            # Generate a strong API-like key with more readable format
            # Format: prefix_randomstring_YYMMDD
            random_str = ''.join(secrets.choice(
                string.ascii_letters + string.digits) for _ in range(16))
            password = f"{prefix}_{random_str}_{timestamp}"

            # Generate a more readable key name
            # Format: prefix_YYMMDD_shortid
            short_id = ''.join(secrets.choice(
                string.ascii_uppercase + string.digits) for _ in range(6))
            key_name = f"{prefix}_{timestamp}_{short_id}"

            # Calculate expiration date
            expiry_date = (
                current_time + timedelta(days=days_valid)).strftime("%Y-%m-%d")

            # Add to session state
            if 'api_keys' not in st.session_state:
                st.session_state.api_keys = dict(self.api_keys)
            st.session_state.api_keys[key_name] = password

            if 'api_metadata' not in st.session_state:
                st.session_state.api_metadata = dict(self.api_metadata)
            st.session_state.api_metadata[key_name] = {
                'expires': expiry_date,
                'created': created_date,
                'days_valid': days_valid
            }

            # Initialize usage tracking for new key
            if 'usage_stats' not in st.session_state:
                st.session_state.usage_stats = {}
            st.session_state.usage_stats[key_name] = {
                'daily_usage': {},
                'total_usage': 0,
                'last_used': None,
                'created': created_date
            }

            # Update local references
            self.api_keys = st.session_state.api_keys
            self.api_metadata = st.session_state.api_metadata

            # Show instructions for permanent storage
            st.info(f"""
            To make this password permanent, add these lines to your secrets.toml:
            
            [api_keys]
            {key_name} = "{password}"
            
            [api_metadata]
            {key_name} = {{ expires = "{expiry_date}", created = "{created_date}", days_valid = {days_valid} }}
            """)

            return password

        except Exception as e:
            st.error(f"Error adding password: {str(e)}")
            return None

    def extend_password(self, password, additional_days):
        """Extend the validity of a password"""
        try:
            # Find the key name for this password
            key_name = None
            for k, v in self.api_keys.items():
                if v == password:
                    key_name = k
                    break

            if not key_name:
                return False

            # Get current expiry
            current_expiry = self.api_metadata[key_name].get('expires')
            if current_expiry:
                # Calculate new expiry date
                current_date = datetime.strptime(current_expiry, "%Y-%m-%d")
                new_expiry = (
                    current_date + timedelta(days=additional_days)).strftime("%Y-%m-%d")

                # Update in session state
                if 'api_metadata' not in st.session_state:
                    st.session_state.api_metadata = self.api_metadata.copy()
                st.session_state.api_metadata[key_name]['expires'] = new_expiry

                # Update local reference
                self.api_metadata = st.session_state.api_metadata
                return True

            return False

        except Exception as e:
            st.error(f"Error extending password: {str(e)}")
            return False
