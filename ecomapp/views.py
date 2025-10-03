"""
Enhanced views for the Merchant Financial Agent

Includes Google Calendar OAuth 2.0 integration and improved
financial management capabilities.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import requests
import json
import os
from .models import Transaction, Category, Event, Forecast, CurrencyRate, MerchantProfile
from django.http import JsonResponse
from django.contrib.auth.models import User

# Google Calendar OAuth imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Security imports
try:
    from security.audit import log_financial_action, log_security_incident
except ImportError:
    # Fallback for when security module is not available
    def log_financial_action(*args, **kwargs):
        pass
    def log_security_incident(*args, **kwargs):
        pass


def home(request):
    """Landing page"""
    return render(request, 'home.html')


def register_view(request):
    """User registration"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        
        if password == password2:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists')
            elif User.objects.filter(email=email).exists():
                messages.error(request, 'Email already registered')
            else:
                user = User.objects.create_user(username=username, email=email, password=password)
                user.save()
                
                # Create merchant profile
                MerchantProfile.objects.create(
                    user=user,
                    business_name=username,
                    business_type='OTHER'
                )
                
                login(request, user)
                messages.success(request, 'Registration successful!')
                
                # Log user registration
                log_security_incident(
                    merchant=user,
                    event_type='USER_REGISTRATION',
                    description=f'New user registered: {username}',
                    severity='LOW'
                )
                
                return redirect('dashboard')
        else:
            messages.error(request, 'Passwords do not match')
    
    return render(request, 'register.html')


def login_view(request):
    """User login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            
            # Log successful login
            log_security_incident(
                merchant=user,
                event_type='USER_LOGIN',
                description=f'User logged in: {username}',
                severity='LOW'
            )
            
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
            
            # Log failed login attempt
            log_security_incident(
                merchant=None,
                event_type='FAILED_LOGIN',
                description=f'Failed login attempt for username: {username}',
                severity='MEDIUM'
            )
    
    return render(request, 'login.html')


def logout_view(request):
    """User logout"""
    username = request.user.username
    logout(request)
    messages.success(request, 'Logged out successfully')
    
    # Log logout
    log_security_incident(
        merchant=None,
        event_type='USER_LOGOUT',
        description=f'User logged out: {username}',
        severity='LOW'
    )
    
    return redirect('home')


@login_required
def dashboard(request):
    """Main dashboard with financial overview"""
    user = request.user
    
    today = timezone.now()
    thirty_days_ago = today - timedelta(days=30)
    
    # Get merchant profile
    merchant_profile, created = MerchantProfile.objects.get_or_create(
        user=user,
        defaults={
            'business_name': user.username,
            'business_type': 'OTHER'
        }
    )
    
    total_income = Transaction.objects.filter(
        merchant=user,
        transaction_type='INCOME',
        status='COMPLETED',
        is_deleted=False
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_expenses = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        status='COMPLETED',
        is_deleted=False
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    net_balance = total_income - total_expenses
    
    monthly_income = Transaction.objects.filter(
        merchant=user,
        transaction_type='INCOME',
        transaction_date__gte=thirty_days_ago,
        status='COMPLETED',
        is_deleted=False
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    monthly_expenses = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        transaction_date__gte=thirty_days_ago,
        status='COMPLETED',
        is_deleted=False
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    recent_transactions = Transaction.objects.filter(
        merchant=user,
        is_deleted=False
    )[:10]
    
    upcoming_events = Event.objects.filter(
        merchant=user,
        status='UPCOMING',
        event_date__gte=today,
        is_deleted=False
    ).order_by('event_date')[:5]
    
    overdue_events = Event.objects.filter(
        merchant=user,
        status='UPCOMING',
        event_date__lt=today,
        is_deleted=False
    ).count()
    
    expense_by_category = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        transaction_date__gte=thirty_days_ago,
        status='COMPLETED',
        category__isnull=False,
        is_deleted=False
    ).values('category__name').annotate(total=Sum('amount')).order_by('-total')[:5]
    
    context = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_balance': net_balance,
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'monthly_net': monthly_income - monthly_expenses,
        'recent_transactions': recent_transactions,
        'upcoming_events': upcoming_events,
        'overdue_events': overdue_events,
        'expense_by_category': expense_by_category,
        'merchant_profile': merchant_profile,
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def transactions_view(request):
    """View and manage transactions"""
    transactions = Transaction.objects.filter(merchant=request.user, is_deleted=False)
    categories = Category.objects.filter(merchant=request.user, is_active=True)
    
    filter_type = request.GET.get('type', '')
    filter_category = request.GET.get('category', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if filter_type:
        transactions = transactions.filter(transaction_type=filter_type)
    if filter_category:
        transactions = transactions.filter(category_id=filter_category)
    if date_from:
        transactions = transactions.filter(transaction_date__gte=date_from)
    if date_to:
        transactions = transactions.filter(transaction_date__lte=date_to)
    
    context = {
        'transactions': transactions,
        'categories': categories,
    }
    return render(request, 'transactions.html', context)


@login_required
def add_transaction(request):
    """Add new transaction"""
    if request.method == 'POST':
        amount = request.POST.get('amount')
        transaction_type = request.POST.get('transaction_type')
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        transaction_date = request.POST.get('transaction_date')
        payment_method = request.POST.get('payment_method', 'CASH')
        reference_id = request.POST.get('reference_id', '')
        currency = request.POST.get('currency', 'USD')
        
        category = None
        if category_id:
            category = Category.objects.get(id=category_id, merchant=request.user)
        
        transaction = Transaction.objects.create(
            merchant=request.user,
            amount=amount,
            transaction_type=transaction_type,
            category=category,
            description=description,
            transaction_date=transaction_date or timezone.now(),
            payment_method=payment_method,
            reference_id=reference_id,
            currency=currency,
            status='COMPLETED',
            created_by=request.user
        )
        
        # Log transaction creation
        log_financial_action(
            merchant=request.user,
            action='CREATE',
            object_id=str(transaction.id),
            amount=float(amount),
            currency=currency
        )
        
        messages.success(request, 'Transaction added successfully!')
        return redirect('transactions')
    
    categories = Category.objects.filter(merchant=request.user, is_active=True)
    return render(request, 'add_transaction.html', {'categories': categories})


@login_required
def events_view(request):
    """View and manage events/deadlines"""
    events = Event.objects.filter(merchant=request.user, is_deleted=False)
    
    filter_status = request.GET.get('status', '')
    filter_type = request.GET.get('type', '')
    
    if filter_status:
        events = events.filter(status=filter_status)
    if filter_type:
        events = events.filter(deadline_type=filter_type)
    
    context = {
        'events': events,
    }
    return render(request, 'events.html', context)


@login_required
def add_event(request):
    """Add new event"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        event_date = request.POST.get('event_date')
        end_date = request.POST.get('end_date')
        deadline_type = request.POST.get('deadline_type')
        priority = request.POST.get('priority', 'MEDIUM')
        amount = request.POST.get('amount', None)
        currency = request.POST.get('currency', 'USD')
        location = request.POST.get('location', '')
        
        event = Event.objects.create(
            merchant=request.user,
            title=title,
            description=description,
            event_date=event_date,
            end_date=end_date,
            deadline_type=deadline_type,
            priority=priority,
            amount=amount if amount else None,
            currency=currency,
            location=location,
            status='UPCOMING',
            created_by=request.user
        )
        
        messages.success(request, 'Event added successfully!')
        return redirect('events')
    
    return render(request, 'add_event.html')


@login_required
def reports_view(request):
    """Financial reports and analytics"""
    user = request.user
    
    period = request.GET.get('period', 'month')
    
    today = timezone.now()
    if period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today - timedelta(days=30)
    elif period == 'quarter':
        start_date = today - timedelta(days=90)
    elif period == 'year':
        start_date = today - timedelta(days=365)
    else:
        start_date = today - timedelta(days=30)
    
    income_transactions = Transaction.objects.filter(
        merchant=user,
        transaction_type='INCOME',
        transaction_date__gte=start_date,
        status='COMPLETED',
        is_deleted=False
    )
    
    expense_transactions = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        transaction_date__gte=start_date,
        status='COMPLETED',
        is_deleted=False
    )
    
    total_income = income_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expense = expense_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_profit = total_income - total_expense
    
    expense_by_category = expense_transactions.values(
        'category__name'
    ).annotate(total=Sum('amount')).order_by('-total')
    
    income_by_category = income_transactions.values(
        'category__name'
    ).annotate(total=Sum('amount')).order_by('-total')
    
    context = {
        'period': period,
        'start_date': start_date,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'expense_by_category': expense_by_category,
        'income_by_category': income_by_category,
        'income_count': income_transactions.count(),
        'expense_count': expense_transactions.count(),
    }
    
    return render(request, 'reports.html', context)


@login_required
def reports_advanced_view(request):
    """Advanced financial reports with comprehensive analytics"""
    return render(request, 'reports_advanced.html')


@login_required
def currency_converter(request):
    """Currency conversion tool"""
    result = None
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', '0'))
        from_currency = request.POST.get('from_currency', 'USD').upper()
        to_currency = request.POST.get('to_currency', 'EUR').upper()
        
        rate = get_exchange_rate(from_currency, to_currency)
        
        if rate:
            converted_amount = amount * rate
            result = {
                'amount': amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'rate': rate,
                'converted_amount': converted_amount
            }
        else:
            messages.error(request, 'Could not fetch exchange rate')
    
    context = {
        'result': result
    }
    return render(request, 'currency_converter.html', context)


def get_exchange_rate(from_currency, to_currency):
    """Fetch exchange rate from external API"""
    try:
        cached_rate = CurrencyRate.objects.filter(
            base_currency=from_currency,
            target_currency=to_currency,
            fetched_at__gte=timezone.now() - timedelta(hours=1)
        ).first()
        
        if cached_rate:
            return cached_rate.rate
        
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            rate = Decimal(str(data['rates'].get(to_currency, 0)))
            
            CurrencyRate.objects.update_or_create(
                base_currency=from_currency,
                target_currency=to_currency,
                defaults={'rate': rate}
            )
            
            return rate
    except Exception as e:
        print(f"Error fetching exchange rate: {e}")
    
    return None


@login_required
def ai_agent_view(request):
    """AI Financial Agent interface"""
    return render(request, 'ai_agent.html')


# Google Calendar OAuth 2.0 Integration

@login_required
def google_calendar_auth(request):
    """Initiate Google Calendar OAuth 2.0 flow"""
    try:
        # Google Calendar API scopes
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        
        # Check if credentials file exists
        credentials_file = os.getenv('GOOGLE_CALENDAR_CREDENTIALS_FILE', 'credentials.json')
        if not os.path.exists(credentials_file):
            messages.error(request, 'Google Calendar credentials not configured')
            return redirect('dashboard')
        
        # Create flow
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file, SCOPES)
        
        # Get authorization URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        # Store state in session
        request.session['google_auth_state'] = flow.state
        
        return redirect(auth_url)
        
    except Exception as e:
        messages.error(request, f'Google Calendar authentication failed: {str(e)}')
        return redirect('dashboard')


@login_required
def google_calendar_callback(request):
    """Handle Google Calendar OAuth 2.0 callback"""
    try:
        # Google Calendar API scopes
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        
        # Get authorization code from callback
        code = request.GET.get('code')
        state = request.GET.get('state')
        
        if not code or not state:
            messages.error(request, 'Google Calendar authentication failed')
            return redirect('dashboard')
        
        # Verify state
        if state != request.session.get('google_auth_state'):
            messages.error(request, 'Invalid state parameter')
            return redirect('dashboard')
        
        # Create flow
        credentials_file = os.getenv('GOOGLE_CALENDAR_CREDENTIALS_FILE', 'credentials.json')
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file, SCOPES, state=state)
        
        # Exchange code for credentials
        flow.fetch_token(code=code)
        
        # Save credentials
        credentials = flow.credentials
        token_file = os.getenv('GOOGLE_CALENDAR_TOKEN_FILE', 'token.json')
        
        with open(token_file, 'w') as token:
            token.write(credentials.to_json())
        
        # Update merchant profile
        merchant_profile, created = MerchantProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'business_name': request.user.username,
                'business_type': 'OTHER'
            }
        )
        
        merchant_profile.google_calendar_enabled = True
        merchant_profile.save()
        
        # Test calendar access
        service = build('calendar', 'v3', credentials=credentials)
        calendar_list = service.calendarList().list().execute()
        
        messages.success(request, 'Google Calendar connected successfully!')
        
        # Log successful OAuth
        log_security_incident(
            merchant=request.user,
            event_type='GOOGLE_CALENDAR_CONNECTED',
            description='Google Calendar OAuth 2.0 connection established',
            severity='LOW'
        )
        
        return redirect('dashboard')
        
    except Exception as e:
        messages.error(request, f'Google Calendar connection failed: {str(e)}')
        
        # Log failed OAuth
        log_security_incident(
            merchant=request.user,
            event_type='GOOGLE_CALENDAR_CONNECTION_FAILED',
            description=f'Google Calendar OAuth failed: {str(e)}',
            severity='MEDIUM'
        )
        
        return redirect('dashboard')


@login_required
def google_calendar_disconnect(request):
    """Disconnect Google Calendar integration"""
    try:
        # Update merchant profile
        merchant_profile, created = MerchantProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'business_name': request.user.username,
                'business_type': 'OTHER'
            }
        )
        
        merchant_profile.google_calendar_enabled = False
        merchant_profile.save()
        
        # Remove token file
        token_file = os.getenv('GOOGLE_CALENDAR_TOKEN_FILE', 'token.json')
        if os.path.exists(token_file):
            os.remove(token_file)
        
        messages.success(request, 'Google Calendar disconnected successfully!')
        
        # Log disconnection
        log_security_incident(
            merchant=request.user,
            event_type='GOOGLE_CALENDAR_DISCONNECTED',
            description='Google Calendar integration disconnected',
            severity='LOW'
        )
        
        return redirect('dashboard')
        
    except Exception as e:
        messages.error(request, f'Google Calendar disconnection failed: {str(e)}')
        return redirect('dashboard')


@login_required
def merchant_profile_view(request):
    """View and edit merchant profile"""
    merchant_profile, created = MerchantProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'business_name': request.user.username,
            'business_type': 'OTHER'
        }
    )
    
    if request.method == 'POST':
        merchant_profile.business_name = request.POST.get('business_name', '')
        merchant_profile.business_type = request.POST.get('business_type', 'OTHER')
        merchant_profile.base_currency = request.POST.get('base_currency', 'USD')
        merchant_profile.phone = request.POST.get('phone', '')
        merchant_profile.address = request.POST.get('address', '')
        merchant_profile.website = request.POST.get('website', '')
        merchant_profile.default_reminder_minutes = int(request.POST.get('default_reminder_minutes', 15))
        merchant_profile.email_notifications = request.POST.get('email_notifications') == 'on'
        merchant_profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('merchant_profile')
    
    context = {
        'merchant_profile': merchant_profile,
    }
    return render(request, 'merchant_profile.html', context)