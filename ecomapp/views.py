from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import requests
from .models import Transaction, Category, Event, Forecast, CurrencyRate
from django.http import JsonResponse
from django.contrib.auth.models import User


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
                login(request, user)
                messages.success(request, 'Registration successful!')
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
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
    
    return render(request, 'login.html')


def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'Logged out successfully')
    return redirect('home')


@login_required
def dashboard(request):
    """Main dashboard with financial overview"""
    user = request.user
    
    today = timezone.now()
    thirty_days_ago = today - timedelta(days=30)
    
    total_income = Transaction.objects.filter(
        merchant=user,
        transaction_type='INCOME',
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_expenses = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    net_balance = total_income - total_expenses
    
    monthly_income = Transaction.objects.filter(
        merchant=user,
        transaction_type='INCOME',
        transaction_date__gte=thirty_days_ago,
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    monthly_expenses = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        transaction_date__gte=thirty_days_ago,
        status='COMPLETED'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    recent_transactions = Transaction.objects.filter(merchant=user)[:10]
    
    upcoming_events = Event.objects.filter(
        merchant=user,
        status='UPCOMING',
        event_date__gte=today
    ).order_by('event_date')[:5]
    
    overdue_events = Event.objects.filter(
        merchant=user,
        status='UPCOMING',
        event_date__lt=today
    ).count()
    
    expense_by_category = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        transaction_date__gte=thirty_days_ago,
        status='COMPLETED',
        category__isnull=False
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
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def transactions_view(request):
    """View and manage transactions"""
    transactions = Transaction.objects.filter(merchant=request.user)
    categories = Category.objects.all()
    
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
        
        category = None
        if category_id:
            category = Category.objects.get(id=category_id)
        
        Transaction.objects.create(
            merchant=request.user,
            amount=amount,
            transaction_type=transaction_type,
            category=category,
            description=description,
            transaction_date=transaction_date or timezone.now(),
            payment_method=payment_method,
            reference_id=reference_id,
            status='COMPLETED'
        )
        
        messages.success(request, 'Transaction added successfully!')
        return redirect('transactions')
    
    categories = Category.objects.all()
    return render(request, 'add_transaction.html', {'categories': categories})


@login_required
def events_view(request):
    """View and manage events/deadlines"""
    events = Event.objects.filter(merchant=request.user)
    
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
        deadline_type = request.POST.get('deadline_type')
        amount = request.POST.get('amount', None)
        
        Event.objects.create(
            merchant=request.user,
            title=title,
            description=description,
            event_date=event_date,
            deadline_type=deadline_type,
            amount=amount if amount else None,
            status='UPCOMING'
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
        status='COMPLETED'
    )
    
    expense_transactions = Transaction.objects.filter(
        merchant=user,
        transaction_type='EXPENSE',
        transaction_date__gte=start_date,
        status='COMPLETED'
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
