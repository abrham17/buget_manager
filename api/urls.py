"""
URL configuration for the Merchant Financial Agent API
"""

from django.urls import path
from . import views

urlpatterns = [
    # AI Agent endpoints
    path('chat/', views.AgentChatView.as_view(), name='agent_chat'),
    path('intent/', views.IntentParseView.as_view(), name='parse_intent'),
    path('tools/', views.AvailableToolsView.as_view(), name='available_tools'),
    path('conversation/history/', views.ConversationHistoryView.as_view(), name='conversation_history'),
    path('conversation/clear/', views.ClearConversationView.as_view(), name='clear_conversation'),
    
    # Function calling endpoints
    path('function-call/', views.FunctionCallView.as_view(), name='function_call'),
    path('chained-operations/', views.ChainedOperationsView.as_view(), name='chained_operations'),
    
    # Financial data endpoints
    path('financial/summary/', views.FinancialSummaryView.as_view(), name='financial_summary'),
    path('currency/convert/', views.CurrencyConversionView.as_view(), name='currency_conversion'),
    
    # Calendar endpoints
    path('calendar/events/', views.CalendarEventsView.as_view(), name='calendar_events'),
    
    # System endpoints
    path('health/', views.HealthCheckView.as_view(), name='health_check'),
]
