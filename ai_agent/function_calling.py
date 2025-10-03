"""
Function Calling Layer for the Merchant Financial Agent

Implements the Function Calling (FC) layer that translates natural language
requests into structured JSON commands for reliable execution by MCP servers.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class FunctionCallingError(Exception):
    """Base exception for Function Calling errors"""
    pass


class IntentParsingError(FunctionCallingError):
    """Error in parsing user intent"""
    pass


class ToolSchema:
    """
    Represents a tool schema for Function Calling
    
    Defines the structure and validation rules for tool parameters
    """
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._validate_schema()
    
    def _validate_schema(self):
        """Validate the tool schema structure"""
        if not isinstance(self.parameters, dict):
            raise ValueError("Parameters must be a dictionary")
        
        if "type" not in self.parameters:
            raise ValueError("Parameters must have a 'type' field")
        
        if self.parameters["type"] != "object":
            raise ValueError("Parameters type must be 'object'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to dictionary format"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> bool:
        """Validate arguments against the schema"""
        try:
            properties = self.parameters.get("properties", {})
            required = self.parameters.get("required", [])
            
            # Check required fields
            for field in required:
                if field not in arguments:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate field types
            for field, value in arguments.items():
                if field in properties:
                    self._validate_field(field, value, properties[field])
            
            return True
        except Exception as e:
            logger.error(f"Validation error for {self.name}: {e}")
            return False
    
    def _validate_field(self, field_name: str, value: Any, field_schema: Dict[str, Any]):
        """Validate individual field against its schema"""
        expected_type = field_schema.get("type")
        
        if expected_type == "string" and not isinstance(value, str):
            raise ValueError(f"Field {field_name} must be a string")
        elif expected_type == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"Field {field_name} must be a number")
        elif expected_type == "boolean" and not isinstance(value, bool):
            raise ValueError(f"Field {field_name} must be a boolean")
        elif expected_type == "array" and not isinstance(value, list):
            raise ValueError(f"Field {field_name} must be an array")
        elif expected_type == "object" and not isinstance(value, dict):
            raise ValueError(f"Field {field_name} must be an object")
        
        # Validate enum values
        if "enum" in field_schema and value not in field_schema["enum"]:
            raise ValueError(f"Field {field_name} must be one of: {field_schema['enum']}")
        
        # Validate string patterns
        if expected_type == "string" and "pattern" in field_schema:
            import re
            if not re.match(field_schema["pattern"], str(value)):
                raise ValueError(f"Field {field_name} does not match required pattern")


class FunctionCallingEngine:
    """
    Function Calling Engine for the Merchant Financial Agent
    
    Handles intent parsing, tool selection, and argument extraction
    from natural language requests.
    """
    
    def __init__(self):
        self.tools = {}
        self.intent_patterns = {}
        self._initialize_tools()
        self._initialize_intent_patterns()
        logger.info("Function Calling Engine initialized with {} tools".format(len(self.tools)))
    
    def _initialize_tools(self):
        """Initialize available tools and their schemas"""
        
        # Financial Database Tools
        self.register_tool(ToolSchema(
            name="generate_summary",
            description="Generate financial summary reports for a specific timeframe",
            parameters={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "timeframe": {"type": "string", "enum": ["week", "month", "quarter", "year", "custom"], 
                                "description": "Time period for the report"},
                    "start_date": {"type": "string", "format": "date", "description": "Custom start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "format": "date", "description": "Custom end date (YYYY-MM-DD)"},
                    "include_categories": {"type": "boolean", "default": True, "description": "Include category breakdown"},
                    "include_breakdown": {"type": "boolean", "default": False, "description": "Include detailed breakdown"}
                },
                "required": ["merchant_id", "timeframe"]
            }
        ))
        
        self.register_tool(ToolSchema(
            name="analyze_revenue",
            description="Analyze revenue trends and patterns over time",
            parameters={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "period": {"type": "string", "enum": ["month", "quarter", "year"], 
                             "description": "Analysis period"},
                    "comparison_periods": {"type": "integer", "minimum": 1, "maximum": 12, "default": 3,
                                         "description": "Number of periods to compare"},
                    "include_forecasting": {"type": "boolean", "default": False, "description": "Include forecasting"}
                },
                "required": ["merchant_id", "period"]
            }
        ))
        
        self.register_tool(ToolSchema(
            name="analyze_expenses",
            description="Analyze expense patterns and categories",
            parameters={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "period": {"type": "string", "enum": ["month", "quarter", "year"], 
                             "description": "Analysis period"},
                    "top_categories": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10,
                                     "description": "Number of top categories to show"},
                    "include_trends": {"type": "boolean", "default": True, "description": "Include trend analysis"}
                },
                "required": ["merchant_id", "period"]
            }
        ))
        
        # Calendar Tools
        self.register_tool(ToolSchema(
            name="calendar_create_event",
            description="Create a new calendar event with optional Google Meet link",
            parameters={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "title": {"type": "string", "description": "Event title"},
                    "description": {"type": "string", "description": "Event description"},
                    "start_datetime": {"type": "string", "format": "date-time", "description": "Start datetime (ISO format)"},
                    "end_datetime": {"type": "string", "format": "date-time", "description": "End datetime (ISO format)"},
                    "attendees": {"type": "array", "items": {"type": "string", "format": "email"}, 
                                "description": "Attendee email addresses"},
                    "is_meeting": {"type": "boolean", "default": False, "description": "Generate Google Meet link"},
                    "deadline_type": {"type": "string", "enum": ["TAX_PAYMENT", "INVOICE_DUE", "LOAN_REPAYMENT", 
                                                               "MEETING", "REMINDER", "OTHER"], "default": "OTHER"},
                    "amount": {"type": "number", "description": "Associated amount if applicable"},
                    "reminder_minutes": {"type": "integer", "default": 15, "description": "Reminder time in minutes"}
                },
                "required": ["merchant_id", "title", "start_datetime", "end_datetime"]
            }
        ))
        
        self.register_tool(ToolSchema(
            name="calendar_find_events",
            description="Find calendar events with filters",
            parameters={
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "description": "Merchant user ID"},
                    "start_date": {"type": "string", "format": "date", "description": "Start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "format": "date", "description": "End date (YYYY-MM-DD)"},
                    "query": {"type": "string", "description": "Search query for event titles/descriptions"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 250, "default": 10,
                                  "description": "Maximum number of results"}
                },
                "required": ["merchant_id"]
            }
        ))
        
        # Currency Tools
        self.register_tool(ToolSchema(
            name="convert_currency",
            description="Convert amount from one currency to another",
            parameters={
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "minimum": 0, "description": "Amount to convert"},
                    "from_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Source currency code"},
                    "to_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Target currency code"},
                    "force_refresh": {"type": "boolean", "default": False, "description": "Force refresh rate from API"}
                },
                "required": ["amount", "from_currency", "to_currency"]
            }
        ))
        
        self.register_tool(ToolSchema(
            name="get_live_fx_rate",
            description="Get real-time foreign exchange rate between two currencies",
            parameters={
                "type": "object",
                "properties": {
                    "base_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Base currency code"},
                    "target_currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Target currency code"},
                    "amount": {"type": "number", "minimum": 0, "description": "Amount to convert (optional)"},
                    "force_refresh": {"type": "boolean", "default": False, "description": "Force refresh from API"}
                },
                "required": ["base_currency", "target_currency"]
            }
        ))
    
    def _initialize_intent_patterns(self):
        """Initialize intent recognition patterns"""
        self.intent_patterns = {
            "financial_report": [
                "show me", "generate", "create", "get", "fetch", "display", "report", "summary",
                "revenue", "expense", "profit", "loss", "income", "spending", "financial"
            ],
            "calendar_event": [
                "schedule", "create", "add", "book", "plan", "meeting", "appointment", "event",
                "reminder", "deadline", "calendar", "agenda"
            ],
            "currency_conversion": [
                "convert", "exchange", "rate", "currency", "dollar", "euro", "pound", "yen",
                "worth", "equivalent", "translate"
            ],
            "analysis": [
                "analyze", "analysis", "trend", "pattern", "comparison", "compare", "growth",
                "forecast", "prediction", "insight"
            ]
        }
    
    def register_tool(self, tool_schema: ToolSchema):
        """Register a new tool schema"""
        self.tools[tool_schema.name] = tool_schema
        logger.debug(f"Registered tool: {tool_schema.name}")
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools"""
        return [tool.to_dict() for tool in self.tools.values()]
    
    def parse_intent(self, user_input: str, merchant_id: int) -> Dict[str, Any]:
        """
        Parse user input and determine intent and required tools
        
        Args:
            user_input: Natural language input from user
            merchant_id: Merchant user ID for context
            
        Returns:
            Dictionary containing parsed intent and tool calls
        """
        try:
            user_input_lower = user_input.lower()
            
            # Determine primary intent
            intent_type = self._classify_intent(user_input_lower)
            
            # Extract entities and parameters
            entities = self._extract_entities(user_input)
            
            # Generate tool calls based on intent
            tool_calls = self._generate_tool_calls(intent_type, entities, merchant_id, user_input)
            
            return {
                "intent_type": intent_type,
                "entities": entities,
                "tool_calls": tool_calls,
                "confidence": self._calculate_confidence(intent_type, entities, user_input),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Intent parsing error: {e}")
            raise IntentParsingError(f"Failed to parse intent: {str(e)}")
    
    def _classify_intent(self, user_input: str) -> str:
        """Classify the primary intent from user input"""
        intent_scores = {}
        
        for intent_type, patterns in self.intent_patterns.items():
            score = sum(1 for pattern in patterns if pattern in user_input)
            if score > 0:
                intent_scores[intent_type] = score
        
        if not intent_scores:
            return "general_query"
        
        return max(intent_scores, key=intent_scores.get)
    
    def _extract_entities(self, user_input: str) -> Dict[str, Any]:
        """Extract entities and parameters from user input"""
        import re
        
        entities = {}
        
        # Extract dates
        date_patterns = [
            r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD
            r"(today|yesterday|tomorrow)",
            r"(this week|last week|next week)",
            r"(this month|last month|next month)",
            r"(this quarter|last quarter|next quarter)",
            r"(this year|last year|next year)"
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            if matches:
                entities["dates"] = matches
        
        # Extract amounts
        amount_pattern = r"(\$?\d+(?:,\d{3})*(?:\.\d{2})?)"
        amounts = re.findall(amount_pattern, user_input)
        if amounts:
            entities["amounts"] = amounts
        
        # Extract currency codes
        currency_pattern = r"\b([A-Z]{3})\b"
        currencies = re.findall(currency_pattern, user_input)
        if currencies:
            entities["currencies"] = currencies
        
        # Extract timeframes
        timeframe_patterns = [
            r"(week|month|quarter|year|day)",
            r"(weekly|monthly|quarterly|yearly|daily)"
        ]
        
        for pattern in timeframe_patterns:
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            if matches:
                entities["timeframes"] = matches
        
        return entities
    
    def _generate_tool_calls(self, intent_type: str, entities: Dict[str, Any], 
                           merchant_id: int, user_input: str) -> List[Dict[str, Any]]:
        """Generate tool calls based on intent and entities"""
        tool_calls = []
        
        if intent_type == "financial_report":
            tool_calls.extend(self._generate_financial_report_calls(entities, merchant_id, user_input))
        elif intent_type == "calendar_event":
            tool_calls.extend(self._generate_calendar_calls(entities, merchant_id, user_input))
        elif intent_type == "currency_conversion":
            tool_calls.extend(self._generate_currency_calls(entities, merchant_id, user_input))
        elif intent_type == "analysis":
            tool_calls.extend(self._generate_analysis_calls(entities, merchant_id, user_input))
        
        return tool_calls
    
    def _generate_financial_report_calls(self, entities: Dict[str, Any], 
                                       merchant_id: int, user_input: str) -> List[Dict[str, Any]]:
        """Generate financial report tool calls"""
        tool_calls = []
        
        # Determine timeframe
        timeframe = "month"  # default
        if "timeframes" in entities:
            timeframe_map = {
                "week": "week", "weekly": "week",
                "month": "month", "monthly": "month",
                "quarter": "quarter", "quarterly": "quarter",
                "year": "year", "yearly": "year"
            }
            for tf in entities["timeframes"]:
                if tf.lower() in timeframe_map:
                    timeframe = timeframe_map[tf.lower()]
                    break
        
        # Generate summary call
        tool_calls.append({
            "name": "generate_summary",
            "arguments": {
                "merchant_id": merchant_id,
                "timeframe": timeframe,
                "include_categories": True,
                "include_breakdown": "detailed" in user_input.lower()
            }
        })
        
        return tool_calls
    
    def _generate_calendar_calls(self, entities: Dict[str, Any], 
                               merchant_id: int, user_input: str) -> List[Dict[str, Any]]:
        """Generate calendar tool calls"""
        tool_calls = []
        
        # For now, create a basic event call
        # In a real implementation, this would extract more details from the input
        tool_calls.append({
            "name": "calendar_create_event",
            "arguments": {
                "merchant_id": merchant_id,
                "title": "New Event",  # Would be extracted from input
                "description": "Event created from natural language input",
                "start_datetime": datetime.now().isoformat(),
                "end_datetime": (datetime.now().timestamp() + 3600).isoformat(),  # 1 hour later
                "is_meeting": "meeting" in user_input.lower()
            }
        })
        
        return tool_calls
    
    def _generate_currency_calls(self, entities: Dict[str, Any], 
                               merchant_id: int, user_input: str) -> List[Dict[str, Any]]:
        """Generate currency conversion tool calls"""
        tool_calls = []
        
        if "amounts" in entities and "currencies" in entities and len(entities["currencies"]) >= 2:
            amount = float(entities["amounts"][0].replace("$", "").replace(",", ""))
            from_currency = entities["currencies"][0]
            to_currency = entities["currencies"][1]
            
            tool_calls.append({
                "name": "convert_currency",
                "arguments": {
                    "amount": amount,
                    "from_currency": from_currency,
                    "to_currency": to_currency
                }
            })
        
        return tool_calls
    
    def _generate_analysis_calls(self, entities: Dict[str, Any], 
                               merchant_id: int, user_input: str) -> List[Dict[str, Any]]:
        """Generate analysis tool calls"""
        tool_calls = []
        
        if "revenue" in user_input.lower():
            tool_calls.append({
                "name": "analyze_revenue",
                "arguments": {
                    "merchant_id": merchant_id,
                    "period": "month",
                    "comparison_periods": 3,
                    "include_forecasting": "forecast" in user_input.lower()
                }
            })
        elif "expense" in user_input.lower():
            tool_calls.append({
                "name": "analyze_expenses",
                "arguments": {
                    "merchant_id": merchant_id,
                    "period": "month",
                    "top_categories": 10,
                    "include_trends": True
                }
            })
        
        return tool_calls
    
    def _calculate_confidence(self, intent_type: str, entities: Dict[str, Any], user_input: str) -> float:
        """Calculate confidence score for the parsed intent"""
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on entity extraction
        if entities:
            confidence += 0.2
        
        # Increase confidence based on intent-specific indicators
        if intent_type == "financial_report" and any(word in user_input.lower() for word in ["report", "summary", "show"]):
            confidence += 0.2
        elif intent_type == "calendar_event" and any(word in user_input.lower() for word in ["schedule", "meeting", "event"]):
            confidence += 0.2
        elif intent_type == "currency_conversion" and any(word in user_input.lower() for word in ["convert", "exchange", "rate"]):
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Validate a tool call against its schema"""
        if tool_name not in self.tools:
            return False
        
        return self.tools[tool_name].validate_arguments(arguments)


# Global Function Calling Engine instance
function_calling_engine = FunctionCallingEngine()


# Example usage and testing
def example_intent_parsing():
    """Example of intent parsing functionality"""
    
    test_inputs = [
        "Show me my revenue report for last month",
        "Convert 1000 USD to EUR",
        "Schedule a meeting with my accountant next Tuesday",
        "Analyze my expense trends for the quarter"
    ]
    
    for user_input in test_inputs:
        try:
            result = function_calling_engine.parse_intent(user_input, merchant_id=1)
            print(f"\nInput: {user_input}")
            print(f"Intent: {result['intent_type']}")
            print(f"Confidence: {result['confidence']:.2f}")
            print(f"Tool Calls: {len(result['tool_calls'])}")
            for i, call in enumerate(result['tool_calls']):
                print(f"  {i+1}. {call['name']} - {call['arguments']}")
        except Exception as e:
            print(f"Error parsing '{user_input}': {e}")


if __name__ == "__main__":
    example_intent_parsing()
