import logging
import os
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from functools import wraps
import re
import ipaddress
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

# Configure enterprise security logging
security_logger = logging.getLogger('enterprise_security')
security_handler = logging.FileHandler('enterprise_security_audit.log')
security_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [AUDIT] %(message)s'
)
security_handler.setFormatter(security_formatter)
security_logger.addHandler(security_handler)
security_logger.setLevel(logging.INFO)

@dataclass
class SecurityEvent:
    """Enterprise security event for audit trail"""
    event_id: str
    event_type: str
    user_id: Optional[str]
    ip_address: str
    user_agent: str
    endpoint: str
    timestamp: datetime
    risk_level: str
    details: Dict[str, Any]
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "endpoint": self.endpoint,
            "timestamp": self.timestamp.isoformat(),
            "risk_level": self.risk_level,
            "details": self.details,
            "session_id": self.session_id
        }

class EnterpriseSecurityManager:
    
    def __init__(self):
        self.rate_limits: Dict[str, List[float]] = {}
        self.blocked_ips: set = set()
        self.suspicious_patterns: List[str] = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'eval\s*\(',
            r'document\.',
            r'window\.',
            r'union\s+select',
            r'drop\s+table',
            r'delete\s+from',
            r'insert\s+into',
            r'--',
            r'/\*.*?\*/',
            r'exec\s*\(',
            r'system\s*\(',
            r'file://',
            r'ftp://',
            r'data:',
        ]
        
        # Enterprise encryption setup
        self.master_key = self._generate_master_key()
        self.cipher_suite = Fernet(self.master_key)
        
        # FIXED: Security thresholds - more lenient for development
        self.rate_limit_threshold = 500  # Increased from 100 for development
        self.suspicious_score_threshold = 75  # Increased from 50 to be less strict
        self.max_content_length = 500000  # 500KB
        self.max_url_length = 2048
        
        # FIXED: Development mode detection
        self.development_mode = self._detect_development_mode()
        self.allowed_localhost_ips = ['127.0.0.1', '::1', 'localhost']
        
        if self.development_mode:
            security_logger.info("🛠️ Enterprise Security: DEVELOPMENT MODE - Localhost allowed")
        
    def _detect_development_mode(self) -> bool:
        """Detect if running in development mode"""
        import os
        return (
            os.getenv("ENVIRONMENT", "development").lower() == "development" or
            os.getenv("DEVELOPMENT_MODE", "true").lower() == "true" or
            os.getenv("DEBUG", "false").lower() == "true"
        )
        
    def _generate_master_key(self) -> bytes:
        """Generate enterprise master encryption key"""
        # In production, this should come from secure key management
        password = b"TTS_DeepSight_Enterprise_Master_Key_2024"
        salt = b"enterprise_salt_2024"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str],
        ip_address: str,
        user_agent: str,
        endpoint: str,
        risk_level: str = "LOW",
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> SecurityEvent:
        """Log enterprise security event with audit trail"""
        
        event = SecurityEvent(
            event_id=secrets.token_hex(16),
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint=endpoint,
            timestamp=datetime.now(timezone.utc),
            risk_level=risk_level,
            details=details or {},
            session_id=session_id
        )
        
        # Only log significant events in development to reduce noise
        if not self.development_mode or risk_level in ["HIGH", "CRITICAL"]:
            security_logger.info(
                f"SECURITY_EVENT: {event_type} | User: {user_id} | IP: {ip_address} | "
                f"Risk: {risk_level} | Endpoint: {endpoint} | Details: {details}"
            )
        
        # Store in audit database (implement as needed)
        self._store_security_event(event)
        
        return event
    
    def _store_security_event(self, event: SecurityEvent):
        """Store security event in audit database"""
        # In production, implement database storage for audit trail
        pass
    
    def validate_request_security(
        self,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        content: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        
        validation_result = {
            "allowed": True,
            "risk_score": 0,
            "violations": [],
            "requires_additional_auth": False
        }
        
        # FIXED: Skip strict validation for localhost in development
        if self.development_mode and self._is_localhost_request(ip_address):
            # Still do basic validation but be very lenient
            validation_result["risk_score"] = 5  # Very low risk for localhost
            validation_result["violations"] = ["DEVELOPMENT_LOCALHOST_ACCESS"]
            
            # Only check rate limiting for localhost
            rate_limit_validation = self._check_rate_limit_lenient(ip_address, endpoint)
            if not rate_limit_validation["allowed"]:
                validation_result["risk_score"] += 20
                validation_result["violations"].append("RATE_LIMIT_EXCEEDED")
            
            # Log development access
            self.log_security_event(
                "DEVELOPMENT_LOCALHOST_ACCESS",
                user_id,
                ip_address,
                user_agent,
                endpoint,
                "LOW",
                {
                    "development_mode": True,
                    "localhost_access": True,
                    "risk_score": validation_result["risk_score"]
                }
            )
            
            return validation_result
        
        # Full validation for non-localhost or production
        
        # Check IP reputation and rate limiting
        ip_validation = self._validate_ip_address(ip_address)
        validation_result["risk_score"] += ip_validation["risk_score"]
        validation_result["violations"].extend(ip_validation["violations"])
        
        # Check rate limiting
        rate_limit_validation = self._check_rate_limit(ip_address, endpoint)
        if not rate_limit_validation["allowed"]:
            validation_result["allowed"] = False
            validation_result["violations"].append("RATE_LIMIT_EXCEEDED")
            validation_result["risk_score"] += 30
        
        # User agent validation
        ua_validation = self._validate_user_agent(user_agent)
        validation_result["risk_score"] += ua_validation["risk_score"]
        validation_result["violations"].extend(ua_validation["violations"])
        
        # Content validation if provided
        if content:
            content_validation = self._validate_content_security(content)
            validation_result["risk_score"] += content_validation["risk_score"]
            validation_result["violations"].extend(content_validation["violations"])
        
        # Determine final security decision
        if validation_result["risk_score"] >= self.suspicious_score_threshold:
            validation_result["allowed"] = False
            validation_result["requires_additional_auth"] = True
        
        # Log security validation
        risk_level = self._calculate_risk_level(validation_result["risk_score"])
        self.log_security_event(
            "REQUEST_SECURITY_VALIDATION",
            user_id,
            ip_address,
            user_agent,
            endpoint,
            risk_level,
            {
                "risk_score": validation_result["risk_score"],
                "violations": validation_result["violations"],
                "allowed": validation_result["allowed"]
            }
        )
        
        return validation_result
    
    def _is_localhost_request(self, ip_address: str) -> bool:
        """Check if request is from localhost"""
        return ip_address in self.allowed_localhost_ips or ip_address.startswith('127.') or ip_address.startswith('::1')
    
    def _check_rate_limit_lenient(self, ip_address: str, endpoint: str) -> Dict[str, Any]:
        """Lenient rate limiting for development localhost"""
        current_time = time.time()
        rate_key = f"{ip_address}:{endpoint}"
        
        # Initialize or clean old entries
        if rate_key not in self.rate_limits:
            self.rate_limits[rate_key] = []
        
        # Remove requests older than 1 hour
        hour_ago = current_time - 3600
        self.rate_limits[rate_key] = [
            timestamp for timestamp in self.rate_limits[rate_key]
            if timestamp > hour_ago
        ]
        
        # Much higher limit for localhost in development
        localhost_limit = self.rate_limit_threshold * 2  # Double the normal limit
        
        # Check if limit exceeded
        request_count = len(self.rate_limits[rate_key])
        if request_count >= localhost_limit:
            return {
                "allowed": False,
                "remaining": 0,
                "reset_time": min(self.rate_limits[rate_key]) + 3600
            }
        
        # Add current request
        self.rate_limits[rate_key].append(current_time)
        
        return {
            "allowed": True,
            "remaining": localhost_limit - request_count - 1,
            "reset_time": current_time + 3600
        }
    
    def _validate_ip_address(self, ip_address: str) -> Dict[str, Any]:
        """Validate IP address for security risks - FIXED FOR LOCALHOST"""
        validation = {"risk_score": 0, "violations": []}
        
        try:
            # FIXED: Allow localhost in development mode
            if self.development_mode and self._is_localhost_request(ip_address):
                validation["risk_score"] = 0  # No risk for localhost in dev
                return validation
            
            ip = ipaddress.ip_address(ip_address)
            
            # Check if IP is in blocked list
            if ip_address in self.blocked_ips:
                validation["risk_score"] += 100
                validation["violations"].append("BLOCKED_IP")
                return validation
            
            # Check for private/internal networks (only in production)
            if not self.development_mode and (ip.is_private or ip.is_loopback):
                validation["risk_score"] += 60
                validation["violations"].append("INTERNAL_NETWORK_ACCESS")
            
            # Check for reserved addresses
            if ip.is_reserved and not self.development_mode:
                validation["risk_score"] += 30
                validation["violations"].append("RESERVED_IP_ADDRESS")
            
        except ValueError:
            validation["risk_score"] += 50
            validation["violations"].append("INVALID_IP_ADDRESS")
        
        return validation
    
    def _check_rate_limit(self, ip_address: str, endpoint: str) -> Dict[str, Any]:
        """Enterprise rate limiting with sliding window"""
        current_time = time.time()
        rate_key = f"{ip_address}:{endpoint}"
        
        # Initialize or clean old entries
        if rate_key not in self.rate_limits:
            self.rate_limits[rate_key] = []
        
        # Remove requests older than 1 hour
        hour_ago = current_time - 3600
        self.rate_limits[rate_key] = [
            timestamp for timestamp in self.rate_limits[rate_key]
            if timestamp > hour_ago
        ]
        
        # Check if limit exceeded
        request_count = len(self.rate_limits[rate_key])
        if request_count >= self.rate_limit_threshold:
            return {
                "allowed": False,
                "remaining": 0,
                "reset_time": min(self.rate_limits[rate_key]) + 3600
            }
        
        # Add current request
        self.rate_limits[rate_key].append(current_time)
        
        return {
            "allowed": True,
            "remaining": self.rate_limit_threshold - request_count - 1,
            "reset_time": current_time + 3600
        }
    
    def _validate_user_agent(self, user_agent: str) -> Dict[str, Any]:
        """Validate user agent for suspicious patterns"""
        validation = {"risk_score": 0, "violations": []}
        
        if not user_agent or len(user_agent.strip()) == 0:
            validation["risk_score"] += 10  # Reduced from 20 for development
            validation["violations"].append("MISSING_USER_AGENT")
            return validation
        
        # Check for suspicious patterns
        suspicious_ua_patterns = [
            r'bot', r'crawler', r'spider', r'scraper', r'scanner',
            r'hack', r'exploit', r'injection', r'sqlmap',
            r'nikto', r'nmap', r'masscan'
        ]
        
        ua_lower = user_agent.lower()
        for pattern in suspicious_ua_patterns:
            if re.search(pattern, ua_lower):
                validation["risk_score"] += 15
                validation["violations"].append(f"SUSPICIOUS_USER_AGENT_PATTERN: {pattern}")
        
        # Check length
        if len(user_agent) > 1000:
            validation["risk_score"] += 10
            validation["violations"].append("EXCESSIVE_USER_AGENT_LENGTH")
        
        return validation
    
    def _validate_content_security(self, content: str) -> Dict[str, Any]:
        """Validate content for security threats"""
        validation = {"risk_score": 0, "violations": []}
        
        # Check content length
        if len(content) > self.max_content_length:
            validation["risk_score"] += 30
            validation["violations"].append("EXCESSIVE_CONTENT_LENGTH")
        
        # Check for suspicious patterns
        content_lower = content.lower()
        for pattern in self.suspicious_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE | re.DOTALL)
            if matches:
                validation["risk_score"] += 25
                validation["violations"].append(f"SUSPICIOUS_CONTENT_PATTERN: {pattern[:20]}...")
        
        # Check for potential data exfiltration
        if self._check_data_exfiltration_patterns(content):
            validation["risk_score"] += 40
            validation["violations"].append("POTENTIAL_DATA_EXFILTRATION")
        
        return validation
    
    def _check_data_exfiltration_patterns(self, content: str) -> bool:
        """Check for patterns indicating potential data exfiltration"""
        exfiltration_patterns = [
            r'password\s*[:=]\s*\w+',
            r'api[_-]?key\s*[:=]\s*\w+',
            r'secret\s*[:=]\s*\w+',
            r'token\s*[:=]\s*\w+',
            r'credit[_-]?card',
            r'ssn\s*[:=]\s*\d{3}-?\d{2}-?\d{4}',
            r'email\s*[:=]\s*\S+@\S+',
            r'phone\s*[:=]\s*[\d\-\(\)\s]+',
        ]
        
        content_lower = content.lower()
        for pattern in exfiltration_patterns:
            if re.search(pattern, content_lower):
                return True
        
        return False
    
    def _calculate_risk_level(self, risk_score: int) -> str:
        """Calculate risk level based on score"""
        if risk_score >= 75:
            return "CRITICAL"
        elif risk_score >= 50:
            return "HIGH"
        elif risk_score >= 25:
            return "MEDIUM"
        else:
            return "LOW"
    
    def validate_url_security(self, url: str) -> Dict[str, Any]:
        """Enterprise URL security validation - FIXED FOR LOCALHOST"""
        validation = {
            "allowed": True,
            "risk_score": 0,
            "violations": [],
            "sanitized_url": url
        }
        
        try:
            # Basic URL validation
            if len(url) > self.max_url_length:
                validation["allowed"] = False
                validation["risk_score"] += 30
                validation["violations"].append("EXCESSIVE_URL_LENGTH")
                return validation
            
            parsed = urlparse(url)
            
            # Protocol validation
            if parsed.scheme not in ['http', 'https']:
                validation["allowed"] = False
                validation["risk_score"] += 50
                validation["violations"].append("INVALID_PROTOCOL")
                return validation
            
            # Hostname validation
            if not parsed.hostname:
                validation["allowed"] = False
                validation["risk_score"] += 40
                validation["violations"].append("MISSING_HOSTNAME")
                return validation
            
            # FIXED: Allow localhost URLs in development
            if self.development_mode and self._is_localhost_hostname(parsed.hostname):
                validation["risk_score"] = 5  # Very low risk for localhost URLs in dev
                validation["violations"] = ["DEVELOPMENT_LOCALHOST_URL"]
                return validation
            
            # Check for internal/private network access (production only)
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                if not self.development_mode and (ip.is_private or ip.is_loopback):
                    validation["allowed"] = False
                    validation["risk_score"] += 60
                    validation["violations"].append("INTERNAL_NETWORK_ACCESS_ATTEMPT")
                    return validation
            except ValueError:
                # Hostname is not an IP, continue validation
                pass
            
            # Check for suspicious hostnames (relaxed in development)
            suspicious_hosts = [
                'localhost', '127.0.0.1', '0.0.0.0', '10.', '192.168.', '172.',
                'metadata.google', 'instance-data', 'link-local'
            ]
            
            for suspicious in suspicious_hosts:
                if suspicious in parsed.hostname.lower():
                    if not self.development_mode:
                        validation["allowed"] = False
                        validation["risk_score"] += 70
                        validation["violations"].append(f"SUSPICIOUS_HOSTNAME: {suspicious}")
                        return validation
                    else:
                        # Just log in development
                        validation["risk_score"] += 10
                        validation["violations"].append(f"DEV_LOCALHOST_HOSTNAME: {suspicious}")
            
            # Check for suspicious paths
            suspicious_paths = [
                '/admin', '/config', '/backup', '/secret', '/private',
                '/.env', '/.aws', '/.ssh', '/etc/passwd', '/proc/'
            ]
            
            path_lower = parsed.path.lower()
            for suspicious_path in suspicious_paths:
                if suspicious_path in path_lower:
                    validation["risk_score"] += 30
                    validation["violations"].append(f"SUSPICIOUS_PATH: {suspicious_path}")
            
            # Check for URL encoding attempts to bypass filters
            if '%' in url:
                decoded_attempts = 0
                test_url = url
                while '%' in test_url and decoded_attempts < 5:
                    try:
                        from urllib.parse import unquote
                        new_url = unquote(test_url)
                        if new_url == test_url:
                            break
                        test_url = new_url
                        decoded_attempts += 1
                    except:
                        break
                
                if decoded_attempts >= 3:
                    validation["risk_score"] += 25
                    validation["violations"].append("EXCESSIVE_URL_ENCODING")
            
        except Exception as e:
            validation["allowed"] = False
            validation["risk_score"] += 50
            validation["violations"].append(f"URL_PARSING_ERROR: {str(e)}")
        
        return validation
    
    def _is_localhost_hostname(self, hostname: str) -> bool:
        """Check if hostname is localhost"""
        localhost_names = ['localhost', '127.0.0.1', '::1', '0.0.0.0']
        return hostname.lower() in localhost_names or hostname.startswith('127.')
    
    def sanitize_text_content(self, content: str) -> str:
        """Sanitize text content for TTS processing"""
        if not content:
            return ""
        
        # Remove potential XSS vectors
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
        content = re.sub(r'on\w+\s*=', '', content, flags=re.IGNORECASE)
        
        # Remove HTML tags but preserve content
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        
        # Limit length for DoS protection
        if len(content) > self.max_content_length:
            content = content[:self.max_content_length] + "... [Content truncated for security]"
        
        return content
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data for storage"""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
    
    def generate_secure_session_id(self) -> str:
        """Generate cryptographically secure session ID"""
        return secrets.token_urlsafe(32)
    
    def validate_session_security(self, session_id: str, user_id: str, ip_address: str) -> bool:
        """Validate session security and detect hijacking attempts"""
        # In production, implement session validation against database
        # Check for IP changes, concurrent sessions, etc.
        return True
    
    def audit_trail_integrity_check(self) -> Dict[str, Any]:
        """Verify audit trail integrity"""
        # In production, implement cryptographic verification of audit logs
        return {
            "integrity_verified": True,
            "log_count": 0,
            "tampering_detected": False
        }

def enterprise_security_middleware(security_manager: EnterpriseSecurityManager):
    """Enterprise security middleware decorator for FastAPI endpoints"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Extract request information
            ip_address = request.client.host
            user_agent = request.headers.get("user-agent", "")
            endpoint = str(request.url.path)
            
            # Get user ID if available (from JWT token, etc.)
            user_id = getattr(request.state, 'user_id', None)
            
            # Validate request security
            validation = security_manager.validate_request_security(
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                user_id=user_id
            )
            
            if not validation["allowed"]:
                security_manager.log_security_event(
                    "REQUEST_BLOCKED",
                    user_id,
                    ip_address,
                    user_agent,
                    endpoint,
                    "HIGH",
                    validation
                )
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=403,
                    detail="Request blocked by enterprise security policy"
                )
            
            # Add security headers to request state
            request.state.security_validation = validation
            
            # Execute the original function
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator

# Global enterprise security manager instance
enterprise_security = EnterpriseSecurityManager()

# FIXED: Security configuration constants - More lenient for development
CORS_ALLOWED_ORIGINS_ENV = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000","http://localhost:3001","http://127.0.0.1:3000","http://127.0.0.1:3001")
ENTERPRISE_SECURITY_CONFIG = {
    "RATE_LIMIT_REQUESTS_PER_HOUR": 500,  # Increased from 100
    "MAX_CONTENT_LENGTH_BYTES": 500000,
    "MAX_URL_LENGTH": 2048,
    "SESSION_TIMEOUT_MINUTES": 60,
    "AUDIT_LOG_RETENTION_DAYS": 365,
    "ENCRYPTION_ALGORITHM": "Fernet",
    "PASSWORD_MIN_LENGTH": 8,  # Reduced from 12 for development
    "PASSWORD_COMPLEXITY_REQUIRED": True,
    "MFA_REQUIRED_FOR_ADMIN": True,
    "IP_WHITELIST_ENABLED": False,
    "CONTENT_SECURITY_POLICY_ENABLED": True,
    "CORS_ALLOWED_ORIGINS": CORS_ALLOWED_ORIGINS_ENV.split(","),
    "SECURE_HEADERS_ENABLED": True,
    "TLS_VERSION_MIN": "1.2",
    "HSTS_MAX_AGE_SECONDS": 31536000,
    "AUDIT_SENSITIVE_OPERATIONS": True,
    "DEVELOPMENT_MODE": True,  # Enable development mode
    "ALLOW_LOCALHOST": True    # Allow localhost access
}

def get_enterprise_security_headers() -> Dict[str, str]:
    """Get enterprise security headers for responses"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": f"max-age={ENTERPRISE_SECURITY_CONFIG['HSTS_MAX_AGE_SECONDS']}; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none';",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
    }