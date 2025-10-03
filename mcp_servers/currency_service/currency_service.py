"""
Currency Service MCP Server

Implements real-time foreign exchange rate lookup and currency conversion
for the Merchant Financial Agent with caching and error handling.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
import logging

# Add Django project to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

try:
    import django
    django.setup()
    from django.utils import timezone
    from ecomapp.models import CurrencyRate
except ImportError:
    # Handle case where Django is not available
    pass

from ..base_mcp_server import BaseMCPServer, MCPServerError

logger = logging.getLogger(__name__)

# Currency API configuration
EXCHANGE_RATE_API_URL = "https://api.exchangerate-api.com/v4/latest/"
EXCHANGE_RATES_API_URL = "https://api.exchangeratesapi.io/v1/latest"
CACHE_DURATION_HOURS = 1  # Cache exchange rates for 1 hour


class CurrencyService(BaseMCPServer):
    """
    Currency Service MCP Server
    
    Provides real-time foreign exchange rate lookup and currency conversion
    with intelligent caching and multiple API fallbacks for reliability.
    """
    
    def __init__(self):
        super().__init__("Currency Service", "1.0.0")
        self.api_key = os.getenv('EXCHANGE_RATES_API_KEY', None)
    
    def _initialize_tools(self):
        """Initialize currency service tools"""
        
        # Get Live Exchange Rate Tool
        self.register_tool(
            name="get_live_fx_rate",
            description="Get real-time foreign exchange rate between two currencies",
            input_schema={
                "type": "object",
                "properties": {
                    "base_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Base currency code (e.g., USD)"},
                    "target_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Target currency code (e.g., EUR)"},
                    "amount": {"type": "number", "minimum": 0, "description": "Amount to convert (optional)"},
                    "force_refresh": {"type": "boolean", "default": False, "description": "Force refresh from API"}
                },
                "required": ["base_currency", "target_currency"]
            }
        )
        
        # Convert Currency Tool
        self.register_tool(
            name="convert_currency",
            description="Convert amount from one currency to another",
            input_schema={
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "minimum": 0, "description": "Amount to convert"},
                    "from_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Source currency code"},
                    "to_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Target currency code"},
                    "force_refresh": {"type": "boolean", "default": False, "description": "Force refresh rate from API"}
                },
                "required": ["amount", "from_currency", "to_currency"]
            }
        )
        
        # Get Multiple Rates Tool
        self.register_tool(
            name="get_multiple_rates",
            description="Get exchange rates for multiple currency pairs",
            input_schema={
                "type": "object",
                "properties": {
                    "base_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Base currency code"},
                    "target_currencies": {"type": "array", "items": {"type": "string", "pattern": "^[A-Z]{3}$"}, "description": "List of target currency codes"},
                    "force_refresh": {"type": "boolean", "default": False, "description": "Force refresh from API"}
                },
                "required": ["base_currency", "target_currencies"]
            }
        )
        
        # Get Supported Currencies Tool
        self.register_tool(
            name="get_supported_currencies",
            description="Get list of supported currency codes",
            input_schema={
                "type": "object",
                "properties": {}
            }
        )
        
        # Historical Rate Tool
        self.register_tool(
            name="get_historical_rate",
            description="Get historical exchange rate for a specific date",
            input_schema={
                "type": "object",
                "properties": {
                    "base_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Base currency code"},
                    "target_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Target currency code"},
                    "date": {"type": "string", "format": "date", "description": "Date in YYYY-MM-DD format"},
                    "amount": {"type": "number", "minimum": 0, "description": "Amount to convert (optional)"}
                },
                "required": ["base_currency", "target_currency", "date"]
            }
        )
        
        # Currency Info Tool
        self.register_tool(
            name="get_currency_info",
            description="Get detailed information about a currency",
            input_schema={
                "type": "object",
                "properties": {
                    "currency_code": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Currency code to get info for"}
                },
                "required": ["currency_code"]
            }
        )
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute currency service tools"""
        
        try:
            if tool_name == "get_live_fx_rate":
                return await self._get_live_fx_rate(arguments)
            elif tool_name == "convert_currency":
                return await self._convert_currency(arguments)
            elif tool_name == "get_multiple_rates":
                return await self._get_multiple_rates(arguments)
            elif tool_name == "get_supported_currencies":
                return await self._get_supported_currencies(arguments)
            elif tool_name == "get_historical_rate":
                return await self._get_historical_rate(arguments)
            elif tool_name == "get_currency_info":
                return await self._get_currency_info(arguments)
            else:
                raise MCPServerError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            logger.error(f"Error executing currency tool {tool_name}: {e}")
            raise MCPServerError(f"Currency operation failed: {str(e)}")
    
    async def _get_live_fx_rate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get real-time foreign exchange rate"""
        base_currency = args["base_currency"].upper()
        target_currency = args["target_currency"].upper()
        amount = args.get("amount", 1)
        force_refresh = args.get("force_refresh", False)
        
        # Check cache first
        cached_rate = None
        if not force_refresh:
            cached_rate = self._get_cached_rate(base_currency, target_currency)
        
        if cached_rate:
            converted_amount = amount * cached_rate
            return {
                "exchange_rate": {
                    "base_currency": base_currency,
                    "target_currency": target_currency,
                    "rate": float(cached_rate),
                    "amount": amount,
                    "converted_amount": float(converted_amount),
                    "cached": True,
                    "fetched_at": datetime.now().isoformat()
                }
            }
        
        # Fetch from API
        rate = await self._fetch_exchange_rate(base_currency, target_currency)
        if rate is None:
            raise MCPServerError(f"Could not fetch exchange rate for {base_currency}/{target_currency}")
        
        # Cache the rate
        self._cache_rate(base_currency, target_currency, rate)
        
        converted_amount = amount * rate
        
        return {
            "exchange_rate": {
                "base_currency": base_currency,
                "target_currency": target_currency,
                "rate": float(rate),
                "amount": amount,
                "converted_amount": float(converted_amount),
                "cached": False,
                "fetched_at": datetime.now().isoformat()
            }
        }
    
    async def _convert_currency(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Convert amount from one currency to another"""
        amount = args["amount"]
        from_currency = args["from_currency"].upper()
        to_currency = args["to_currency"].upper()
        force_refresh = args.get("force_refresh", False)
        
        # Get exchange rate
        rate_args = {
            "base_currency": from_currency,
            "target_currency": to_currency,
            "force_refresh": force_refresh
        }
        
        rate_result = await self._get_live_fx_rate(rate_args)
        rate = rate_result["exchange_rate"]["rate"]
        
        converted_amount = amount * rate
        
        return {
            "conversion": {
                "original_amount": amount,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "exchange_rate": rate,
                "converted_amount": float(converted_amount),
                "conversion_timestamp": datetime.now().isoformat()
            }
        }
    
    async def _get_multiple_rates(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get exchange rates for multiple currency pairs"""
        base_currency = args["base_currency"].upper()
        target_currencies = [curr.upper() for curr in args["target_currencies"]]
        force_refresh = args.get("force_refresh", False)
        
        rates = {}
        
        for target_currency in target_currencies:
            try:
                rate_args = {
                    "base_currency": base_currency,
                    "target_currency": target_currency,
                    "force_refresh": force_refresh
                }
                
                rate_result = await self._get_live_fx_rate(rate_args)
                rates[target_currency] = rate_result["exchange_rate"]
                
            except Exception as e:
                logger.warning(f"Could not fetch rate for {base_currency}/{target_currency}: {e}")
                rates[target_currency] = {"error": str(e)}
        
        return {
            "multiple_rates": {
                "base_currency": base_currency,
                "rates": rates,
                "fetched_at": datetime.now().isoformat()
            }
        }
    
    async def _get_supported_currencies(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of supported currency codes"""
        # Common currencies supported by most FX APIs
        supported_currencies = {
            "major_currencies": [
                "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"
            ],
            "emerging_markets": [
                "CNY", "INR", "BRL", "MXN", "KRW", "SGD", "HKD", "NOK", "SEK", "DKK"
            ],
            "african_currencies": [
                "ZAR", "EGP", "NGN", "KES", "GHS", "ETB", "MAD", "TND", "DZD"
            ],
            "middle_eastern": [
                "AED", "SAR", "QAR", "KWD", "BHD", "OMR", "JOD", "ILS", "TRY"
            ],
            "other_currencies": [
                "RUB", "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "RSD", "UAH"
            ]
        }
        
        # Get current rates for major currencies to verify API availability
        api_status = {}
        try:
            rate_args = {
                "base_currency": "USD",
                "target_currency": "EUR",
                "force_refresh": False
            }
            rate_result = await self._get_live_fx_rate(rate_args)
            api_status = {
                "status": "online",
                "last_checked": datetime.now().isoformat(),
                "sample_rate": rate_result["exchange_rate"]["rate"]
            }
        except Exception as e:
            api_status = {
                "status": "offline",
                "last_checked": datetime.now().isoformat(),
                "error": str(e)
            }
        
        return {
            "supported_currencies": supported_currencies,
            "total_count": sum(len(currencies) for currencies in supported_currencies.values()),
            "api_status": api_status
        }
    
    async def _get_historical_rate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get historical exchange rate for a specific date"""
        base_currency = args["base_currency"].upper()
        target_currency = args["target_currency"].upper()
        date = args["date"]
        amount = args.get("amount", 1)
        
        # Validate date (not in the future)
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        if target_date > datetime.now().date():
            raise MCPServerError("Historical rates cannot be fetched for future dates")
        
        # Check if date is too old (most free APIs have limited historical data)
        if target_date < datetime.now().date() - timedelta(days=365):
            raise MCPServerError("Historical data only available for the last 365 days")
        
        # Fetch historical rate
        try:
            url = f"https://api.exchangerate-api.com/v4/history/{base_currency}/{date}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                rate = Decimal(str(data['rates'].get(target_currency, 0)))
                
                if rate == 0:
                    raise MCPServerError(f"No historical rate found for {base_currency}/{target_currency} on {date}")
                
                converted_amount = amount * rate
                
                return {
                    "historical_rate": {
                        "base_currency": base_currency,
                        "target_currency": target_currency,
                        "date": date,
                        "rate": float(rate),
                        "amount": amount,
                        "converted_amount": float(converted_amount),
                        "fetched_at": datetime.now().isoformat()
                    }
                }
            else:
                raise MCPServerError(f"API returned status {response.status_code}")
                
        except requests.RequestException as e:
            raise MCPServerError(f"Failed to fetch historical rate: {str(e)}")
    
    async def _get_currency_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a currency"""
        currency_code = args["currency_code"].upper()
        
        # Currency information database
        currency_info = {
            "USD": {"name": "US Dollar", "symbol": "$", "region": "United States", "decimal_places": 2},
            "EUR": {"name": "Euro", "symbol": "€", "region": "European Union", "decimal_places": 2},
            "GBP": {"name": "British Pound", "symbol": "£", "region": "United Kingdom", "decimal_places": 2},
            "JPY": {"name": "Japanese Yen", "symbol": "¥", "region": "Japan", "decimal_places": 0},
            "CHF": {"name": "Swiss Franc", "symbol": "CHF", "region": "Switzerland", "decimal_places": 2},
            "CAD": {"name": "Canadian Dollar", "symbol": "C$", "region": "Canada", "decimal_places": 2},
            "AUD": {"name": "Australian Dollar", "symbol": "A$", "region": "Australia", "decimal_places": 2},
            "NZD": {"name": "New Zealand Dollar", "symbol": "NZ$", "region": "New Zealand", "decimal_places": 2},
            "CNY": {"name": "Chinese Yuan", "symbol": "¥", "region": "China", "decimal_places": 2},
            "INR": {"name": "Indian Rupee", "symbol": "₹", "region": "India", "decimal_places": 2},
            "BRL": {"name": "Brazilian Real", "symbol": "R$", "region": "Brazil", "decimal_places": 2},
            "MXN": {"name": "Mexican Peso", "symbol": "$", "region": "Mexico", "decimal_places": 2},
            "KRW": {"name": "South Korean Won", "symbol": "₩", "region": "South Korea", "decimal_places": 0},
            "SGD": {"name": "Singapore Dollar", "symbol": "S$", "region": "Singapore", "decimal_places": 2},
            "HKD": {"name": "Hong Kong Dollar", "symbol": "HK$", "region": "Hong Kong", "decimal_places": 2},
            "ZAR": {"name": "South African Rand", "symbol": "R", "region": "South Africa", "decimal_places": 2},
            "EGP": {"name": "Egyptian Pound", "symbol": "£", "region": "Egypt", "decimal_places": 2},
            "NGN": {"name": "Nigerian Naira", "symbol": "₦", "region": "Nigeria", "decimal_places": 2},
            "KES": {"name": "Kenyan Shilling", "symbol": "KSh", "region": "Kenya", "decimal_places": 2},
            "ETB": {"name": "Ethiopian Birr", "symbol": "Br", "region": "Ethiopia", "decimal_places": 2},
            "AED": {"name": "UAE Dirham", "symbol": "د.إ", "region": "United Arab Emirates", "decimal_places": 2},
            "SAR": {"name": "Saudi Riyal", "symbol": "﷼", "region": "Saudi Arabia", "decimal_places": 2},
            "TRY": {"name": "Turkish Lira", "symbol": "₺", "region": "Turkey", "decimal_places": 2},
            "RUB": {"name": "Russian Ruble", "symbol": "₽", "region": "Russia", "decimal_places": 2},
            "PLN": {"name": "Polish Złoty", "symbol": "zł", "region": "Poland", "decimal_places": 2}
        }
        
        if currency_code not in currency_info:
            # Try to get basic info from API
            try:
                rate_args = {
                    "base_currency": "USD",
                    "target_currency": currency_code,
                    "force_refresh": False
                }
                rate_result = await self._get_live_fx_rate(rate_args)
                
                return {
                    "currency_info": {
                        "code": currency_code,
                        "name": f"Currency {currency_code}",
                        "symbol": currency_code,
                        "region": "Unknown",
                        "decimal_places": 2,
                        "current_rate_vs_usd": rate_result["exchange_rate"]["rate"],
                        "info_source": "API"
                    }
                }
            except Exception:
                raise MCPServerError(f"Currency {currency_code} not supported")
        
        info = currency_info[currency_code]
        
        # Get current rate vs USD if possible
        try:
            rate_args = {
                "base_currency": "USD",
                "target_currency": currency_code,
                "force_refresh": False
            }
            rate_result = await self._get_live_fx_rate(rate_args)
            current_rate = rate_result["exchange_rate"]["rate"]
        except Exception:
            current_rate = None
        
        return {
            "currency_info": {
                "code": currency_code,
                "name": info["name"],
                "symbol": info["symbol"],
                "region": info["region"],
                "decimal_places": info["decimal_places"],
                "current_rate_vs_usd": current_rate,
                "info_source": "Database"
            }
        }
    
    def _get_cached_rate(self, base_currency: str, target_currency: str) -> Optional[Decimal]:
        """Get cached exchange rate if available and not expired"""
        try:
            cached_rate = CurrencyRate.objects.filter(
                base_currency=base_currency,
                target_currency=target_currency,
                fetched_at__gte=timezone.now() - timedelta(hours=CACHE_DURATION_HOURS)
            ).first()
            
            return cached_rate.rate if cached_rate else None
        except Exception as e:
            logger.warning(f"Could not access cache: {e}")
            return None
    
    def _cache_rate(self, base_currency: str, target_currency: str, rate: Decimal):
        """Cache exchange rate"""
        try:
            CurrencyRate.objects.update_or_create(
                base_currency=base_currency,
                target_currency=target_currency,
                defaults={'rate': rate}
            )
        except Exception as e:
            logger.warning(f"Could not cache rate: {e}")
    
    async def _fetch_exchange_rate(self, base_currency: str, target_currency: str) -> Optional[Decimal]:
        """Fetch exchange rate from API with fallback"""
        
        # Try primary API
        try:
            url = f"{EXCHANGE_RATE_API_URL}{base_currency}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                rate = Decimal(str(data['rates'].get(target_currency, 0)))
                if rate > 0:
                    return rate
        except Exception as e:
            logger.warning(f"Primary API failed: {e}")
        
        # Try secondary API if available
        if self.api_key:
            try:
                url = f"{EXCHANGE_RATES_API_URL}?access_key={self.api_key}&base={base_currency}&symbols={target_currency}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        rate = Decimal(str(data['rates'].get(target_currency, 0)))
                        if rate > 0:
                            return rate
            except Exception as e:
                logger.warning(f"Secondary API failed: {e}")
        
        return None


# Server instance for running
currency_service = CurrencyService()


if __name__ == "__main__":
    import asyncio
    import json
    
    async def main():
        # Example usage
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "convert_currency",
                "arguments": {
                    "amount": 1000,
                    "from_currency": "USD",
                    "to_currency": "EUR"
                }
            },
            "id": 1
        }
        
        response = await currency_service.handle_request(request)
        print(json.dumps(response.data, indent=2, default=str))
    
    asyncio.run(main())
