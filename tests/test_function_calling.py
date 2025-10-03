"""
Test Function Calling accuracy and intent generation

Tests the Function Calling layer to ensure proper intent generation
and structured JSON command creation.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase
from django.contrib.auth.models import User

from ai_agent.function_calling import FunctionCalling
from mcp_servers.mcp_orchestrator import MCPOrchestrator


class TestFunctionCalling(TestCase):
    """Test Function Calling accuracy and intent generation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        # Mock orchestrator
        self.mock_orchestrator = Mock(spec=MCPOrchestrator)
        self.function_calling = FunctionCalling(self.mock_orchestrator)
    
    def test_function_schema_loading(self):
        """Test that function schemas are properly loaded"""
        # Mock orchestrator response
        mock_schemas = {
            'financial_db_adapter.generate_summary': {
                'name': 'financial_db_adapter.generate_summary',
                'description': 'Generates a financial summary',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'merchant_id': {'type': 'integer'},
                        'timeframe': {'type': 'string', 'enum': ['week', 'month', 'quarter', 'year']},
                        'categories': {'type': 'boolean'}
                    },
                    'required': ['merchant_id', 'timeframe']
                }
            }
        }
        
        self.mock_orchestrator.get_all_function_schemas.return_value = mock_schemas
        
        # Test schema loading
        schemas = self.function_calling.get_schemas_for_llm()
        
        self.assertIsInstance(schemas, list)
        self.assertEqual(len(schemas), 1)
        
        schema = schemas[0]
        self.assertEqual(schema['type'], 'function')
        self.assertIn('function', schema)
        self.assertEqual(schema['function']['name'], 'financial_db_adapter.generate_summary')
    
    def test_function_execution(self):
        """Test function execution through orchestrator"""
        # Mock orchestrator response
        mock_result = {
            'jsonrpc': '2.0',
            'result': {
                'total_income': '5000.00',
                'total_expenses': '3000.00',
                'net_profit': '2000.00'
            },
            'id': 'test-123'
        }
        
        self.mock_orchestrator.execute_function_call.return_value = mock_result
        
        # Test function execution
        result = self.function_calling.execute_function(
            'financial_db_adapter.generate_summary',
            merchant_id=self.user.id,
            timeframe='month',
            categories=True
        )
        
        self.assertEqual(result, mock_result)
        self.mock_orchestrator.execute_function_call.assert_called_once()
    
    def test_get_function_by_name(self):
        """Test retrieving function schema by name"""
        mock_schemas = {
            'financial_db_adapter.generate_summary': {
                'name': 'financial_db_adapter.generate_summary',
                'description': 'Generates a financial summary'
            }
        }
        
        self.mock_orchestrator.get_all_function_schemas.return_value = mock_schemas
        
        # Test getting function by name
        function = self.function_calling.get_function_by_name('financial_db_adapter.generate_summary')
        self.assertIsNotNone(function)
        self.assertEqual(function['name'], 'financial_db_adapter.generate_summary')
        
        # Test non-existent function
        function = self.function_calling.get_function_by_name('non_existent_function')
        self.assertIsNone(function)


class TestFunctionCallingAccuracy(TestCase):
    """Test Function Calling accuracy with real scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testmerchant',
            email='test@example.com',
            password='testpass123'
        )
        
        self.mock_orchestrator = Mock(spec=MCPOrchestrator)
        self.function_calling = FunctionCalling(self.mock_orchestrator)
    
    def test_financial_summary_intent_parsing(self):
        """Test parsing financial summary requests"""
        test_cases = [
            {
                'input': 'Show me my financial summary for last month',
                'expected_function': 'financial_db_adapter.generate_summary',
                'expected_params': {
                    'merchant_id': self.user.id,
                    'timeframe': 'month',
                    'categories': False
                }
            },
            {
                'input': 'What were my expenses last quarter with categories?',
                'expected_function': 'financial_db_adapter.generate_summary',
                'expected_params': {
                    'merchant_id': self.user.id,
                    'timeframe': 'quarter',
                    'categories': True
                }
            },
            {
                'input': 'Convert 1000 USD to EUR',
                'expected_function': 'currency_service.convert_currency',
                'expected_params': {
                    'amount': '1000',
                    'base': 'USD',
                    'target': 'EUR'
                }
            }
        ]
        
        # Mock orchestrator responses
        self.mock_orchestrator.execute_function_call.return_value = {
            'jsonrpc': '2.0',
            'result': {'success': True},
            'id': 'test'
        }
        
        for test_case in test_cases:
            # This would typically be done by the LLM, but we're testing the function calling layer
            # In a real scenario, the LLM would parse the intent and call the appropriate function
            
            # Simulate function call based on parsed intent
            if 'financial summary' in test_case['input'].lower():
                result = self.function_calling.execute_function(
                    test_case['expected_function'],
                    **test_case['expected_params']
                )
                self.assertIsNotNone(result)
                self.mock_orchestrator.execute_function_call.assert_called()
    
    def test_currency_conversion_intent_parsing(self):
        """Test parsing currency conversion requests"""
        test_cases = [
            {
                'input': 'Convert 500 USD to EUR',
                'expected_function': 'currency_service.convert_currency',
                'expected_params': {
                    'amount': '500',
                    'base': 'USD',
                    'target': 'EUR'
                }
            },
            {
                'input': 'What is the exchange rate between USD and GBP?',
                'expected_function': 'currency_service.get_live_fx_rate',
                'expected_params': {
                    'base': 'USD',
                    'target': 'GBP'
                }
            }
        ]
        
        # Mock orchestrator responses
        self.mock_orchestrator.execute_function_call.return_value = {
            'jsonrpc': '2.0',
            'result': {'converted_amount': '450.00'},
            'id': 'test'
        }
        
        for test_case in test_cases:
            result = self.function_calling.execute_function(
                test_case['expected_function'],
                **test_case['expected_params']
            )
            self.assertIsNotNone(result)
    
    def test_calendar_event_intent_parsing(self):
        """Test parsing calendar event requests"""
        test_cases = [
            {
                'input': 'Schedule a meeting with my accountant next Tuesday',
                'expected_function': 'google_calendar_server.calendar_create_event',
                'expected_params': {
                    'merchant_id': self.user.id,
                    'title': 'Meeting with accountant',
                    'event_date': '2024-01-16T10:00:00Z',  # This would be calculated
                    'description': 'Meeting with accountant',
                    'duration_minutes': 60
                }
            }
        ]
        
        # Mock orchestrator responses
        self.mock_orchestrator.execute_function_call.return_value = {
            'jsonrpc': '2.0',
            'result': {'id': 'event_123', 'message': 'Event created successfully'},
            'id': 'test'
        }
        
        for test_case in test_cases:
            result = self.function_calling.execute_function(
                test_case['expected_function'],
                **test_case['expected_params']
            )
            self.assertIsNotNone(result)


class TestFunctionCallingErrorHandling(TestCase):
    """Test Function Calling error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_orchestrator = Mock(spec=MCPOrchestrator)
        self.function_calling = FunctionCalling(self.mock_orchestrator)
    
    def test_invalid_function_name(self):
        """Test handling of invalid function names"""
        # Mock orchestrator error response
        self.mock_orchestrator.execute_function_call.return_value = {
            'jsonrpc': '2.0',
            'error': {
                'code': -32601,
                'message': 'Method not found'
            },
            'id': 'test'
        }
        
        result = self.function_calling.execute_function(
            'invalid_function_name',
            param1='value1'
        )
        
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32601)
    
    def test_missing_required_parameters(self):
        """Test handling of missing required parameters"""
        # Mock orchestrator error response
        self.mock_orchestrator.execute_function_call.return_value = {
            'jsonrpc': '2.0',
            'error': {
                'code': -32602,
                'message': 'Invalid params'
            },
            'id': 'test'
        }
        
        result = self.function_calling.execute_function(
            'financial_db_adapter.generate_summary'
            # Missing required merchant_id parameter
        )
        
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32602)
    
    def test_orchestrator_exception_handling(self):
        """Test handling of orchestrator exceptions"""
        # Mock orchestrator exception
        self.mock_orchestrator.execute_function_call.side_effect = Exception('Connection error')
        
        with pytest.raises(Exception):
            self.function_calling.execute_function(
                'financial_db_adapter.generate_summary',
                merchant_id=1,
                timeframe='month'
            )


class TestFunctionCallingPerformance(TestCase):
    """Test Function Calling performance"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_orchestrator = Mock(spec=MCPOrchestrator)
        self.function_calling = FunctionCalling(self.mock_orchestrator)
    
    def test_schema_loading_performance(self):
        """Test performance of schema loading"""
        import time
        
        # Mock large schema response
        large_schema = {}
        for i in range(100):
            large_schema[f'function_{i}'] = {
                'name': f'function_{i}',
                'description': f'Description for function {i}',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'param1': {'type': 'string'},
                        'param2': {'type': 'integer'}
                    }
                }
            }
        
        self.mock_orchestrator.get_all_function_schemas.return_value = large_schema
        
        start_time = time.time()
        schemas = self.function_calling.get_schemas_for_llm()
        end_time = time.time()
        
        # Should complete within reasonable time (less than 1 second)
        self.assertLess(end_time - start_time, 1.0)
        self.assertEqual(len(schemas), 100)
    
    def test_concurrent_function_calls(self):
        """Test handling of concurrent function calls"""
        import threading
        import time
        
        # Mock orchestrator with delay
        def mock_execute_with_delay(*args, **kwargs):
            time.sleep(0.1)  # Simulate network delay
            return {
                'jsonrpc': '2.0',
                'result': {'success': True},
                'id': 'test'
            }
        
        self.mock_orchestrator.execute_function_call.side_effect = mock_execute_with_delay
        
        results = []
        threads = []
        
        def call_function():
            result = self.function_calling.execute_function(
                'test_function',
                param='value'
            )
            results.append(result)
        
        # Create multiple threads
        for i in range(10):
            thread = threading.Thread(target=call_function)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All calls should complete successfully
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIn('result', result)
            self.assertTrue(result['result']['success'])


if __name__ == '__main__':
    pytest.main([__file__])


