"""
Pytest configuration and fixtures for the Merchant Financial Agent

Provides common fixtures and configuration for all tests.
"""

import pytest
import os
import tempfile
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta

from ecomapp.models import Transaction, Category, Event, Forecast, MerchantProfile


@pytest.fixture
def test_user():
    """Create a test user"""
    return User.objects.create_user(
        username='testmerchant',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def test_merchant_profile(test_user):
    """Create a test merchant profile"""
    return MerchantProfile.objects.create(
        user=test_user,
        business_name='Test Business',
        business_type='RETAIL',
        base_currency='USD',
        business_address='123 Test St',
        business_phone='+1-555-0123',
        business_email='test@testbusiness.com'
    )


@pytest.fixture
def test_categories(test_user):
    """Create test categories"""
    income_category = Category.objects.create(
        merchant=test_user,
        name='Sales',
        category_type='INCOME',
        description='Product sales and revenue'
    )
    
    expense_category = Category.objects.create(
        merchant=test_user,
        name='Supplies',
        category_type='EXPENSE',
        description='Office supplies and materials'
    )
    
    return {
        'income': income_category,
        'expense': expense_category
    }


@pytest.fixture
def test_transactions(test_user, test_categories):
    """Create test transactions"""
    transactions = []
    
    # Create income transactions
    for i in range(5):
        transaction = Transaction.objects.create(
            merchant=test_user,
            amount=Decimal('100.00') * (i + 1),
            transaction_type='INCOME',
            description=f'Product Sale {i + 1}',
            category=test_categories['income'],
            transaction_date=timezone.now() - timedelta(days=i),
            status='COMPLETED',
            payment_method='CASH',
            currency='USD',
            exchange_rate=Decimal('1.00'),
            base_currency_amount=Decimal('100.00') * (i + 1),
            created_by=test_user
        )
        transactions.append(transaction)
    
    # Create expense transactions
    for i in range(3):
        transaction = Transaction.objects.create(
            merchant=test_user,
            amount=Decimal('50.00') * (i + 1),
            transaction_type='EXPENSE',
            description=f'Supply Purchase {i + 1}',
            category=test_categories['expense'],
            transaction_date=timezone.now() - timedelta(days=i),
            status='COMPLETED',
            payment_method='CREDIT_CARD',
            currency='USD',
            exchange_rate=Decimal('1.00'),
            base_currency_amount=Decimal('50.00') * (i + 1),
            created_by=test_user
        )
        transactions.append(transaction)
    
    return transactions


@pytest.fixture
def test_events(test_user):
    """Create test events"""
    events = []
    
    for i in range(3):
        event = Event.objects.create(
            merchant=test_user,
            title=f'Meeting {i + 1}',
            description=f'Team meeting {i + 1}',
            event_date=timezone.now() + timedelta(days=i + 1),
            deadline_type='MEETING',
            priority='MEDIUM',
            status='UPCOMING',
            created_by=test_user
        )
        events.append(event)
    
    return events


@pytest.fixture
def test_forecasts(test_user):
    """Create test forecasts"""
    forecasts = []
    
    for i in range(2):
        forecast = Forecast.objects.create(
            merchant=test_user,
            forecast_type='REVENUE',
            forecast_amount=Decimal('10000.00') * (i + 1),
            period_start=timezone.now().date() + timedelta(days=30 * i),
            period_end=timezone.now().date() + timedelta(days=30 * (i + 1)),
            currency='USD',
            confidence_level=0.8 - (i * 0.1),
            notes=f'Forecast {i + 1}',
            created_by=test_user
        )
        forecasts.append(forecast)
    
    return forecasts


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response"""
    return {
        'choices': [{
            'message': {
                'content': 'Mocked AI response',
                'role': 'assistant'
            }
        }],
        'usage': {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'total_tokens': 150
        }
    }


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response"""
    return {
        'content': [{
            'text': 'Mocked AI response',
            'type': 'text'
        }],
        'usage': {
            'input_tokens': 100,
            'output_tokens': 50
        }
    }


@pytest.fixture
def mock_currency_api_response():
    """Mock currency API response"""
    return {
        'rates': {
            'USD': 1.0,
            'EUR': 0.85,
            'GBP': 0.73,
            'JPY': 110.0
        },
        'base': 'USD',
        'date': '2024-01-15'
    }


@pytest.fixture
def mock_google_calendar_response():
    """Mock Google Calendar API response"""
    return {
        'id': 'event_123',
        'htmlLink': 'https://calendar.google.com/event/123',
        'summary': 'Test Event',
        'start': {
            'dateTime': '2024-01-16T10:00:00Z'
        },
        'end': {
            'dateTime': '2024-01-16T11:00:00Z'
        }
    }


@pytest.fixture
def sample_report_data():
    """Sample report data for testing"""
    return {
        'report_metadata': {
            'merchant_id': 1,
            'merchant_name': 'testmerchant',
            'period_start': '2024-01-01',
            'period_end': '2024-01-31',
            'base_currency': 'USD',
            'generated_at': '2024-01-15T10:00:00Z',
            'report_type': 'comprehensive'
        },
        'financial_summary': {
            'total_income': 1500.0,
            'total_expenses': 300.0,
            'total_transfers': 0.0,
            'net_profit': 1200.0,
            'total_transactions': 8,
            'average_transaction_size': 225.0,
            'profit_margin': 0.8,
            'currency': 'USD'
        },
        'income_analysis': {
            'monthly_breakdown': [],
            'category_breakdown': [
                {'category__name': 'Sales', 'total': 1500.0, 'count': 5}
            ],
            'payment_method_breakdown': [
                {'payment_method': 'CASH', 'total': 1500.0, 'count': 5}
            ],
            'top_sources': [
                {'description': 'Product Sale 5', 'total': 500.0, 'count': 1}
            ],
            'growth_rate': 0.0
        },
        'expense_analysis': {
            'monthly_breakdown': [],
            'category_breakdown': [
                {'category__name': 'Supplies', 'total': 300.0, 'count': 3}
            ],
            'payment_method_breakdown': [
                {'payment_method': 'CREDIT_CARD', 'total': 300.0, 'count': 3}
            ],
            'largest_expenses': [
                {
                    'description': 'Supply Purchase 3',
                    'amount': 150.0,
                    'date': '2024-01-15',
                    'category': 'Supplies'
                }
            ],
            'growth_rate': 0.0
        }
    }


# Performance test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.security = pytest.mark.security
pytest.mark.slow = pytest.mark.slow


# Test database configuration
@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Configure test database"""
    with django_db_blocker.unblock():
        # Additional database setup if needed
        pass


# Environment variables for testing
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
    os.environ.setdefault('OPENAI_API_KEY', 'test-key')
    os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
    os.environ.setdefault('EXCHANGE_RATE_API_KEY', 'test-key')
    os.environ.setdefault('GOOGLE_CLIENT_SECRETS_FILE', '/tmp/test-secrets.json')
    
    # Create temporary secrets file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"installed":{"client_id":"test","client_secret":"test"}}')
        os.environ['GOOGLE_CLIENT_SECRETS_FILE'] = f.name
    
    yield
    
    # Cleanup
    if os.path.exists(os.environ['GOOGLE_CLIENT_SECRETS_FILE']):
        os.unlink(os.environ['GOOGLE_CLIENT_SECRETS_FILE'])


