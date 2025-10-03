from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import uuid
import json

class Category(models.Model):
    """Transaction categories for expense/income classification - TR_CATEGORIES"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category_type = models.CharField(
        max_length=20,
        choices=[('INCOME', 'Income'), ('EXPENSE', 'Expense')],
        default='EXPENSE'
    )
    color_code = models.CharField(max_length=7, default='#007bff', help_text="Hex color code for UI display")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['category_type', 'name']
        unique_together = ['merchant', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.category_type}) - {self.merchant.username}"


class Transaction(models.Model):
    """Immutable ledger for all financial transactions - TR_TRANSACTIONS"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=15, decimal_places=4)  # Increased precision for international currencies
    transaction_date = models.DateTimeField(default=timezone.now)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='transactions')
    description = models.TextField()
    reference_id = models.CharField(max_length=200, blank=True, db_index=True)
    
    transaction_type = models.CharField(
        max_length=20,
        choices=[('INCOME', 'Income'), ('EXPENSE', 'Expense'), ('TRANSFER', 'Transfer')],
        default='EXPENSE'
    )
    
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('CASH', 'Cash'),
            ('CARD', 'Credit/Debit Card'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE', 'Mobile Payment'),
            ('CRYPTOCURRENCY', 'Cryptocurrency'),
            ('CHECK', 'Check'),
            ('WIRE', 'Wire Transfer'),
            ('OTHER', 'Other')
        ],
        default='CASH'
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('COMPLETED', 'Completed'),
            ('PENDING', 'Pending'),
            ('CANCELLED', 'Cancelled'),
            ('REVERSED', 'Reversed'),
            ('FAILED', 'Failed')
        ],
        default='COMPLETED'
    )
    
    # Currency and FX fields
    currency = models.CharField(max_length=3, default='USD', help_text="ISO 4217 currency code")
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, 
                                      help_text="Exchange rate used for conversion")
    base_currency_amount = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True,
                                             help_text="Amount converted to base currency")
    
    # Enhanced metadata
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True, help_text="Transaction tags for categorization")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional transaction metadata")
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='created_transactions')
    
    # Soft delete support
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='deleted_transactions')
    
    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['merchant', '-transaction_date']),
            models.Index(fields=['category', '-transaction_date']),
            models.Index(fields=['transaction_type', '-transaction_date']),
            models.Index(fields=['status', '-transaction_date']),
            models.Index(fields=['currency', '-transaction_date']),
            models.Index(fields=['reference_id']),
            models.Index(fields=['is_deleted', '-transaction_date']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type}: {self.amount} {self.currency} - {self.description[:50]}"
    
    def get_signed_amount(self):
        """Returns amount with appropriate sign (positive for income, negative for expense)"""
        if self.transaction_type == 'INCOME':
            return abs(self.amount)
        elif self.transaction_type == 'EXPENSE':
            return -abs(self.amount)
        return self.amount  # For transfers, return as-is
    
    def soft_delete(self, user=None):
        """Soft delete the transaction"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()
    
    def get_base_currency_amount(self):
        """Get amount in base currency (USD equivalent)"""
        if self.base_currency_amount:
            return self.base_currency_amount
        if self.currency == 'USD':
            return self.amount
        return None  # Need to convert using exchange rate


class Event(models.Model):
    """Business events and deadlines - TR_EVENTS"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True, help_text="End date for events with duration")
    
    deadline_type = models.CharField(
        max_length=50,
        choices=[
            ('TAX_PAYMENT', 'Tax Payment'),
            ('INVOICE_DUE', 'Invoice Due'),
            ('LOAN_REPAYMENT', 'Loan Repayment'),
            ('MEETING', 'Meeting'),
            ('REMINDER', 'Reminder'),
            ('DEADLINE', 'Deadline'),
            ('APPOINTMENT', 'Appointment'),
            ('REVIEW', 'Review'),
            ('AUDIT', 'Audit'),
            ('RENEWAL', 'Renewal'),
            ('OTHER', 'Other')
        ],
        default='OTHER'
    )
    
    priority = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical')
        ],
        default='MEDIUM'
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('UPCOMING', 'Upcoming'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
            ('OVERDUE', 'Overdue'),
            ('IN_PROGRESS', 'In Progress'),
            ('RESCHEDULED', 'Rescheduled')
        ],
        default='UPCOMING'
    )
    
    # External calendar integration
    calendar_id = models.CharField(max_length=200, blank=True, help_text="External calendar reference ID")
    calendar_provider = models.CharField(max_length=50, default='GOOGLE', 
                                       choices=[('GOOGLE', 'Google Calendar'), ('OUTLOOK', 'Outlook'), ('OTHER', 'Other')])
    
    # Financial association
    amount = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True, help_text="Associated amount if applicable")
    currency = models.CharField(max_length=3, default='USD', help_text="Currency for associated amount")
    
    # Event metadata
    location = models.CharField(max_length=500, blank=True, help_text="Event location or venue")
    attendees = models.JSONField(default=list, blank=True, help_text="List of attendee email addresses")
    tags = models.JSONField(default=list, blank=True, help_text="Event tags for categorization")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional event metadata")
    
    # Recurrence support
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=200, blank=True, help_text="Recurrence rule (RRULE format)")
    parent_event = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, 
                                   related_name='recurrence_instances')
    
    # Reminder settings
    reminder_minutes = models.IntegerField(default=15, help_text="Reminder time in minutes before event")
    reminder_sent = models.BooleanField(default=False)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='created_events')
    
    # Soft delete support
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['event_date']
        indexes = [
            models.Index(fields=['merchant', 'event_date']),
            models.Index(fields=['status', 'event_date']),
            models.Index(fields=['deadline_type', 'event_date']),
            models.Index(fields=['priority', 'event_date']),
            models.Index(fields=['calendar_id']),
            models.Index(fields=['is_deleted', 'event_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.event_date.strftime('%Y-%m-%d %H:%M')}"
    
    def is_overdue(self):
        """Check if event is past due"""
        return self.event_date < timezone.now() and self.status == 'UPCOMING'
    
    def get_duration_minutes(self):
        """Get event duration in minutes"""
        if self.end_date:
            return int((self.end_date - self.event_date).total_seconds() / 60)
        return None
    
    def is_all_day(self):
        """Check if event is all-day"""
        return self.end_date is None
    
    def soft_delete(self):
        """Soft delete the event"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Forecast(models.Model):
    """Financial forecasting data - TR_FORECASTS"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forecasts')
    period_start = models.DateField()
    period_end = models.DateField(null=True, blank=True)
    forecast_amount = models.DecimalField(max_digits=15, decimal_places=4)
    currency = models.CharField(max_length=3, default='USD')
    
    forecast_type = models.CharField(
        max_length=20,
        choices=[
            ('REVENUE', 'Revenue'), 
            ('EXPENSE', 'Expense'), 
            ('PROFIT', 'Profit'),
            ('CASH_FLOW', 'Cash Flow'),
            ('GROWTH', 'Growth Rate')
        ],
        default='REVENUE'
    )
    
    forecast_method = models.CharField(
        max_length=50,
        choices=[
            ('HISTORICAL_AVERAGE', 'Historical Average'),
            ('LINEAR_TREND', 'Linear Trend'),
            ('SEASONAL', 'Seasonal Analysis'),
            ('MANUAL', 'Manual Entry'),
            ('AI_PREDICTION', 'AI Prediction')
        ],
        default='HISTORICAL_AVERAGE'
    )
    
    confidence_level = models.IntegerField(
        choices=[(i, f"{i}%") for i in range(50, 101, 5)],
        default=80,
        help_text="Confidence level in percentage"
    )
    
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Forecast metadata and assumptions")
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='created_forecasts')
    
    class Meta:
        ordering = ['-period_start']
        unique_together = ['merchant', 'period_start', 'forecast_type']
        indexes = [
            models.Index(fields=['merchant', 'period_start']),
            models.Index(fields=['forecast_type', 'period_start']),
        ]
    
    def __str__(self):
        return f"{self.merchant.username} - {self.period_start.strftime('%Y-%m')}: {self.forecast_amount} {self.currency} ({self.forecast_type})"


class CurrencyRate(models.Model):
    """Cache for currency exchange rates"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    base_currency = models.CharField(max_length=3, db_index=True)
    target_currency = models.CharField(max_length=3, db_index=True)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    source_api = models.CharField(max_length=50, default='exchangerate-api', help_text="Source API for the rate")
    fetched_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['base_currency', 'target_currency']
        ordering = ['-fetched_at']
        indexes = [
            models.Index(fields=['base_currency', 'target_currency']),
            models.Index(fields=['-fetched_at']),
        ]
    
    def __str__(self):
        return f"{self.base_currency}/{self.target_currency}: {self.rate} ({self.source_api})"
    
    def is_stale(self, hours=1):
        """Check if the rate is stale (older than specified hours)"""
        from datetime import timedelta
        return self.fetched_at < timezone.now() - timedelta(hours=hours)


class AuditLog(models.Model):
    """Audit trail for financial data changes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    
    action = models.CharField(
        max_length=50,
        choices=[
            ('CREATE', 'Create'),
            ('UPDATE', 'Update'),
            ('DELETE', 'Delete'),
            ('VIEW', 'View'),
            ('EXPORT', 'Export'),
            ('IMPORT', 'Import')
        ]
    )
    
    model_name = models.CharField(max_length=50, help_text="Name of the model being audited")
    object_id = models.UUIDField(help_text="ID of the object being audited")
    
    old_values = models.JSONField(null=True, blank=True, help_text="Previous values before change")
    new_values = models.JSONField(null=True, blank=True, help_text="New values after change")
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                           related_name='performed_audits')
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['merchant', '-timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action} {self.model_name} {self.object_id} by {self.user.username if self.user else 'System'}"


class MerchantProfile(models.Model):
    """Extended merchant profile with business information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='merchant_profile')
    
    business_name = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(
        max_length=100,
        choices=[
            ('RETAIL', 'Retail'),
            ('WHOLESALE', 'Wholesale'),
            ('SERVICE', 'Service'),
            ('MANUFACTURING', 'Manufacturing'),
            ('RESTAURANT', 'Restaurant'),
            ('CONSULTING', 'Consulting'),
            ('ONLINE', 'Online Business'),
            ('OTHER', 'Other')
        ],
        default='OTHER'
    )
    
    base_currency = models.CharField(max_length=3, default='USD')
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Business settings
    fiscal_year_start = models.DateField(default='2024-01-01')
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Contact information
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    
    # Integration settings
    google_calendar_enabled = models.BooleanField(default=False)
    google_calendar_id = models.CharField(max_length=200, blank=True)
    
    # Preferences
    default_reminder_minutes = models.IntegerField(default=15)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.business_name or self.user.username} - {self.business_type}"
