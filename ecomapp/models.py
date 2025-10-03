from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

class Category(models.Model):
    """Transaction categories for expense/income classification"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    category_type = models.CharField(
        max_length=20,
        choices=[('INCOME', 'Income'), ('EXPENSE', 'Expense')],
        default='EXPENSE'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.category_type})"


class Transaction(models.Model):
    """Immutable ledger for all financial transactions"""
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = models.DateTimeField(default=timezone.now)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='transactions')
    description = models.TextField()
    reference_id = models.CharField(max_length=100, blank=True)
    
    transaction_type = models.CharField(
        max_length=20,
        choices=[('INCOME', 'Income'), ('EXPENSE', 'Expense')],
        default='EXPENSE'
    )
    
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('CASH', 'Cash'),
            ('CARD', 'Credit/Debit Card'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE', 'Mobile Payment'),
            ('OTHER', 'Other')
        ],
        default='CASH'
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('COMPLETED', 'Completed'),
            ('PENDING', 'Pending'),
            ('CANCELLED', 'Cancelled')
        ],
        default='COMPLETED'
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['merchant', '-transaction_date']),
            models.Index(fields=['category', '-transaction_date']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type}: {self.amount} - {self.description[:50]}"
    
    def get_signed_amount(self):
        """Returns amount with appropriate sign (positive for income, negative for expense)"""
        if self.transaction_type == 'INCOME':
            return abs(self.amount)
        return -abs(self.amount)


class Event(models.Model):
    """Business events and deadlines"""
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_date = models.DateTimeField()
    
    deadline_type = models.CharField(
        max_length=50,
        choices=[
            ('TAX_PAYMENT', 'Tax Payment'),
            ('INVOICE_DUE', 'Invoice Due'),
            ('LOAN_REPAYMENT', 'Loan Repayment'),
            ('MEETING', 'Meeting'),
            ('REMINDER', 'Reminder'),
            ('OTHER', 'Other')
        ],
        default='OTHER'
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('UPCOMING', 'Upcoming'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
            ('OVERDUE', 'Overdue')
        ],
        default='UPCOMING'
    )
    
    calendar_id = models.CharField(max_length=200, blank=True, help_text="External calendar reference ID")
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Associated amount if applicable")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['event_date']
        indexes = [
            models.Index(fields=['merchant', 'event_date']),
            models.Index(fields=['status', 'event_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.event_date.strftime('%Y-%m-%d')}"
    
    def is_overdue(self):
        """Check if event is past due"""
        return self.event_date < timezone.now() and self.status == 'UPCOMING'


class Forecast(models.Model):
    """Financial forecasting data"""
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forecasts')
    month = models.DateField()
    forecast_amount = models.DecimalField(max_digits=12, decimal_places=2)
    forecast_type = models.CharField(
        max_length=20,
        choices=[('REVENUE', 'Revenue'), ('EXPENSE', 'Expense'), ('PROFIT', 'Profit')],
        default='REVENUE'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-month']
        unique_together = ['merchant', 'month', 'forecast_type']
    
    def __str__(self):
        return f"{self.merchant.username} - {self.month.strftime('%B %Y')}: {self.forecast_amount}"


class CurrencyRate(models.Model):
    """Cache for currency exchange rates"""
    base_currency = models.CharField(max_length=3)
    target_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    fetched_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['base_currency', 'target_currency']
        ordering = ['-fetched_at']
    
    def __str__(self):
        return f"{self.base_currency}/{self.target_currency}: {self.rate}"
