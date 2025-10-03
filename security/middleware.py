"""
Security Middleware for the Merchant Financial Agent

Implements security measures including rate limiting, request validation,
and security headers for enhanced protection against common attacks.
"""

import time
import logging
from typing import Dict, Any
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth.models import User

from .audit import get_audit_manager, log_security_incident

logger = logging.getLogger(__name__)


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware to prevent API abuse
    
    Implements sliding window rate limiting with configurable limits
    for different types of requests and users.
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.rate_limits = {
            'api': {'requests': 100, 'window': 3600},  # 100 requests per hour
            'chat': {'requests': 50, 'window': 3600},  # 50 chat requests per hour
            'function_call': {'requests': 200, 'window': 3600},  # 200 function calls per hour
            'default': {'requests': 1000, 'window': 3600}  # 1000 requests per hour
        }
    
    def process_request(self, request: HttpRequest) -> HttpResponse:
        """Process incoming request for rate limiting"""
        if not self._should_rate_limit(request):
            return None
        
        # Get rate limit key
        rate_limit_key = self._get_rate_limit_key(request)
        endpoint_type = self._get_endpoint_type(request.path)
        
        # Check rate limit
        if self._is_rate_limited(rate_limit_key, endpoint_type):
            # Log security incident
            log_security_incident(
                merchant=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                event_type='RATE_LIMIT_EXCEEDED',
                description=f'Rate limit exceeded for {endpoint_type} endpoint',
                severity='MEDIUM',
                request=request
            )
            
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.',
                'retry_after': self._get_retry_after(rate_limit_key, endpoint_type)
            }, status=429)
        
        return None
    
    def _should_rate_limit(self, request: HttpRequest) -> bool:
        """Determine if request should be rate limited"""
        # Skip rate limiting for admin users
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff:
            return False
        
        # Skip rate limiting for static files
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return False
        
        return True
    
    def _get_rate_limit_key(self, request: HttpRequest) -> str:
        """Generate rate limit key for request"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"rate_limit:user:{request.user.id}"
        else:
            return f"rate_limit:ip:{self._get_client_ip(request)}"
    
    def _get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type for rate limiting"""
        if path.startswith('/api/chat/'):
            return 'chat'
        elif path.startswith('/api/function-call/'):
            return 'function_call'
        elif path.startswith('/api/'):
            return 'api'
        else:
            return 'default'
    
    def _is_rate_limited(self, key: str, endpoint_type: str) -> bool:
        """Check if request is rate limited"""
        limits = self.rate_limits.get(endpoint_type, self.rate_limits['default'])
        
        # Get current request count
        current_count = cache.get(key, 0)
        
        if current_count >= limits['requests']:
            return True
        
        # Increment counter
        if current_count == 0:
            cache.set(key, 1, limits['window'])
        else:
            cache.incr(key)
        
        return False
    
    def _get_retry_after(self, key: str, endpoint_type: str) -> int:
        """Get retry after time in seconds"""
        limits = self.rate_limits.get(endpoint_type, self.rate_limits['default'])
        ttl = cache.ttl(key)
        return ttl if ttl > 0 else limits['window']
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Security headers middleware for enhanced protection
    
    Adds security headers to responses to protect against common attacks.
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add security headers to response"""
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.openai.com https://api.anthropic.com; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp
        
        # X-Frame-Options
        response['X-Frame-Options'] = 'DENY'
        
        # X-Content-Type-Options
        response['X-Content-Type-Options'] = 'nosniff'
        
        # X-XSS-Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy
        response['Permissions-Policy'] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "speaker=()"
        )
        
        return response


class RequestValidationMiddleware(MiddlewareMixin):
    """
    Request validation middleware for security
    
    Validates requests for potential security issues and malicious content.
    """
    
    def process_request(self, request: HttpRequest) -> HttpResponse:
        """Validate incoming request"""
        
        # Check for suspicious patterns
        if self._is_suspicious_request(request):
            log_security_incident(
                merchant=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                event_type='SUSPICIOUS_REQUEST',
                description=f'Suspicious request detected: {request.path}',
                severity='HIGH',
                request=request
            )
            
            return JsonResponse({
                'error': 'Request blocked',
                'message': 'Request contains potentially malicious content'
            }, status=400)
        
        # Validate JSON requests
        if request.content_type == 'application/json' and request.method in ['POST', 'PUT', 'PATCH']:
            if not self._is_valid_json_request(request):
                log_security_incident(
                    merchant=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                    event_type='INVALID_JSON_REQUEST',
                    description='Invalid JSON request format',
                    severity='MEDIUM',
                    request=request
                )
                
                return JsonResponse({
                    'error': 'Invalid request format',
                    'message': 'Request must contain valid JSON'
                }, status=400)
        
        return None
    
    def _is_suspicious_request(self, request: HttpRequest) -> bool:
        """Check for suspicious request patterns"""
        
        # Check for SQL injection patterns
        sql_patterns = [
            'union select', 'drop table', 'delete from', 'insert into',
            'update set', 'or 1=1', 'and 1=1', 'exec(', 'execute('
        ]
        
        # Check for XSS patterns
        xss_patterns = [
            '<script', 'javascript:', 'onload=', 'onerror=', 'onclick=',
            'document.cookie', 'window.location', 'eval('
        ]
        
        # Check for path traversal
        path_patterns = ['../', '..\\', '/etc/passwd', '/windows/system32']
        
        # Combine all patterns
        suspicious_patterns = sql_patterns + xss_patterns + path_patterns
        
        # Check URL path
        path_lower = request.path.lower()
        if any(pattern in path_lower for pattern in suspicious_patterns):
            return True
        
        # Check query parameters
        for param_value in request.GET.values():
            param_lower = param_value.lower()
            if any(pattern in param_lower for pattern in suspicious_patterns):
                return True
        
        # Check POST data
        if request.POST:
            for param_value in request.POST.values():
                param_lower = param_value.lower()
                if any(pattern in param_lower for pattern in suspicious_patterns):
                    return True
        
        # Check for excessively long requests
        if len(request.path) > 2000:
            return True
        
        # Check for too many query parameters
        if len(request.GET) > 50:
            return True
        
        return False
    
    def _is_valid_json_request(self, request: HttpRequest) -> bool:
        """Validate JSON request format"""
        try:
            import json
            if hasattr(request, '_body'):
                body = request._body
            else:
                body = request.body
            
            if not body:
                return True  # Empty body is valid
            
            # Check if JSON is too large
            if len(body) > 1024 * 1024:  # 1MB limit
                return False
            
            # Try to parse JSON
            json.loads(body)
            return True
            
        except (json.JSONDecodeError, ValueError):
            return False
        except Exception:
            return False


class AuditMiddleware(MiddlewareMixin):
    """
    Audit middleware for logging API access
    
    Logs all API access for audit trail and security monitoring.
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log API access for audit trail"""
        
        # Only log API requests
        if not request.path.startswith('/api/'):
            return response
        
        # Only log for authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response
        
        # Log API access
        audit_manager = get_audit_manager()
        audit_manager.log_api_access(
            merchant=request.user if hasattr(request, 'user') else None,
            endpoint=request.path,
            method=request.method,
            status_code=response.status_code,
            request=request
        )
        
        return response


# Security utility functions
def get_client_ip(request: HttpRequest) -> str:
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def is_suspicious_ip(ip: str) -> bool:
    """Check if IP address is suspicious"""
    # This would typically check against a database of known malicious IPs
    # For now, we'll implement basic checks
    
    # Check for private/local IPs (should not be making requests in production)
    if ip.startswith(('10.', '192.168.', '172.')):
        return False  # Allow private IPs in development
    
    # Check for common attack patterns
    suspicious_patterns = [
        '127.0.0.1',  # Localhost (suspicious if not expected)
        '0.0.0.0',    # Invalid IP
    ]
    
    return ip in suspicious_patterns


def validate_api_key(api_key: str) -> bool:
    """Validate API key format and authenticity"""
    if not api_key:
        return False
    
    # Basic format validation
    if len(api_key) < 20:
        return False
    
    # Check for valid characters (alphanumeric and some special chars)
    import re
    if not re.match(r'^[a-zA-Z0-9\-_]+$', api_key):
        return False
    
    # In a real implementation, you would check against a database
    # of valid API keys here
    
    return True


# Example usage and testing
if __name__ == "__main__":
    print("Security middleware modules loaded successfully")
    print("Available middleware:")
    print("- RateLimitMiddleware: Rate limiting for API abuse prevention")
    print("- SecurityHeadersMiddleware: Security headers for attack protection")
    print("- RequestValidationMiddleware: Request validation for malicious content")
    print("- AuditMiddleware: API access logging for audit trail")
