from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('transactions/add/', views.add_transaction, name='add_transaction'),
    path('events/', views.events_view, name='events'),
    path('events/add/', views.add_event, name='add_event'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/advanced/', views.reports_advanced_view, name='reports_advanced'),
    path('currency/', views.currency_converter, name='currency_converter'),
    path('ai-agent/', views.ai_agent_view, name='ai_agent'),
    path('profile/', views.merchant_profile_view, name='merchant_profile'),
    path('google-calendar/auth/', views.google_calendar_auth, name='google_calendar_auth'),
    path('google-calendar/callback/', views.google_calendar_callback, name='google_calendar_callback'),
    path('google-calendar/disconnect/', views.google_calendar_disconnect, name='google_calendar_disconnect'),
]
