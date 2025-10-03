"""
URL patterns for the Reporting Engine
"""

from django.urls import path
from .views import (
    ReportGenerationView,
    QuickReportView,
    CustomQueryView,
    get_report_templates,
    get_available_periods,
    export_report
)

urlpatterns = [
    path('generate/', ReportGenerationView.as_view(), name='generate_report'),
    path('quick/', QuickReportView.as_view(), name='quick_report'),
    path('query/', CustomQueryView.as_view(), name='custom_query'),
    path('templates/', get_report_templates, name='report_templates'),
    path('periods/', get_available_periods, name='available_periods'),
    path('export/<str:format_type>/', export_report, name='export_report'),
]


