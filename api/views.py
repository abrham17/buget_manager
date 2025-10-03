"""
REST API Views for the Merchant Financial Agent

Provides REST API endpoints for MCP server communication, AI agent interaction,
and external service integration.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.models import User
from django.db import transaction

try:
    from ai_agent.llm_integration import create_agent
    from mcp_servers.mcp_orchestrator import mcp_orchestrator
    from ai_agent.function_calling import function_calling_engine
    from ecomapp.models import AuditLog
    from security.audit import log_financial_action, log_api_call, log_ai_interaction, log_security_incident
except ImportError:
    # Fallback for when modules are not available
    def create_agent():
        return None
    mcp_orchestrator = None
    function_calling_engine = None
    AuditLog = None
    def log_financial_action(*args, **kwargs):
        pass
    def log_api_call(*args, **kwargs):
        pass
    def log_ai_interaction(*args, **kwargs):
        pass
    def log_security_incident(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


def create_audit_log(merchant_id: int, action: str, model_name: str, 
                    object_id: str, old_values: Optional[Dict] = None, 
                    new_values: Optional[Dict] = None, request: Optional[HttpRequest] = None):
    """Create audit log entry"""
    try:
        merchant = User.objects.get(id=merchant_id)
        
        audit_log = AuditLog.objects.create(
            merchant=merchant,
            action=action,
            model_name=model_name,
            object_id=object_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=request.META.get('REMOTE_ADDR') if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else ''
        )
        return audit_log
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        return None


class AgentChatView(View):
    """Chat endpoint for AI agent interaction"""
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    async def post(self, request):
        """Process chat message with AI agent"""
        try:
            data = json.loads(request.body)
            user_input = data.get('message', '')
            
            if not user_input:
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Create agent instance
            agent = create_agent()
            
            # Process message
            response = await agent.process_message(
                merchant_id=request.user.id,
                user_input=user_input
            )
            
            # Log AI interaction
            log_ai_interaction(
                merchant=request.user,
                user_input=user_input,
                agent_response=response['content'],
                tool_calls=response.get('tool_results', []),
                request=request
            )
            
            return JsonResponse({
                'response': response['content'],
                'timestamp': response['timestamp'],
                'tool_results': response.get('tool_results', [])
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class FunctionCallView(View):
    """Direct function call endpoint"""
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    async def post(self, request):
        """Execute a function call directly"""
        try:
            data = json.loads(request.body)
            tool_name = data.get('tool_name')
            arguments = data.get('arguments', {})
            
            if not tool_name:
                return JsonResponse({'error': 'tool_name is required'}, status=400)
            
            # Add merchant_id to arguments
            arguments['merchant_id'] = request.user.id
            
            # Validate tool call
            if not function_calling_engine.validate_tool_call(tool_name, arguments):
                return JsonResponse({'error': 'Invalid tool call parameters'}, status=400)
            
            # Execute tool through MCP orchestrator
            result = await mcp_orchestrator.execute_tool(tool_name, arguments, request.user.id)
            
            # Create audit log
            create_audit_log(
                merchant_id=request.user.id,
                action='FUNCTION_CALL',
                model_name='MCP_TOOL',
                object_id=tool_name,
                new_values={'tool_name': tool_name, 'arguments': arguments, 'result': result},
                request=request
            )
            
            return JsonResponse({
                'result': result,
                'timestamp': datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Function call error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class IntentParseView(View):
    """Intent parsing endpoint"""
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    async def post(self, request):
        """Parse user intent from natural language"""
        try:
            data = json.loads(request.body)
            user_input = data.get('message', '')
            
            if not user_input:
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Parse intent
            intent_result = function_calling_engine.parse_intent(user_input, request.user.id)
            
            return JsonResponse({
                'intent': intent_result,
                'timestamp': datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Intent parsing error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class AvailableToolsView(View):
    """Get available tools endpoint"""
    
    @method_decorator(login_required)
    async def get(self, request):
        """Get list of available tools"""
        try:
            tools = function_calling_engine.get_available_tools()
            
            return JsonResponse({
                'tools': tools,
                'count': len(tools),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Get tools error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class ChainedOperationsView(View):
    """Execute chained operations endpoint"""
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    async def post(self, request):
        """Execute a chain of operations"""
        try:
            data = json.loads(request.body)
            operations = data.get('operations', [])
            
            if not operations:
                return JsonResponse({'error': 'Operations list is required'}, status=400)
            
            # Execute chained operations
            results = await mcp_orchestrator.execute_chained_operations(
                operations, merchant_id=request.user.id
            )
            
            # Create audit log
            create_audit_log(
                merchant_id=request.user.id,
                action='CHAINED_OPERATIONS',
                model_name='MCP_ORCHESTRATOR',
                object_id=str(request.user.id),
                new_values={'operations': operations, 'results': results},
                request=request
            )
            
            return JsonResponse({
                'results': results,
                'timestamp': datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Chained operations error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class HealthCheckView(View):
    """Health check endpoint"""
    
    async def get(self, request):
        """Perform system health check"""
        try:
            # Check MCP orchestrator health
            orchestrator_health = await mcp_orchestrator.health_check()
            
            # Check function calling engine
            function_calling_health = {
                'tools_available': len(function_calling_engine.get_available_tools()),
                'status': 'healthy'
            }
            
            # Overall health status
            overall_status = 'healthy'
            if orchestrator_health.get('overall_status') != 'healthy':
                overall_status = 'degraded'
            
            return JsonResponse({
                'status': overall_status,
                'components': {
                    'mcp_orchestrator': orchestrator_health,
                    'function_calling': function_calling_health
                },
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return JsonResponse({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }, status=500)


class ConversationHistoryView(View):
    """Get conversation history endpoint"""
    
    @method_decorator(login_required)
    async def get(self, request):
        """Get conversation history for the user"""
        try:
            # Create agent instance to access conversation context
            agent = create_agent()
            
            # Get conversation history
            history = await agent.get_conversation_history(request.user.id)
            
            return JsonResponse({
                'conversation_history': history,
                'merchant_id': request.user.id,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Get conversation history error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class ClearConversationView(View):
    """Clear conversation history endpoint"""
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    async def post(self, request):
        """Clear conversation history for the user"""
        try:
            # Create agent instance
            agent = create_agent()
            
            # Clear conversation
            await agent.clear_conversation(request.user.id)
            
            # Create audit log
            create_audit_log(
                merchant_id=request.user.id,
                action='CLEAR_CONVERSATION',
                model_name='AI_AGENT',
                object_id=str(request.user.id),
                request=request
            )
            
            return JsonResponse({
                'message': 'Conversation history cleared',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Clear conversation error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# Financial Data API Views

class FinancialSummaryView(View):
    """Financial summary endpoint"""
    
    @method_decorator(login_required)
    async def get(self, request):
        """Get financial summary for the user"""
        try:
            timeframe = request.GET.get('timeframe', 'month')
            include_categories = request.GET.get('include_categories', 'true').lower() == 'true'
            
            # Execute through MCP orchestrator
            result = await mcp_orchestrator.execute_tool(
                'generate_summary',
                {
                    'merchant_id': request.user.id,
                    'timeframe': timeframe,
                    'include_categories': include_categories
                },
                request.user.id
            )
            
            return JsonResponse({
                'summary': result,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Financial summary error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class CurrencyConversionView(View):
    """Currency conversion endpoint"""
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    async def post(self, request):
        """Convert currency"""
        try:
            data = json.loads(request.body)
            amount = data.get('amount')
            from_currency = data.get('from_currency')
            to_currency = data.get('to_currency')
            
            if not all([amount, from_currency, to_currency]):
                return JsonResponse({
                    'error': 'amount, from_currency, and to_currency are required'
                }, status=400)
            
            # Execute conversion
            result = await mcp_orchestrator.execute_tool(
                'convert_currency',
                {
                    'amount': float(amount),
                    'from_currency': from_currency.upper(),
                    'to_currency': to_currency.upper()
                },
                request.user.id
            )
            
            return JsonResponse({
                'conversion': result,
                'timestamp': datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Currency conversion error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class CalendarEventsView(View):
    """Calendar events endpoint"""
    
    @method_decorator(login_required)
    async def get(self, request):
        """Get calendar events"""
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            query = request.GET.get('query', '')
            
            # Execute through MCP orchestrator
            result = await mcp_orchestrator.execute_tool(
                'calendar_find_events',
                {
                    'merchant_id': request.user.id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'query': query
                },
                request.user.id
            )
            
            return JsonResponse({
                'events': result,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Calendar events error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @method_decorator(csrf_exempt)
    @method_decorator(login_required)
    async def post(self, request):
        """Create calendar event"""
        try:
            data = json.loads(request.body)
            
            required_fields = ['title', 'start_datetime', 'end_datetime']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({'error': f'{field} is required'}, status=400)
            
            # Execute through MCP orchestrator
            result = await mcp_orchestrator.execute_tool(
                'calendar_create_event',
                {
                    'merchant_id': request.user.id,
                    **data
                },
                request.user.id
            )
            
            # Create audit log
            create_audit_log(
                merchant_id=request.user.id,
                action='CREATE_EVENT',
                model_name='CALENDAR',
                object_id=result.get('event_created', {}).get('id', 'unknown'),
                new_values=data,
                request=request
            )
            
            return JsonResponse({
                'event': result,
                'timestamp': datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Create calendar event error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# Utility functions for async support in Django views
import asyncio
from functools import wraps

def async_view(func):
    """Decorator to make Django views async"""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        return asyncio.run(func(request, *args, **kwargs))
    return wrapper

# Apply async decorator to async methods
AgentChatView.post = async_view(AgentChatView.post)
FunctionCallView.post = async_view(FunctionCallView.post)
ChainedOperationsView.post = async_view(ChainedOperationsView.post)
HealthCheckView.get = async_view(HealthCheckView.get)
ConversationHistoryView.get = async_view(ConversationHistoryView.get)
ClearConversationView.post = async_view(ClearConversationView.post)
FinancialSummaryView.get = async_view(FinancialSummaryView.get)
CurrencyConversionView.post = async_view(CurrencyConversionView.post)
CalendarEventsView.get = async_view(CalendarEventsView.get)
CalendarEventsView.post = async_view(CalendarEventsView.post)
