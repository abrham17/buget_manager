"""
Advanced Financial Reporting Engine

Provides comprehensive financial analytics, dynamic report generation,
and query-based aggregation for the Merchant Financial Agent.
"""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from django.db.models import Sum, Count, Avg, Q, F, Case, When, Value, DecimalField
from django.db.models.functions import TruncMonth, TruncQuarter, TruncYear, Coalesce
from django.utils import timezone
from django.contrib.auth.models import User

from ecomapp.models import Transaction, Category, Event, Forecast, CurrencyRate

logger = logging.getLogger(__name__)


class FinancialReportingEngine:
    """
    Advanced Financial Reporting Engine
    
    Provides comprehensive financial analytics with dynamic report generation,
    trend analysis, forecasting, and customizable query-based aggregation.
    """
    
    def __init__(self, merchant: User):
        self.merchant = merchant
        self.base_currency = self._get_base_currency()
    
    def _get_base_currency(self) -> str:
        """Get merchant's base currency"""
        try:
            return self.merchant.merchant_profile.base_currency or 'USD'
        except:
            return 'USD'
    
    def generate_comprehensive_report(self, 
                                    start_date: date, 
                                    end_date: date,
                                    include_forecasts: bool = True,
                                    include_trends: bool = True) -> Dict[str, Any]:
        """
        Generate a comprehensive financial report for the specified period
        """
        try:
            report_data = {
                'report_metadata': {
                    'merchant_id': self.merchant.id,
                    'merchant_name': self.merchant.username,
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat(),
                    'base_currency': self.base_currency,
                    'generated_at': timezone.now().isoformat(),
                    'report_type': 'comprehensive'
                },
                'financial_summary': self._get_financial_summary(start_date, end_date),
                'income_analysis': self._analyze_income(start_date, end_date),
                'expense_analysis': self._analyze_expenses(start_date, end_date),
                'cash_flow_analysis': self._analyze_cash_flow(start_date, end_date),
                'category_breakdown': self._get_category_breakdown(start_date, end_date),
                'monthly_trends': self._get_monthly_trends(start_date, end_date),
                'top_transactions': self._get_top_transactions(start_date, end_date),
                'payment_method_analysis': self._analyze_payment_methods(start_date, end_date),
                'currency_analysis': self._analyze_currencies(start_date, end_date),
            }
            
            if include_forecasts:
                report_data['forecasts'] = self._generate_forecasts(start_date, end_date)
            
            if include_trends:
                report_data['trend_analysis'] = self._analyze_trends(start_date, end_date)
            
            report_data['key_metrics'] = self._calculate_key_metrics(report_data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating comprehensive report: {e}")
            raise
    
    def _get_financial_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get basic financial summary for the period"""
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        income = transactions.filter(transaction_type='INCOME').aggregate(
            total=Coalesce(Sum('base_currency_amount'), Value(0, DecimalField()))
        )['total']
        
        expenses = transactions.filter(transaction_type='EXPENSE').aggregate(
            total=Coalesce(Sum('base_currency_amount'), Value(0, DecimalField()))
        )['total']
        
        transfers = transactions.filter(transaction_type='TRANSFER').aggregate(
            total=Coalesce(Sum('base_currency_amount'), Value(0, DecimalField()))
        )['total']
        
        net_profit = income - expenses
        total_transactions = transactions.count()
        
        return {
            'total_income': float(income),
            'total_expenses': float(expenses),
            'total_transfers': float(transfers),
            'net_profit': float(net_profit),
            'total_transactions': total_transactions,
            'average_transaction_size': float(income + expenses) / max(total_transactions, 1),
            'profit_margin': float(net_profit / income) if income > 0 else 0,
            'currency': self.base_currency
        }
    
    def _analyze_income(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze income patterns and trends"""
        income_transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_type='INCOME',
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        # Monthly income breakdown
        monthly_income = income_transactions.annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id'),
            average=Avg('base_currency_amount')
        ).order_by('month')
        
        # Category breakdown
        category_income = income_transactions.values('category__name').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id'),
            average=Avg('base_currency_amount')
        ).order_by('-total')
        
        # Payment method breakdown
        payment_method_income = income_transactions.values('payment_method').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Top income sources
        top_sources = income_transactions.values('description').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id')
        ).order_by('-total')[:10]
        
        return {
            'monthly_breakdown': list(monthly_income),
            'category_breakdown': list(category_income),
            'payment_method_breakdown': list(payment_method_income),
            'top_sources': list(top_sources),
            'growth_rate': self._calculate_growth_rate(income_transactions, start_date, end_date)
        }
    
    def _analyze_expenses(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze expense patterns and trends"""
        expense_transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_type='EXPENSE',
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        # Monthly expense breakdown
        monthly_expenses = expense_transactions.annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id'),
            average=Avg('base_currency_amount')
        ).order_by('month')
        
        # Category breakdown
        category_expenses = expense_transactions.values('category__name').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id'),
            average=Avg('base_currency_amount'),
            percentage=Case(
                When(
                    total=Sum('base_currency_amount'),
                    then=Value(100.0) * Sum('base_currency_amount') / 
                         Sum('base_currency_amount', filter=Q(transaction_type='EXPENSE'))
                ),
                default=Value(0.0),
                output_field=DecimalField()
            )
        ).order_by('-total')
        
        # Payment method breakdown
        payment_method_expenses = expense_transactions.values('payment_method').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Largest expenses
        largest_expenses = expense_transactions.order_by('-base_currency_amount')[:10]
        
        return {
            'monthly_breakdown': list(monthly_expenses),
            'category_breakdown': list(category_expenses),
            'payment_method_breakdown': list(payment_method_expenses),
            'largest_expenses': [
                {
                    'description': exp.description,
                    'amount': float(exp.base_currency_amount),
                    'date': exp.transaction_date.date().isoformat(),
                    'category': exp.category.name if exp.category else 'Uncategorized'
                }
                for exp in largest_expenses
            ],
            'growth_rate': self._calculate_growth_rate(expense_transactions, start_date, end_date)
        }
    
    def _analyze_cash_flow(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze cash flow patterns"""
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        # Daily cash flow
        daily_cash_flow = []
        current_date = start_date
        running_balance = Decimal('0')
        
        while current_date <= end_date:
            day_transactions = transactions.filter(transaction_date__date=current_date)
            
            daily_income = day_transactions.filter(transaction_type='INCOME').aggregate(
                total=Coalesce(Sum('base_currency_amount'), Value(0, DecimalField()))
            )['total']
            
            daily_expenses = day_transactions.filter(transaction_type='EXPENSE').aggregate(
                total=Coalesce(Sum('base_currency_amount'), Value(0, DecimalField()))
            )['total']
            
            daily_net = daily_income - daily_expenses
            running_balance += daily_net
            
            daily_cash_flow.append({
                'date': current_date.isoformat(),
                'income': float(daily_income),
                'expenses': float(daily_expenses),
                'net_cash_flow': float(daily_net),
                'running_balance': float(running_balance)
            })
            
            current_date += timedelta(days=1)
        
        # Cash flow metrics
        total_inflow = sum(day['income'] for day in daily_cash_flow)
        total_outflow = sum(day['expenses'] for day in daily_cash_flow)
        net_cash_flow = total_inflow - total_outflow
        
        # Calculate volatility
        net_flows = [day['net_cash_flow'] for day in daily_cash_flow]
        if len(net_flows) > 1:
            mean_flow = sum(net_flows) / len(net_flows)
            variance = sum((x - mean_flow) ** 2 for x in net_flows) / (len(net_flows) - 1)
            volatility = variance ** 0.5
        else:
            volatility = 0
        
        return {
            'daily_cash_flow': daily_cash_flow,
            'total_inflow': total_inflow,
            'total_outflow': total_outflow,
            'net_cash_flow': net_cash_flow,
            'volatility': volatility,
            'average_daily_flow': net_cash_flow / len(daily_cash_flow) if daily_cash_flow else 0,
            'positive_days': len([day for day in daily_cash_flow if day['net_cash_flow'] > 0]),
            'negative_days': len([day for day in daily_cash_flow if day['net_cash_flow'] < 0])
        }
    
    def _get_category_breakdown(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get detailed category breakdown"""
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        # Income by category
        income_by_category = transactions.filter(transaction_type='INCOME').values(
            'category__name'
        ).annotate(
            total=Sum('base_currency_amount'),
            count=Count('id'),
            average=Avg('base_currency_amount')
        ).order_by('-total')
        
        # Expenses by category
        expenses_by_category = transactions.filter(transaction_type='EXPENSE').values(
            'category__name'
        ).annotate(
            total=Sum('base_currency_amount'),
            count=Count('id'),
            average=Avg('base_currency_amount')
        ).order_by('-total')
        
        return {
            'income_by_category': list(income_by_category),
            'expenses_by_category': list(expenses_by_category),
            'top_income_category': list(income_by_category[:1])[0] if income_by_category else None,
            'top_expense_category': list(expenses_by_category[:1])[0] if expenses_by_category else None
        }
    
    def _get_monthly_trends(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get monthly trends and patterns"""
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        # Monthly trends
        monthly_data = transactions.annotate(
            month=TruncMonth('transaction_date')
        ).values('month', 'transaction_type').annotate(
            total=Sum('base_currency_amount'),
            count=Count('id')
        ).order_by('month', 'transaction_type')
        
        # Calculate month-over-month growth
        monthly_totals = {}
        for item in monthly_data:
            month_key = item['month'].strftime('%Y-%m')
            if month_key not in monthly_totals:
                monthly_totals[month_key] = {'income': 0, 'expenses': 0}
            
            if item['transaction_type'] == 'INCOME':
                monthly_totals[month_key]['income'] = float(item['total'])
            elif item['transaction_type'] == 'EXPENSE':
                monthly_totals[month_key]['expenses'] = float(item['total'])
        
        # Calculate growth rates
        months = sorted(monthly_totals.keys())
        growth_rates = []
        
        for i in range(1, len(months)):
            prev_month = monthly_totals[months[i-1]]
            curr_month = monthly_totals[months[i]]
            
            income_growth = self._calculate_percentage_change(
                prev_month['income'], curr_month['income']
            )
            expense_growth = self._calculate_percentage_change(
                prev_month['expenses'], curr_month['expenses']
            )
            
            growth_rates.append({
                'month': months[i],
                'income_growth': income_growth,
                'expense_growth': expense_growth,
                'net_growth': income_growth - expense_growth
            })
        
        return {
            'monthly_data': list(monthly_data),
            'monthly_totals': monthly_totals,
            'growth_rates': growth_rates,
            'average_monthly_income': sum(totals['income'] for totals in monthly_totals.values()) / len(monthly_totals) if monthly_totals else 0,
            'average_monthly_expenses': sum(totals['expenses'] for totals in monthly_totals.values()) / len(monthly_totals) if monthly_totals else 0
        }
    
    def _get_top_transactions(self, start_date: date, end_date: date, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top transactions by amount"""
        top_income = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_type='INCOME',
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        ).order_by('-base_currency_amount')[:limit]
        
        top_expenses = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_type='EXPENSE',
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        ).order_by('-base_currency_amount')[:limit]
        
        transactions = []
        
        for transaction in top_income:
            transactions.append({
                'type': 'INCOME',
                'description': transaction.description,
                'amount': float(transaction.base_currency_amount),
                'date': transaction.transaction_date.date().isoformat(),
                'category': transaction.category.name if transaction.category else 'Uncategorized',
                'payment_method': transaction.payment_method
            })
        
        for transaction in top_expenses:
            transactions.append({
                'type': 'EXPENSE',
                'description': transaction.description,
                'amount': float(transaction.base_currency_amount),
                'date': transaction.transaction_date.date().isoformat(),
                'category': transaction.category.name if transaction.category else 'Uncategorized',
                'payment_method': transaction.payment_method
            })
        
        return sorted(transactions, key=lambda x: x['amount'], reverse=True)[:limit]
    
    def _analyze_payment_methods(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze payment method usage and patterns"""
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        payment_method_stats = transactions.values('payment_method').annotate(
            total_amount=Sum('base_currency_amount'),
            count=Count('id'),
            average_amount=Avg('base_currency_amount'),
            income_amount=Sum(
                'base_currency_amount',
                filter=Q(transaction_type='INCOME')
            ),
            expense_amount=Sum(
                'base_currency_amount',
                filter=Q(transaction_type='EXPENSE')
            )
        ).order_by('-total_amount')
        
        return {
            'payment_method_usage': list(payment_method_stats),
            'most_used_method': list(payment_method_stats[:1])[0] if payment_method_stats else None,
            'total_methods_used': len(payment_method_stats)
        }
    
    def _analyze_currencies(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze currency usage and conversion patterns"""
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        ).exclude(currency=self.base_currency)
        
        currency_stats = transactions.values('currency').annotate(
            total_amount=Sum('amount'),
            total_base_amount=Sum('base_currency_amount'),
            count=Count('id'),
            average_exchange_rate=Avg('exchange_rate')
        ).order_by('-total_base_amount')
        
        return {
            'foreign_currency_usage': list(currency_stats),
            'currencies_used': [item['currency'] for item in currency_stats],
            'total_foreign_transactions': sum(item['count'] for item in currency_stats)
        }
    
    def _generate_forecasts(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Generate financial forecasts based on historical data"""
        # Get existing forecasts
        forecasts = Forecast.objects.filter(
            merchant=self.merchant,
            period_start__lte=end_date,
            period_end__gte=start_date
        ).order_by('-period_start')
        
        # Calculate simple trend-based forecasts
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        # Monthly averages for forecasting
        monthly_income = transactions.filter(transaction_type='INCOME').annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            total=Sum('base_currency_amount')
        ).order_by('month')
        
        monthly_expenses = transactions.filter(transaction_type='EXPENSE').annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            total=Sum('base_currency_amount')
        ).order_by('month')
        
        # Simple linear trend forecasting
        if len(monthly_income) >= 2:
            income_trend = self._calculate_linear_trend([float(item['total']) for item in monthly_income])
            expense_trend = self._calculate_linear_trend([float(item['total']) for item in monthly_expenses])
        else:
            income_trend = {'slope': 0, 'intercept': 0}
            expense_trend = {'slope': 0, 'intercept': 0}
        
        # Generate next 3 months forecast
        next_month = end_date + timedelta(days=30)
        forecast_data = []
        
        for i in range(3):
            forecast_date = next_month + timedelta(days=30 * i)
            
            predicted_income = max(0, income_trend['slope'] * (i + 1) + income_trend['intercept'])
            predicted_expenses = max(0, expense_trend['slope'] * (i + 1) + expense_trend['intercept'])
            predicted_profit = predicted_income - predicted_expenses
            
            forecast_data.append({
                'period': forecast_date.strftime('%Y-%m'),
                'predicted_income': predicted_income,
                'predicted_expenses': predicted_expenses,
                'predicted_profit': predicted_profit,
                'confidence_level': 0.7 - (i * 0.1)  # Decreasing confidence over time
            })
        
        return {
            'existing_forecasts': [
                {
                    'period_start': f.period_start.isoformat(),
                    'period_end': f.period_end.isoformat() if f.period_end else None,
                    'forecast_type': f.forecast_type,
                    'forecast_amount': float(f.forecast_amount),
                    'currency': f.currency,
                    'confidence_level': f.confidence_level,
                    'notes': f.notes
                }
                for f in forecasts
            ],
            'trend_forecasts': forecast_data,
            'income_trend': income_trend,
            'expense_trend': expense_trend
        }
    
    def _analyze_trends(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze financial trends and patterns"""
        transactions = Transaction.objects.filter(
            merchant=self.merchant,
            transaction_date__date__range=[start_date, end_date],
            status='COMPLETED',
            is_deleted=False
        )
        
        # Calculate various trends
        total_income = transactions.filter(transaction_type='INCOME').aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0')
        
        total_expenses = transactions.filter(transaction_type='EXPENSE').aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0')
        
        # Seasonal analysis (if we have enough data)
        seasonal_patterns = self._analyze_seasonal_patterns(transactions, start_date, end_date)
        
        # Growth trends
        growth_trends = self._calculate_growth_trends(transactions, start_date, end_date)
        
        # Volatility analysis
        volatility_metrics = self._calculate_volatility_metrics(transactions, start_date, end_date)
        
        return {
            'seasonal_patterns': seasonal_patterns,
            'growth_trends': growth_trends,
            'volatility_metrics': volatility_metrics,
            'overall_trend': 'positive' if total_income > total_expenses else 'negative',
            'profitability_trend': float(total_income - total_expenses) / float(total_income) if total_income > 0 else 0
        }
    
    def _calculate_key_metrics(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate key financial metrics and KPIs"""
        financial_summary = report_data['financial_summary']
        cash_flow = report_data['cash_flow_analysis']
        
        # Key metrics
        metrics = {
            'profit_margin': financial_summary['profit_margin'],
            'revenue_growth_rate': report_data.get('income_analysis', {}).get('growth_rate', 0),
            'expense_growth_rate': report_data.get('expense_analysis', {}).get('growth_rate', 0),
            'cash_flow_volatility': cash_flow['volatility'],
            'average_daily_cash_flow': cash_flow['average_daily_flow'],
            'positive_cash_flow_days': cash_flow['positive_days'],
            'negative_cash_flow_days': cash_flow['negative_days'],
            'cash_flow_consistency': cash_flow['positive_days'] / (cash_flow['positive_days'] + cash_flow['negative_days']) if (cash_flow['positive_days'] + cash_flow['negative_days']) > 0 else 0,
            'transaction_frequency': financial_summary['total_transactions'] / max((report_data['report_metadata']['period_end'] - report_data['report_metadata']['period_start']).days, 1),
            'average_transaction_size': financial_summary['average_transaction_size']
        }
        
        # Calculate efficiency ratios
        if financial_summary['total_expenses'] > 0:
            metrics['expense_to_income_ratio'] = financial_summary['total_expenses'] / financial_summary['total_income']
        else:
            metrics['expense_to_income_ratio'] = 0
        
        # Calculate trend indicators
        monthly_trends = report_data.get('monthly_trends', {})
        if monthly_trends.get('growth_rates'):
            recent_growth = monthly_trends['growth_rates'][-1] if monthly_trends['growth_rates'] else {}
            metrics['recent_income_growth'] = recent_growth.get('income_growth', 0)
            metrics['recent_expense_growth'] = recent_growth.get('expense_growth', 0)
            metrics['recent_net_growth'] = recent_growth.get('net_growth', 0)
        
        return metrics
    
    # Helper methods
    def _calculate_growth_rate(self, queryset, start_date: date, end_date: date) -> float:
        """Calculate growth rate for a queryset"""
        period_days = (end_date - start_date).days
        if period_days <= 0:
            return 0
        
        # Split period in half
        mid_date = start_date + timedelta(days=period_days // 2)
        
        first_half = queryset.filter(transaction_date__date__range=[start_date, mid_date]).aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0')
        
        second_half = queryset.filter(transaction_date__date__range=[mid_date, end_date]).aggregate(
            total=Sum('base_currency_amount')
        )['total'] or Decimal('0')
        
        if first_half == 0:
            return 100.0 if second_half > 0 else 0
        
        return float((second_half - first_half) / first_half * 100)
    
    def _calculate_percentage_change(self, old_value: float, new_value: float) -> float:
        """Calculate percentage change between two values"""
        if old_value == 0:
            return 100.0 if new_value > 0 else 0
        return ((new_value - old_value) / old_value) * 100
    
    def _calculate_linear_trend(self, values: List[float]) -> Dict[str, float]:
        """Calculate linear trend for a series of values"""
        if len(values) < 2:
            return {'slope': 0, 'intercept': 0}
        
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        intercept = (y_sum - slope * x_sum) / n
        
        return {'slope': slope, 'intercept': intercept}
    
    def _analyze_seasonal_patterns(self, transactions, start_date: date, end_date: date) -> Dict[str, Any]:
        """Analyze seasonal patterns in transactions"""
        # Group by month to identify seasonal patterns
        monthly_data = transactions.annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            income=Sum('base_currency_amount', filter=Q(transaction_type='INCOME')),
            expenses=Sum('base_currency_amount', filter=Q(transaction_type='EXPENSE'))
        ).order_by('month')
        
        # Calculate seasonal averages
        monthly_totals = {}
        for item in monthly_data:
            month_name = item['month'].strftime('%B')
            if month_name not in monthly_totals:
                monthly_totals[month_name] = {'income': 0, 'expenses': 0, 'count': 0}
            
            monthly_totals[month_name]['income'] += float(item['income'] or 0)
            monthly_totals[month_name]['expenses'] += float(item['expenses'] or 0)
            monthly_totals[month_name]['count'] += 1
        
        # Calculate averages
        for month in monthly_totals:
            if monthly_totals[month]['count'] > 0:
                monthly_totals[month]['avg_income'] = monthly_totals[month]['income'] / monthly_totals[month]['count']
                monthly_totals[month]['avg_expenses'] = monthly_totals[month]['expenses'] / monthly_totals[month]['count']
        
        return {
            'monthly_patterns': monthly_totals,
            'peak_month': max(monthly_totals.keys(), key=lambda x: monthly_totals[x]['avg_income']) if monthly_totals else None,
            'low_month': min(monthly_totals.keys(), key=lambda x: monthly_totals[x]['avg_income']) if monthly_totals else None
        }
    
    def _calculate_growth_trends(self, transactions, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate growth trends"""
        # Calculate week-over-week growth
        weekly_data = transactions.annotate(
            week=TruncMonth('transaction_date')  # Using month as proxy for week in this simplified version
        ).values('week').annotate(
            income=Sum('base_currency_amount', filter=Q(transaction_type='INCOME')),
            expenses=Sum('base_currency_amount', filter=Q(transaction_type='EXPENSE'))
        ).order_by('week')
        
        growth_rates = []
        prev_income = 0
        prev_expenses = 0
        
        for item in weekly_data:
            current_income = float(item['income'] or 0)
            current_expenses = float(item['expenses'] or 0)
            
            if prev_income > 0:
                income_growth = ((current_income - prev_income) / prev_income) * 100
            else:
                income_growth = 0
            
            if prev_expenses > 0:
                expense_growth = ((current_expenses - prev_expenses) / prev_expenses) * 100
            else:
                expense_growth = 0
            
            growth_rates.append({
                'week': item['week'].strftime('%Y-%m-%d'),
                'income_growth': income_growth,
                'expense_growth': expense_growth,
                'net_growth': income_growth - expense_growth
            })
            
            prev_income = current_income
            prev_expenses = current_expenses
        
        return {
            'weekly_growth': growth_rates,
            'average_income_growth': sum(item['income_growth'] for item in growth_rates) / len(growth_rates) if growth_rates else 0,
            'average_expense_growth': sum(item['expense_growth'] for item in growth_rates) / len(growth_rates) if growth_rates else 0
        }
    
    def _calculate_volatility_metrics(self, transactions, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate volatility metrics"""
        # Daily volatility
        daily_totals = transactions.annotate(
            day=TruncMonth('transaction_date')  # Simplified to monthly for this example
        ).values('day').annotate(
            income=Sum('base_currency_amount', filter=Q(transaction_type='INCOME')),
            expenses=Sum('base_currency_amount', filter=Q(transaction_type='EXPENSE'))
        ).order_by('day')
        
        income_values = [float(item['income'] or 0) for item in daily_totals]
        expense_values = [float(item['expenses'] or 0) for item in daily_totals]
        
        if len(income_values) > 1:
            income_mean = sum(income_values) / len(income_values)
            income_variance = sum((x - income_mean) ** 2 for x in income_values) / (len(income_values) - 1)
            income_volatility = income_variance ** 0.5
        else:
            income_volatility = 0
        
        if len(expense_values) > 1:
            expense_mean = sum(expense_values) / len(expense_values)
            expense_variance = sum((x - expense_mean) ** 2 for x in expense_values) / (len(expense_values) - 1)
            expense_volatility = expense_variance ** 0.5
        else:
            expense_volatility = 0
        
        return {
            'income_volatility': income_volatility,
            'expense_volatility': expense_volatility,
            'overall_volatility': (income_volatility + expense_volatility) / 2,
            'volatility_trend': 'stable' if (income_volatility + expense_volatility) / 2 < 100 else 'volatile'
        }


