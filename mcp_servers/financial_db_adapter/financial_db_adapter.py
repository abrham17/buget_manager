"""
FinancialDB Adapter MCP Server

Implements secure database access for the Merchant Financial Agent,
providing financial reporting, transaction queries, and data aggregation
through a secure RAG-Database barrier.
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
import logging

# Add Django project to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

from django.db.models import Sum, Count, Q, Avg
from django.contrib.auth.models import User
from django.utils import timezone
from ecomapp.models import Transaction, Category, Event, Forecast

from ..base_mcp_server import BaseMCPServer, MCPServerError, MCPAuthenticationError

logger = logging.getLogger(__name__)


class FinancialDBAdapter(BaseMCPServer):
    """
    FinancialDB Adapter MCP Server
    
    Provides secure access to financial data through parameterized queries
    and structured reporting. Implements the RAG-Database barrier to ensure
    LLM core never has direct database access.
    """
    
    def __init__(self):
        super().__init__("FinancialDB Adapter", "1.0.0")
    
    def _initialize_tools(self):
        """Initialize financial database tools"""
        
        # Transaction Query Tool
        self.register_tool(
            name="query_transactions",
            description="Query financial transactions with filters",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "transaction_type": {"type": "string", "enum": ["INCOME", "EXPENSE", "ALL"]},
                    "category_id": {"type": "integer", "description": "Category ID filter"},
                    "start_date": {"type": "string", "format": "date", "description": "Start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "format": "date", "description": "End date (YYYY-MM-DD)"},
                    "payment_method": {"type": "string", "enum": ["CASH", "CARD", "BANK_TRANSFER", "MOBILE", "OTHER"]},
                    "status": {"type": "string", "enum": ["COMPLETED", "PENDING", "CANCELLED"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100}
                },
                "required": ["merchant_id"]
            }
        )
        
        # Financial Summary Tool
        self.register_tool(
            name="generate_summary",
            description="Generate financial summary reports",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "timeframe": {"type": "string", "enum": ["week", "month", "quarter", "year", "custom"]},
                    "start_date": {"type": "string", "format": "date", "description": "Custom start date"},
                    "end_date": {"type": "string", "format": "date", "description": "Custom end date"},
                    "include_categories": {"type": "boolean", "default": True},
                    "include_breakdown": {"type": "boolean", "default": False}
                },
                "required": ["merchant_id", "timeframe"]
            }
        )
        
        # Revenue Analysis Tool
        self.register_tool(
            name="analyze_revenue",
            description="Analyze revenue trends and patterns",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "period": {"type": "string", "enum": ["month", "quarter", "year"]},
                    "comparison_periods": {"type": "integer", "minimum": 1, "maximum": 12, "default": 3},
                    "include_forecasting": {"type": "boolean", "default": False}
                },
                "required": ["merchant_id", "period"]
            }
        )
        
        # Expense Analysis Tool
        self.register_tool(
            name="analyze_expenses",
            description="Analyze expense patterns and categories",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "period": {"type": "string", "enum": ["month", "quarter", "year"]},
                    "top_categories": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
                    "include_trends": {"type": "boolean", "default": True}
                },
                "required": ["merchant_id", "period"]
            }
        )
        
        # Cash Flow Analysis Tool
        self.register_tool(
            name="analyze_cash_flow",
            description="Analyze cash flow patterns and projections",
            input_schema={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "period_months": {"type": "integer", "minimum": 1, "maximum": 24, "default": 6},
                    "include_projection": {"type": "boolean", "default": True}
                },
                "required": ["merchant_id"]
            }
        )
        
        # Category Management Tool
        self.register_tool(
            name="manage_categories",
            description="List and manage transaction categories",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "create", "update"]},
                    "category_type": {"type": "string", "enum": ["INCOME", "EXPENSE"]},
                    "name": {"type": "string", "description": "Category name"},
                    "description": {"type": "string", "description": "Category description"},
                    "category_id": {"type": "integer", "description": "Category ID for updates"}
                },
                "required": ["action"]
            }
        )
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute financial database tools"""
        
        try:
            if tool_name == "query_transactions":
                return await self._query_transactions(arguments)
            elif tool_name == "generate_summary":
                return await self._generate_summary(arguments)
            elif tool_name == "analyze_revenue":
                return await self._analyze_revenue(arguments)
            elif tool_name == "analyze_expenses":
                return await self._analyze_expenses(arguments)
            elif tool_name == "analyze_cash_flow":
                return await self._analyze_cash_flow(arguments)
            elif tool_name == "manage_categories":
                return await self._manage_categories(arguments)
            else:
                raise MCPServerError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise MCPServerError(f"Database operation failed: {str(e)}")
    
    async def _query_transactions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Query transactions with filters"""
        merchant_id = args["merchant_id"]
        
        # Verify merchant exists
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Build query
        query = Transaction.objects.filter(merchant=merchant)
        
        # Apply filters
        if args.get("transaction_type") and args["transaction_type"] != "ALL":
            query = query.filter(transaction_type=args["transaction_type"])
        
        if args.get("category_id"):
            query = query.filter(category_id=args["category_id"])
        
        if args.get("start_date"):
            query = query.filter(transaction_date__gte=args["start_date"])
        
        if args.get("end_date"):
            query = query.filter(transaction_date__lte=args["end_date"])
        
        if args.get("payment_method"):
            query = query.filter(payment_method=args["payment_method"])
        
        if args.get("status"):
            query = query.filter(status=args["status"])
        
        # Apply limit
        limit = args.get("limit", 100)
        transactions = query.order_by("-transaction_date")[:limit]
        
        # Serialize results
        results = []
        for transaction in transactions:
            results.append({
                "id": transaction.id,
                "amount": float(transaction.amount),
                "transaction_type": transaction.transaction_type,
                "description": transaction.description,
                "transaction_date": transaction.transaction_date.isoformat(),
                "category": transaction.category.name if transaction.category else None,
                "payment_method": transaction.payment_method,
                "status": transaction.status,
                "reference_id": transaction.reference_id
            })
        
        return {
            "transactions": results,
            "total_count": len(results),
            "filters_applied": {k: v for k, v in args.items() if v is not None}
        }
    
    async def _generate_summary(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generate financial summary report"""
        merchant_id = args["merchant_id"]
        timeframe = args["timeframe"]
        
        # Verify merchant exists
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Calculate date range
        end_date = timezone.now()
        if timeframe == "week":
            start_date = end_date - timedelta(days=7)
        elif timeframe == "month":
            start_date = end_date - timedelta(days=30)
        elif timeframe == "quarter":
            start_date = end_date - timedelta(days=90)
        elif timeframe == "year":
            start_date = end_date - timedelta(days=365)
        elif timeframe == "custom":
            start_date = datetime.fromisoformat(args["start_date"])
            end_date = datetime.fromisoformat(args["end_date"])
        else:
            start_date = end_date - timedelta(days=30)
        
        # Query transactions
        transactions = Transaction.objects.filter(
            merchant=merchant,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            status="COMPLETED"
        )
        
        # Calculate totals
        income_total = transactions.filter(transaction_type="INCOME").aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')
        expense_total = transactions.filter(transaction_type="EXPENSE").aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')
        net_balance = income_total - expense_total
        
        # Category breakdown
        category_breakdown = {}
        if args.get("include_categories", True):
            expense_categories = transactions.filter(transaction_type="EXPENSE").values(
                'category__name').annotate(total=Sum('amount')).order_by('-total')
            income_categories = transactions.filter(transaction_type="INCOME").values(
                'category__name').annotate(total=Sum('amount')).order_by('-total')
            
            category_breakdown = {
                "expenses": [{"category": item["category__name"], "amount": float(item["total"])} 
                           for item in expense_categories if item["category__name"]],
                "income": [{"category": item["category__name"], "amount": float(item["total"])} 
                         for item in income_categories if item["category__name"]]
            }
        
        return {
            "summary": {
                "timeframe": timeframe,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_income": float(income_total),
                "total_expenses": float(expense_total),
                "net_balance": float(net_balance),
                "transaction_count": transactions.count()
            },
            "category_breakdown": category_breakdown,
            "generated_at": timezone.now().isoformat()
        }
    
    async def _analyze_revenue(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze revenue trends and patterns"""
        merchant_id = args["merchant_id"]
        period = args["period"]
        comparison_periods = args.get("comparison_periods", 3)
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Calculate periods
        periods = []
        for i in range(comparison_periods):
            if period == "month":
                start = timezone.now() - timedelta(days=30 * (i + 1))
                end = timezone.now() - timedelta(days=30 * i)
            elif period == "quarter":
                start = timezone.now() - timedelta(days=90 * (i + 1))
                end = timezone.now() - timedelta(days=90 * i)
            elif period == "year":
                start = timezone.now() - timedelta(days=365 * (i + 1))
                end = timezone.now() - timedelta(days=365 * i)
            
            periods.append((start, end))
        
        # Analyze each period
        revenue_analysis = []
        for start, end in periods:
            revenue = Transaction.objects.filter(
                merchant=merchant,
                transaction_type="INCOME",
                transaction_date__gte=start,
                transaction_date__lte=end,
                status="COMPLETED"
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            transaction_count = Transaction.objects.filter(
                merchant=merchant,
                transaction_type="INCOME",
                transaction_date__gte=start,
                transaction_date__lte=end,
                status="COMPLETED"
            ).count()
            
            revenue_analysis.append({
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "revenue": float(revenue),
                "transaction_count": transaction_count,
                "average_transaction": float(revenue / transaction_count) if transaction_count > 0 else 0
            })
        
        # Calculate trends
        if len(revenue_analysis) >= 2:
            current_revenue = revenue_analysis[0]["revenue"]
            previous_revenue = revenue_analysis[1]["revenue"]
            growth_rate = ((current_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0
        else:
            growth_rate = 0
        
        return {
            "revenue_analysis": revenue_analysis,
            "growth_rate": growth_rate,
            "period": period,
            "comparison_periods": comparison_periods,
            "generated_at": timezone.now().isoformat()
        }
    
    async def _analyze_expenses(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze expense patterns and categories"""
        merchant_id = args["merchant_id"]
        period = args["period"]
        top_categories = args.get("top_categories", 10)
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Calculate date range
        if period == "month":
            start_date = timezone.now() - timedelta(days=30)
        elif period == "quarter":
            start_date = timezone.now() - timedelta(days=90)
        elif period == "year":
            start_date = timezone.now() - timedelta(days=365)
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        # Get expense breakdown by category
        expenses = Transaction.objects.filter(
            merchant=merchant,
            transaction_type="EXPENSE",
            transaction_date__gte=start_date,
            status="COMPLETED"
        )
        
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        category_breakdown = expenses.values('category__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')[:top_categories]
        
        expense_categories = []
        for item in category_breakdown:
            if item["category__name"]:
                percentage = (float(item["total"]) / float(total_expenses) * 100) if total_expenses > 0 else 0
                expense_categories.append({
                    "category": item["category__name"],
                    "amount": float(item["total"]),
                    "count": item["count"],
                    "percentage": percentage
                })
        
        return {
            "expense_analysis": {
                "period": period,
                "total_expenses": float(total_expenses),
                "transaction_count": expenses.count(),
                "category_breakdown": expense_categories
            },
            "generated_at": timezone.now().isoformat()
        }
    
    async def _analyze_cash_flow(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze cash flow patterns and projections"""
        merchant_id = args["merchant_id"]
        period_months = args.get("period_months", 6)
        include_projection = args.get("include_projection", True)
        
        try:
            merchant = User.objects.get(id=merchant_id)
        except User.DoesNotExist:
            raise MCPAuthenticationError(f"Merchant {merchant_id} not found")
        
        # Calculate monthly cash flow for the specified period
        cash_flow_data = []
        for i in range(period_months):
            month_start = timezone.now() - timedelta(days=30 * (i + 1))
            month_end = timezone.now() - timedelta(days=30 * i)
            
            monthly_income = Transaction.objects.filter(
                merchant=merchant,
                transaction_type="INCOME",
                transaction_date__gte=month_start,
                transaction_date__lte=month_end,
                status="COMPLETED"
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            monthly_expenses = Transaction.objects.filter(
                merchant=merchant,
                transaction_type="EXPENSE",
                transaction_date__gte=month_start,
                transaction_date__lte=month_end,
                status="COMPLETED"
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            cash_flow_data.append({
                "month": month_start.strftime("%Y-%m"),
                "income": float(monthly_income),
                "expenses": float(monthly_expenses),
                "net_cash_flow": float(monthly_income - monthly_expenses)
            })
        
        # Calculate averages for projection
        avg_income = sum(item["income"] for item in cash_flow_data) / len(cash_flow_data)
        avg_expenses = sum(item["expenses"] for item in cash_flow_data) / len(cash_flow_data)
        avg_net_flow = avg_income - avg_expenses
        
        projection = None
        if include_projection:
            projection = {
                "next_month_projected_income": avg_income,
                "next_month_projected_expenses": avg_expenses,
                "next_month_projected_net": avg_net_flow,
                "confidence_level": "Based on historical average"
            }
        
        return {
            "cash_flow_analysis": {
                "period_months": period_months,
                "monthly_data": cash_flow_data,
                "averages": {
                    "monthly_income": avg_income,
                    "monthly_expenses": avg_expenses,
                    "monthly_net_flow": avg_net_flow
                }
            },
            "projection": projection,
            "generated_at": timezone.now().isoformat()
        }
    
    async def _manage_categories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Manage transaction categories"""
        action = args["action"]
        
        if action == "list":
            categories = Category.objects.all().order_by("category_type", "name")
            category_list = []
            for category in categories:
                category_list.append({
                    "id": category.id,
                    "name": category.name,
                    "type": category.category_type,
                    "description": category.description,
                    "created_at": category.created_at.isoformat()
                })
            
            return {
                "categories": category_list,
                "total_count": len(category_list)
            }
        
        elif action == "create":
            name = args.get("name")
            category_type = args.get("category_type", "EXPENSE")
            description = args.get("description", "")
            
            if not name:
                raise MCPValidationError("Category name is required")
            
            category = Category.objects.create(
                name=name,
                category_type=category_type,
                description=description
            )
            
            return {
                "created_category": {
                    "id": category.id,
                    "name": category.name,
                    "type": category.category_type,
                    "description": category.description
                }
            }
        
        elif action == "update":
            category_id = args.get("category_id")
            if not category_id:
                raise MCPValidationError("Category ID is required for updates")
            
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                raise MCPServerError(f"Category {category_id} not found")
            
            if "name" in args:
                category.name = args["name"]
            if "description" in args:
                category.description = args["description"]
            
            category.save()
            
            return {
                "updated_category": {
                    "id": category.id,
                    "name": category.name,
                    "type": category.category_type,
                    "description": category.description
                }
            }
        
        else:
            raise MCPValidationError(f"Unknown action: {action}")


# Server instance for running
financial_db_adapter = FinancialDBAdapter()


if __name__ == "__main__":
    import asyncio
    import json
    
    async def main():
        # Example usage
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "generate_summary",
                "arguments": {
                    "merchant_id": 1,
                    "timeframe": "month",
                    "include_categories": True
                }
            },
            "id": 1
        }
        
        response = await financial_db_adapter.handle_request(request)
        print(json.dumps(response.data, indent=2, default=str))
    
    asyncio.run(main())
