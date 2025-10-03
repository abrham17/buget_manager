"""
Audit Trail Module for the Merchant Financial Agent

Implements comprehensive audit logging for all financial operations,
ensuring compliance and traceability for regulatory requirements.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.http import HttpRequest
from django.conf import settings

try:
    from ecomapp.models import AuditLog
except ImportError:
    AuditLog = None

logger = logging.getLogger(__name__)


class AuditTrailManager:
    """
    Manages audit trail logging for all financial operations
    
    Provides comprehensive logging of user actions, data changes,
    and system events for compliance and security monitoring.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('audit_trail')
    
    def log_action(self, 
                   merchant: User,
                   action: str,
                   model_name: str,
                   object_id: str,
                   old_values: Optional[Dict[str, Any]] = None,
                   new_values: Optional[Dict[str, Any]] = None,
                   request: Optional[HttpRequest] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> AuditLog:
        """
        Log an audit trail entry
        
        Args:
            merchant: User performing the action
            action: Type of action (CREATE, UPDATE, DELETE, VIEW, etc.)
            model_name: Name of the model being acted upon
            object_id: ID of the object being acted upon
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            request: HTTP request object for context
            metadata: Additional metadata
            
        Returns:
            Created AuditLog instance
        """
        try:
            if AuditLog is None:
                # Fallback when AuditLog model is not available
                logger.warning("AuditLog model not available, skipping audit log creation")
                return None
                
            # Sanitize sensitive data
            old_values = self._sanitize_values(old_values)
            new_values = self._sanitize_values(new_values)
            
            audit_log = AuditLog.objects.create(
                merchant=merchant,
                action=action,
                model_name=model_name,
                object_id=object_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=self._get_client_ip(request),
                user_agent=self._get_user_agent(request)
            )
            
            # Log to file for additional monitoring
            self._log_to_file(audit_log, metadata)
            
            logger.info(f"Audit log created: {action} {model_name} {object_id} by {merchant.username}")
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            raise AuditError(f"Audit logging failed: {str(e)}")
    
    def log_financial_transaction(self,
                                merchant: User,
                                transaction_id: str,
                                action: str,
                                amount: Optional[float] = None,
                                currency: Optional[str] = None,
                                request: Optional[HttpRequest] = None) -> AuditLog:
        """
        Log financial transaction audit entry
        
        Args:
            merchant: User performing the action
            transaction_id: Transaction ID
            action: Action type
            amount: Transaction amount
            currency: Transaction currency
            request: HTTP request for context
            
        Returns:
            Created AuditLog instance
        """
        metadata = {
            'transaction_type': 'FINANCIAL_TRANSACTION',
            'amount': amount,
            'currency': currency,
            'timestamp': timezone.now().isoformat()
        }
        
        return self.log_action(
            merchant=merchant,
            action=action,
            model_name='Transaction',
            object_id=transaction_id,
            request=request,
            metadata=metadata
        )
    
    def log_api_access(self,
                      merchant: User,
                      endpoint: str,
                      method: str,
                      status_code: int,
                      request: Optional[HttpRequest] = None,
                      response_data: Optional[Dict[str, Any]] = None) -> AuditLog:
        """
        Log API access audit entry
        
        Args:
            merchant: User making the API call
            endpoint: API endpoint accessed
            method: HTTP method used
            status_code: Response status code
            request: HTTP request for context
            response_data: API response data (sanitized)
            
        Returns:
            Created AuditLog instance
        """
        metadata = {
            'api_access': True,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'response_size': len(str(response_data)) if response_data else 0,
            'timestamp': timezone.now().isoformat()
        }
        
        # Sanitize response data
        sanitized_response = self._sanitize_values(response_data)
        
        return self.log_action(
            merchant=merchant,
            action='API_ACCESS',
            model_name='API',
            object_id=f"{method}:{endpoint}",
            new_values=sanitized_response,
            request=request,
            metadata=metadata
        )
    
    def log_ai_agent_interaction(self,
                               merchant: User,
                               user_input: str,
                               agent_response: str,
                               tool_calls: Optional[List[Dict[str, Any]]] = None,
                               request: Optional[HttpRequest] = None) -> AuditLog:
        """
        Log AI agent interaction audit entry
        
        Args:
            merchant: User interacting with the agent
            user_input: User's input message
            agent_response: Agent's response
            tool_calls: Tool calls made by the agent
            request: HTTP request for context
            
        Returns:
            Created AuditLog instance
        """
        metadata = {
            'ai_interaction': True,
            'input_length': len(user_input),
            'response_length': len(agent_response),
            'tool_calls_count': len(tool_calls) if tool_calls else 0,
            'timestamp': timezone.now().isoformat()
        }
        
        new_values = {
            'user_input': user_input[:500],  # Truncate for storage
            'agent_response': agent_response[:1000],  # Truncate for storage
            'tool_calls': tool_calls
        }
        
        return self.log_action(
            merchant=merchant,
            action='AI_INTERACTION',
            model_name='AI_AGENT',
            object_id=str(merchant.id),
            new_values=new_values,
            request=request,
            metadata=metadata
        )
    
    def log_security_event(self,
                          merchant: Optional[User],
                          event_type: str,
                          description: str,
                          severity: str = 'MEDIUM',
                          request: Optional[HttpRequest] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> AuditLog:
        """
        Log security-related event
        
        Args:
            merchant: User involved (if applicable)
            event_type: Type of security event
            description: Description of the event
            severity: Event severity (LOW, MEDIUM, HIGH, CRITICAL)
            request: HTTP request for context
            metadata: Additional metadata
            
        Returns:
            Created AuditLog instance
        """
        security_metadata = {
            'security_event': True,
            'event_type': event_type,
            'severity': severity,
            'description': description,
            'timestamp': timezone.now().isoformat()
        }
        
        if metadata:
            security_metadata.update(metadata)
        
        return self.log_action(
            merchant=merchant or User.objects.get(id=1),  # System user if no merchant
            action='SECURITY_EVENT',
            model_name='SECURITY',
            object_id=event_type,
            new_values={'description': description, 'severity': severity},
            request=request,
            metadata=security_metadata
        )
    
    def _sanitize_values(self, values: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Sanitize sensitive values for audit logging
        
        Args:
            values: Values to sanitize
            
        Returns:
            Sanitized values
        """
        if not values:
            return values
        
        # Fields to mask or remove
        sensitive_fields = [
            'password', 'secret', 'key', 'token', 'api_key',
            'credit_card', 'ssn', 'social_security', 'bank_account'
        ]
        
        sanitized = {}
        for key, value in values.items():
            key_lower = key.lower()
            
            # Check if field contains sensitive data
            is_sensitive = any(sensitive in key_lower for sensitive in sensitive_fields)
            
            if is_sensitive:
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_values(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_values(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _get_client_ip(self, request: Optional[HttpRequest]) -> Optional[str]:
        """Extract client IP address from request"""
        if not request:
            return None
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip
    
    def _get_user_agent(self, request: Optional[HttpRequest]) -> str:
        """Extract user agent from request"""
        if not request:
            return ''
        
        return request.META.get('HTTP_USER_AGENT', '')[:500]  # Truncate for storage
    
    def _log_to_file(self, audit_log: AuditLog, metadata: Optional[Dict[str, Any]] = None):
        """Log audit entry to file for additional monitoring"""
        try:
            log_entry = {
                'timestamp': audit_log.timestamp.isoformat(),
                'merchant_id': audit_log.merchant.id,
                'merchant_username': audit_log.merchant.username,
                'action': audit_log.action,
                'model_name': audit_log.model_name,
                'object_id': audit_log.object_id,
                'ip_address': audit_log.ip_address,
                'user_agent': audit_log.user_agent,
                'metadata': metadata or {}
            }
            
            self.logger.info(f"AUDIT: {json.dumps(log_entry)}")
            
        except Exception as e:
            logger.error(f"Failed to log audit entry to file: {e}")
    
    def get_audit_trail(self,
                       merchant: User,
                       model_name: Optional[str] = None,
                       action: Optional[str] = None,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None,
                       limit: int = 100) -> List[AuditLog]:
        """
        Retrieve audit trail entries
        
        Args:
            merchant: Merchant to get audit trail for
            model_name: Filter by model name
            action: Filter by action type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of entries to return
            
        Returns:
            List of AuditLog entries
        """
        if AuditLog is None:
            logger.warning("AuditLog model not available, returning empty list")
            return []
            
        queryset = AuditLog.objects.filter(merchant=merchant)
        
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        
        if action:
            queryset = queryset.filter(action=action)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset.order_by('-timestamp')[:limit]


class AuditError(Exception):
    """Custom exception for audit-related errors"""
    pass


# Global audit trail manager instance
def get_audit_manager() -> AuditTrailManager:
    """Get or create global audit trail manager instance"""
    if not hasattr(settings, '_audit_manager'):
        settings._audit_manager = AuditTrailManager()
    return settings._audit_manager


# Convenience functions
def log_financial_action(merchant: User, action: str, object_id: str, **kwargs) -> AuditLog:
    """Convenience function to log financial actions"""
    manager = get_audit_manager()
    return manager.log_financial_transaction(merchant, object_id, action, **kwargs)


def log_api_call(merchant: User, endpoint: str, method: str, status_code: int, **kwargs) -> AuditLog:
    """Convenience function to log API calls"""
    manager = get_audit_manager()
    return manager.log_api_access(merchant, endpoint, method, status_code, **kwargs)


def log_ai_interaction(merchant: User, user_input: str, agent_response: str, **kwargs) -> AuditLog:
    """Convenience function to log AI interactions"""
    manager = get_audit_manager()
    return manager.log_ai_agent_interaction(merchant, user_input, agent_response, **kwargs)


def log_security_incident(merchant: Optional[User], event_type: str, description: str, **kwargs) -> AuditLog:
    """Convenience function to log security incidents"""
    manager = get_audit_manager()
    return manager.log_security_event(merchant, event_type, description, **kwargs)


# Example usage
if __name__ == "__main__":
    # Example of using audit trail
    manager = AuditTrailManager()
    
    # This would typically be called from views or models
    print("Audit trail manager initialized successfully")
    print("Available methods:")
    print("- log_action()")
    print("- log_financial_transaction()")
    print("- log_api_access()")
    print("- log_ai_agent_interaction()")
    print("- log_security_event()")
    print("- get_audit_trail()")
