from django.contrib import admin
from .models import Category, Transaction, Event, Forecast, CurrencyRate


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'created_at']
    list_filter = ['category_type']
    search_fields = ['name']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'amount', 'transaction_type', 'category', 'transaction_date', 'status']
    list_filter = ['transaction_type', 'status', 'transaction_date']
    search_fields = ['description', 'reference_id']
    date_hierarchy = 'transaction_date'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'title', 'event_date', 'deadline_type', 'status']
    list_filter = ['deadline_type', 'status', 'event_date']
    search_fields = ['title', 'description']
    date_hierarchy = 'event_date'


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'month', 'forecast_type', 'forecast_amount']
    list_filter = ['forecast_type', 'month']


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ['base_currency', 'target_currency', 'rate', 'fetched_at']
    list_filter = ['base_currency', 'target_currency']
