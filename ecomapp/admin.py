from django.contrib import admin
from .models import Category, Transaction, Event, Forecast, CurrencyRate, AuditLog, MerchantProfile


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'merchant', 'category_type', 'is_active', 'created_at']
    list_filter = ['category_type', 'is_active', 'merchant']
    search_fields = ['name', 'merchant__username']
    list_editable = ['is_active']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'amount', 'currency', 'transaction_type', 'category', 'transaction_date', 'status', 'is_deleted']
    list_filter = ['transaction_type', 'status', 'currency', 'payment_method', 'is_deleted', 'transaction_date']
    search_fields = ['description', 'reference_id', 'merchant__username']
    date_hierarchy = 'transaction_date'
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    list_editable = ['status']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'title', 'event_date', 'deadline_type', 'priority', 'status', 'is_deleted']
    list_filter = ['deadline_type', 'status', 'priority', 'calendar_provider', 'is_deleted', 'event_date']
    search_fields = ['title', 'description', 'merchant__username']
    date_hierarchy = 'event_date'
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    list_editable = ['status', 'priority']


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'period_start', 'forecast_type', 'forecast_amount', 'currency', 'confidence_level']
    list_filter = ['forecast_type', 'forecast_method', 'currency', 'period_start']
    search_fields = ['merchant__username', 'notes']
    date_hierarchy = 'period_start'
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ['base_currency', 'target_currency', 'rate', 'source_api', 'fetched_at']
    list_filter = ['base_currency', 'target_currency', 'source_api']
    search_fields = ['base_currency', 'target_currency']
    readonly_fields = ['id', 'fetched_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'action', 'model_name', 'object_id', 'user', 'timestamp']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['merchant__username', 'model_name', 'object_id']
    date_hierarchy = 'timestamp'
    readonly_fields = ['id', 'timestamp']


@admin.register(MerchantProfile)
class MerchantProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'business_name', 'business_type', 'base_currency', 'google_calendar_enabled']
    list_filter = ['business_type', 'base_currency', 'google_calendar_enabled']
    search_fields = ['user__username', 'business_name', 'business_type']
    readonly_fields = ['created_at', 'updated_at']
