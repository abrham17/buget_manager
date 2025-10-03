#!/usr/bin/env python
"""
Test runner for the Merchant Financial Agent

Runs comprehensive tests for Function Calling accuracy, MCP chaining integrity,
and overall system functionality.
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

def setup_django():
    """Setup Django for testing"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
    django.setup()

def run_tests():
    """Run all tests"""
    setup_django()
    
    # Get test runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    
    # Run tests
    failures = test_runner.run_tests([
        'tests.test_function_calling',
        'tests.test_mcp_chaining',
        'tests.test_integration',
        'ecomapp.tests',
        'api.tests',
        'reporting.tests',
        'security.tests'
    ])
    
    return failures

def run_specific_test(test_module):
    """Run specific test module"""
    setup_django()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    
    failures = test_runner.run_tests([test_module])
    return failures

def run_performance_tests():
    """Run performance tests"""
    import pytest
    
    return pytest.main([
        'tests/test_integration.py::TestPerformanceIntegration',
        'tests/test_mcp_chaining.py::TestMCPPerformance',
        '-v',
        '--tb=short'
    ])

def run_security_tests():
    """Run security tests"""
    import pytest
    
    return pytest.main([
        'tests/test_integration.py::TestSecurityIntegration',
        'tests/test_mcp_chaining.py::TestMCPSecurity',
        'tests/test_function_calling.py::TestFunctionCallingErrorHandling',
        '-v',
        '--tb=short'
    ])

def run_coverage_report():
    """Run tests with coverage report"""
    import pytest
    
    return pytest.main([
        'tests/',
        '--cov=.',
        '--cov-report=html',
        '--cov-report=term-missing',
        '--cov-fail-under=80',
        '-v'
    ])

if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'performance':
            exit_code = run_performance_tests()
        elif command == 'security':
            exit_code = run_security_tests()
        elif command == 'coverage':
            exit_code = run_coverage_report()
        elif command == 'specific':
            if len(sys.argv) > 2:
                test_module = sys.argv[2]
                exit_code = run_specific_test(test_module)
            else:
                print("Usage: python run_tests.py specific <test_module>")
                exit_code = 1
        else:
            print(f"Unknown command: {command}")
            print("Available commands: performance, security, coverage, specific")
            exit_code = 1
    else:
        # Run all tests
        exit_code = run_tests()
    
    sys.exit(exit_code)


