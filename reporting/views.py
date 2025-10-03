"""
Reporting Views for the Merchant Financial Agent

Handles report generation requests and provides various reporting endpoints.
"""

import json
import logging
from datetime import datetime, timedelta, date
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Q

from .engine import FinancialReportingEngine
try:
    from security.audit import log_financial_action
except ImportError:
    def log_financial_action(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class ReportGenerationView(View):
    """Handle report generation requests"""
    
    def post(self, request, *args, **kwargs):
        """Generate a comprehensive financial report"""
        try:
            data = json.loads(request.body)
            
            # Parse dates
            start_date_str = data.get('start_date')
            end_date_str = data.get('end_date')
            
            if not start_date_str or not end_date_str:
                return JsonResponse({
                    'error': 'start_date and end_date are required'
                }, status=400)
            
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=400)
            
            # Validate date range
            if start_date > end_date:
                return JsonResponse({
                    'error': 'start_date cannot be after end_date'
                }, status=400)
            
            if (end_date - start_date).days > 365:
                return JsonResponse({
                    'error': 'Date range cannot exceed 365 days'
                }, status=400)
            
            # Generate report
            engine = FinancialReportingEngine(request.user)
            report = engine.generate_comprehensive_report(
                start_date=start_date,
                end_date=end_date,
                include_forecasts=data.get('include_forecasts', True),
                include_trends=data.get('include_trends', True)
            )
            
            # Log report generation
            log_financial_action(
                merchant=request.user,
                action='GENERATE_REPORT',
                object_id=f"report_{start_date}_{end_date}",
                amount=report['financial_summary']['net_profit']
            )
            
            return JsonResponse({
                'success': True,
                'report': report
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return JsonResponse({
                'error': 'Failed to generate report'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class QuickReportView(View):
    """Generate quick reports for common time periods"""
    
    def post(self, request, *args, **kwargs):
        """Generate a quick report for predefined periods"""
        try:
            data = json.loads(request.body)
            period = data.get('period', 'month')  # week, month, quarter, year
            
            today = date.today()
            
            # Calculate date range based on period
            if period == 'week':
                start_date = today - timedelta(days=7)
                end_date = today
            elif period == 'month':
                start_date = today - timedelta(days=30)
                end_date = today
            elif period == 'quarter':
                start_date = today - timedelta(days=90)
                end_date = today
            elif period == 'year':
                start_date = today - timedelta(days=365)
                end_date = today
            else:
                return JsonResponse({
                    'error': 'Invalid period. Use: week, month, quarter, or year'
                }, status=400)
            
            # Generate report
            engine = FinancialReportingEngine(request.user)
            report = engine.generate_comprehensive_report(
                start_date=start_date,
                end_date=end_date,
                include_forecasts=False,  # Skip forecasts for quick reports
                include_trends=True
            )
            
            return JsonResponse({
                'success': True,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'report': report
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Error generating quick report: {e}")
            return JsonResponse({
                'error': 'Failed to generate quick report'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class CustomQueryView(View):
    """Handle custom financial queries"""
    
    def post(self, request, *args, **kwargs):
        """Execute custom financial queries"""
        try:
            data = json.loads(request.body)
            query_type = data.get('query_type')
            
            if not query_type:
                return JsonResponse({
                    'error': 'query_type is required'
                }, status=400)
            
            engine = FinancialReportingEngine(request.user)
            
            # Parse date range if provided
            start_date = None
            end_date = None
            
            if data.get('start_date'):
                start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            if data.get('end_date'):
                end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            
            # Default to last 30 days if no dates provided
            if not start_date or not end_date:
                end_date = date.today()
                start_date = end_date - timedelta(days=30)
            
            result = {}
            
            if query_type == 'category_analysis':
                result = engine._get_category_breakdown(start_date, end_date)
            elif query_type == 'cash_flow_analysis':
                result = engine._analyze_cash_flow(start_date, end_date)
            elif query_type == 'payment_method_analysis':
                result = engine._analyze_payment_methods(start_date, end_date)
            elif query_type == 'currency_analysis':
                result = engine._analyze_currencies(start_date, end_date)
            elif query_type == 'monthly_trends':
                result = engine._get_monthly_trends(start_date, end_date)
            elif query_type == 'top_transactions':
                limit = data.get('limit', 10)
                result = engine._get_top_transactions(start_date, end_date, limit)
            elif query_type == 'forecasts':
                result = engine._generate_forecasts(start_date, end_date)
            elif query_type == 'trends':
                result = engine._analyze_trends(start_date, end_date)
            else:
                return JsonResponse({
                    'error': f'Unknown query_type: {query_type}'
                }, status=400)
            
            return JsonResponse({
                'success': True,
                'query_type': query_type,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'result': result
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            return JsonResponse({
                'error': 'Failed to execute custom query'
            }, status=500)


@require_http_methods(["GET"])
@login_required
def get_report_templates(request):
    """Get available report templates"""
    templates = {
        'comprehensive': {
            'name': 'Comprehensive Financial Report',
            'description': 'Complete financial analysis with forecasts and trends',
            'parameters': ['start_date', 'end_date', 'include_forecasts', 'include_trends']
        },
        'quick_monthly': {
            'name': 'Quick Monthly Report',
            'description': 'Fast monthly overview with key metrics',
            'parameters': ['period']
        },
        'category_analysis': {
            'name': 'Category Analysis',
            'description': 'Detailed breakdown by income/expense categories',
            'parameters': ['start_date', 'end_date']
        },
        'cash_flow': {
            'name': 'Cash Flow Analysis',
            'description': 'Daily cash flow patterns and trends',
            'parameters': ['start_date', 'end_date']
        },
        'payment_methods': {
            'name': 'Payment Method Analysis',
            'description': 'Usage patterns by payment method',
            'parameters': ['start_date', 'end_date']
        },
        'currency_analysis': {
            'name': 'Currency Analysis',
            'description': 'Multi-currency transaction analysis',
            'parameters': ['start_date', 'end_date']
        },
        'monthly_trends': {
            'name': 'Monthly Trends',
            'description': 'Month-over-month growth and trends',
            'parameters': ['start_date', 'end_date']
        },
        'top_transactions': {
            'name': 'Top Transactions',
            'description': 'Largest transactions in the period',
            'parameters': ['start_date', 'end_date', 'limit']
        },
        'forecasts': {
            'name': 'Financial Forecasts',
            'description': 'Future projections based on historical data',
            'parameters': ['start_date', 'end_date']
        },
        'trends': {
            'name': 'Trend Analysis',
            'description': 'Seasonal patterns and volatility metrics',
            'parameters': ['start_date', 'end_date']
        }
    }
    
    return JsonResponse({
        'success': True,
        'templates': templates
    })


@require_http_methods(["GET"])
@login_required
def get_available_periods(request):
    """Get available quick report periods"""
    periods = {
        'week': {
            'name': 'Last 7 Days',
            'description': 'Weekly overview',
            'days': 7
        },
        'month': {
            'name': 'Last 30 Days',
            'description': 'Monthly overview',
            'days': 30
        },
        'quarter': {
            'name': 'Last 90 Days',
            'description': 'Quarterly overview',
            'days': 90
        },
        'year': {
            'name': 'Last 365 Days',
            'description': 'Annual overview',
            'days': 365
        }
    }
    
    return JsonResponse({
        'success': True,
        'periods': periods
    })


@require_http_methods(["GET"])
@login_required
def export_report(request, format_type='json'):
    """Export report in various formats"""
    try:
        # Get report parameters from query string
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        if not start_date_str or not end_date_str:
            return JsonResponse({
                'error': 'start_date and end_date are required'
            }, status=400)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Generate report
        engine = FinancialReportingEngine(request.user)
        report = engine.generate_comprehensive_report(start_date, end_date)
        
        if format_type == 'json':
            response = JsonResponse({
                'success': True,
                'report': report
            })
            response['Content-Disposition'] = f'attachment; filename="financial_report_{start_date}_{end_date}.json"'
            return response
        
        elif format_type == 'csv':
            # Convert report to CSV format
            csv_data = _convert_report_to_csv(report)
            response = HttpResponse(csv_data, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="financial_report_{start_date}_{end_date}.csv"'
            return response
        
        else:
            return JsonResponse({
                'error': 'Unsupported format. Use: json or csv'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return JsonResponse({
            'error': 'Failed to export report'
        }, status=500)


def _convert_report_to_csv(report_data):
    """Convert report data to CSV format"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write report metadata
    writer.writerow(['Report Metadata'])
    writer.writerow(['Merchant ID', report_data['report_metadata']['merchant_id']])
    writer.writerow(['Period Start', report_data['report_metadata']['period_start']])
    writer.writerow(['Period End', report_data['report_metadata']['period_end']])
    writer.writerow(['Generated At', report_data['report_metadata']['generated_at']])
    writer.writerow([])
    
    # Write financial summary
    writer.writerow(['Financial Summary'])
    summary = report_data['financial_summary']
    writer.writerow(['Total Income', summary['total_income']])
    writer.writerow(['Total Expenses', summary['total_expenses']])
    writer.writerow(['Net Profit', summary['net_profit']])
    writer.writerow(['Total Transactions', summary['total_transactions']])
    writer.writerow(['Profit Margin', f"{summary['profit_margin']:.2%}"])
    writer.writerow([])
    
    # Write key metrics
    writer.writerow(['Key Metrics'])
    metrics = report_data.get('key_metrics', {})
    for key, value in metrics.items():
        writer.writerow([key.replace('_', ' ').title(), value])
    
    return output.getvalue()
