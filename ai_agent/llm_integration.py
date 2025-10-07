"""
LLM Integration Layer for the Merchant Financial Agent

Implements the LLM core with MCP Host/Client functionality for conversational
AI agent capabilities. Handles natural language processing, context management,
and response generation.
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import os

from .function_calling import function_calling_engine, FunctionCallingError
from ..mcp_servers.mcp_orchestrator import mcp_orchestrator

logger = logging.getLogger(__name__)


class LLMProvider:
    """Base class for LLM providers"""
    
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
    
    async def generate_response(self, messages: List[Dict[str, str]], 
                              tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate response from LLM"""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider implementation"""
    
    def __init__(self, api_key: str, model_name: str = "gpt-4"):
        super().__init__(api_key, model_name)
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
    
    async def generate_response(self, messages: List[Dict[str, str]], 
                              tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate response using OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                temperature=0.7,
                max_tokens=1000
            )
            
            return {
                "content": response.choices[0].message.content,
                "tool_calls": response.choices[0].message.tool_calls,
                "usage": response.usage,
                "model": response.model
            }
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class LocalMockProvider(LLMProvider):
    """Local mock LLM provider for development without external API keys"""
    def __init__(self, api_key: str = "", model_name: str = "local-mock"):
        super().__init__(api_key, model_name)
    async def generate_response(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), {"content": ""})
        content = f"(Mocked) I received your message: '{last_user.get('content','')}'."
        return {"content": content, "tool_calls": None, "usage": {}, "model": self.model_name}

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation"""
    
    def __init__(self, api_key: str, model_name: str = "claude-3-sonnet-20240229"):
        super().__init__(api_key, model_name)
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError:
            raise ImportError("Anthropic package not installed. Install with: pip install anthropic")
    
    async def generate_response(self, messages: List[Dict[str, str]], 
                              tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate response using Anthropic API"""
        try:
            # Convert messages to Anthropic format
            system_message = None
            user_messages = []
            
            for message in messages:
                if message["role"] == "system":
                    system_message = message["content"]
                else:
                    user_messages.append(message)
            
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=1000,
                system=system_message,
                messages=user_messages,
                tools=tools
            )
            
            return {
                "content": response.content[0].text if response.content else None,
                "tool_calls": response.tool_calls,
                "usage": response.usage,
                "model": response.model
            }
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class ConversationContext:
    """Manages conversation context and history"""
    
    def __init__(self, merchant_id: int, max_history: int = 10):
        self.merchant_id = merchant_id
        self.max_history = max_history
        self.messages = []
        self.tool_results = {}
        self.session_start = datetime.now()
    
    def add_message(self, role: str, content: str, tool_calls: Optional[List[Dict]] = None):
        """Add a message to the conversation history"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        self.messages.append(message)
        
        # Trim history if too long
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
    
    def add_tool_result(self, tool_call_id: str, result: Dict[str, Any]):
        """Add tool execution result"""
        self.tool_results[tool_call_id] = result
    
    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """Get messages in format suitable for LLM"""
        llm_messages = []
        
        for message in self.messages:
            llm_message = {
                "role": message["role"],
                "content": message["content"]
            }
            
            if "tool_calls" in message:
                llm_message["tool_calls"] = message["tool_calls"]
            
            llm_messages.append(llm_message)
        
        return llm_messages
    
    def get_context_summary(self) -> str:
        """Get a summary of the conversation context"""
        summary = f"Conversation started at {self.session_start.isoformat()}\n"
        summary += f"Total messages: {len(self.messages)}\n"
        summary += f"Tool executions: {len(self.tool_results)}\n"
        
        if self.messages:
            last_message = self.messages[-1]
            summary += f"Last message: {last_message['role']} - {last_message['content'][:100]}...\n"
        
        return summary


class MerchantFinancialAgent:
    """
    Main Merchant Financial Agent class
    
    Implements the conversational AI agent with MCP Host/Client functionality,
    Function Calling, and context-aware responses for financial operations.
    """
    
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None, 
                 model_name: Optional[str] = None):
        self.provider_name = provider
        self.api_key = api_key or self._get_api_key()
        self.model_name = model_name or self._get_default_model()
        
        # Initialize LLM provider
        self.llm_provider = self._initialize_provider()
        
        # Initialize conversation contexts
        self.conversations = {}
        
        # System prompt for the agent
        self.system_prompt = self._get_system_prompt()
        
        logger.info(f"Merchant Financial Agent initialized with {provider}")
    
    def _get_api_key(self) -> str:
        """Get API key from environment variables"""
        if self.provider_name == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        elif self.provider_name == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY", "")
        return ""
    
    def _get_default_model(self) -> str:
        """Get default model name for provider"""
        if self.provider_name == "openai":
            return "gpt-4"
        elif self.provider_name == "anthropic":
            return "claude-3-sonnet-20240229"
        return "gpt-4"
    
    def _initialize_provider(self) -> LLMProvider:
        """Initialize the LLM provider"""
        if self.provider_name == "openai" and self.api_key:
            return OpenAIProvider(self.api_key, self.model_name)
        elif self.provider_name == "anthropic" and self.api_key:
            return AnthropicProvider(self.api_key, self.model_name)
        # Fallback to local mock if no API key available
        logger.warning("No valid API key found for provider; using LocalMockProvider for development.")
        return LocalMockProvider()
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent"""
        return """You are the Merchant Financial Agent, an AI assistant specialized in helping small-to-medium business owners manage their finances, schedule events, and analyze their business performance.

Your capabilities include:
1. Financial Reporting: Generate summaries, analyze revenue and expenses, track cash flow
2. Calendar Management: Schedule meetings, create reminders, manage deadlines
3. Currency Conversion: Convert between different currencies using real-time rates
4. Business Analysis: Provide insights on financial trends and patterns

Guidelines:
- Always be professional and helpful
- Provide clear, actionable insights
- When creating calendar events, consider the business context
- For financial reports, explain the key findings and implications
- If you need to execute multiple operations, do them in logical sequence
- Always confirm important actions like creating events or making changes

You have access to various tools through Function Calling. Use them to provide accurate, real-time information and perform actions on behalf of the merchant.

Remember: You are working with sensitive financial data, so always be precise and careful with your responses."""
    
    def get_conversation_context(self, merchant_id: int) -> ConversationContext:
        """Get or create conversation context for merchant"""
        if merchant_id not in self.conversations:
            self.conversations[merchant_id] = ConversationContext(merchant_id)
        return self.conversations[merchant_id]
    
    async def process_message(self, merchant_id: int, user_input: str) -> Dict[str, Any]:
        """
        Process a user message and generate response
        
        Args:
            merchant_id: Merchant user ID
            user_input: User's natural language input
            
        Returns:
            Response dictionary with content and any executed actions
        """
        try:
            context = self.get_conversation_context(merchant_id)
            
            # Add user message to context
            context.add_message("user", user_input)
            
            # Parse intent using Function Calling
            intent_result = function_calling_engine.parse_intent(user_input, merchant_id)
            
            # Get available tools
            available_tools = function_calling_engine.get_available_tools()
            
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": self.system_prompt},
                *context.get_messages_for_llm()
            ]
            
            # Generate LLM response with tool calling capability
            llm_response = await self.llm_provider.generate_response(
                messages=messages,
                tools=available_tools
            )
            
            # Process tool calls if any
            tool_results = []
            if llm_response.get("tool_calls"):
                for tool_call in llm_response["tool_calls"]:
                    result = await self._execute_tool_call(tool_call, merchant_id)
                    tool_results.append(result)
                    
                    # Add tool result to context
                    context.add_tool_result(tool_call.id, result)
            
            # Generate final response
            final_response = await self._generate_final_response(
                context, llm_response, tool_results, user_input
            )
            
            # Add assistant response to context
            context.add_message("assistant", final_response["content"])
            
            return {
                "content": final_response["content"],
                "tool_results": tool_results,
                "intent": intent_result,
                "conversation_id": merchant_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "content": f"I apologize, but I encountered an error while processing your request: {str(e)}",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _execute_tool_call(self, tool_call: Dict[str, Any], merchant_id: int) -> Dict[str, Any]:
        """Execute a tool call using the MCP orchestrator"""
        try:
            tool_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])
            
            # Add merchant_id to arguments if not present
            if "merchant_id" not in arguments:
                arguments["merchant_id"] = merchant_id
            
            # Execute tool through MCP orchestrator
            result = await mcp_orchestrator.execute_tool(tool_name, arguments, merchant_id)
            
            return {
                "tool_call_id": tool_call["id"],
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "success": True,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "tool_call_id": tool_call.get("id", "unknown"),
                "tool_name": tool_call.get("function", {}).get("name", "unknown"),
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _generate_final_response(self, context: ConversationContext, 
                                     llm_response: Dict[str, Any], 
                                     tool_results: List[Dict[str, Any]], 
                                     user_input: str) -> Dict[str, Any]:
        """Generate the final response to the user"""
        
        # If there were tool calls, incorporate the results
        if tool_results:
            # Check if all tool calls were successful
            successful_results = [r for r in tool_results if r.get("success")]
            failed_results = [r for r in tool_results if not r.get("success")]
            
            if failed_results:
                content = "I encountered some issues while processing your request:\n\n"
                for result in failed_results:
                    content += f"- {result['tool_name']}: {result.get('error', 'Unknown error')}\n"
                content += "\nPlease try rephrasing your request or contact support if the issue persists."
            else:
                # Generate response incorporating tool results
                content = await self._incorporate_tool_results(llm_response, successful_results)
        else:
            # Use LLM response directly
            content = llm_response.get("content", "I'm sorry, I couldn't generate a response.")
        
        return {"content": content}
    
    async def _incorporate_tool_results(self, llm_response: Dict[str, Any], 
                                      tool_results: List[Dict[str, Any]]) -> str:
        """Incorporate tool execution results into the response"""
        
        # For now, create a simple response incorporating the results
        # In a more sophisticated implementation, this would use the LLM to generate
        # a natural language response based on the tool results
        
        response_parts = []
        
        if llm_response.get("content"):
            response_parts.append(llm_response["content"])
        
        for result in tool_results:
            tool_name = result["tool_name"]
            tool_result = result["result"]
            
            if tool_name == "generate_summary":
                summary = tool_result.get("summary", {})
                response_parts.append(f"Here's your financial summary:\n")
                response_parts.append(f"• Total Income: ${summary.get('total_income', 0):,.2f}")
                response_parts.append(f"• Total Expenses: ${summary.get('total_expenses', 0):,.2f}")
                response_parts.append(f"• Net Balance: ${summary.get('net_balance', 0):,.2f}")
            
            elif tool_name == "convert_currency":
                conversion = tool_result.get("conversion", {})
                response_parts.append(f"Currency Conversion Result:")
                response_parts.append(f"{conversion.get('original_amount', 0)} {conversion.get('from_currency', '')} = {conversion.get('converted_amount', 0):,.2f} {conversion.get('to_currency', '')}")
            
            elif tool_name == "calendar_create_event":
                event = tool_result.get("event_created", {})
                response_parts.append(f"Event created successfully:")
                response_parts.append(f"• Title: {event.get('title', 'N/A')}")
                response_parts.append(f"• Date: {event.get('start_datetime', 'N/A')}")
                if event.get('meet_link'):
                    response_parts.append(f"• Meeting Link: {event['meet_link']}")
        
        return "\n\n".join(response_parts)
    
    async def get_conversation_history(self, merchant_id: int) -> List[Dict[str, Any]]:
        """Get conversation history for a merchant"""
        context = self.get_conversation_context(merchant_id)
        return context.messages
    
    async def clear_conversation(self, merchant_id: int):
        """Clear conversation history for a merchant"""
        if merchant_id in self.conversations:
            del self.conversations[merchant_id]
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the agent"""
        try:
            # Test LLM provider
            test_messages = [{"role": "user", "content": "Hello"}]
            llm_response = await self.llm_provider.generate_response(test_messages)
            
            # Test MCP orchestrator
            orchestrator_status = mcp_orchestrator.get_server_status()
            
            return {
                "status": "healthy",
                "llm_provider": {
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "status": "online"
                },
                "mcp_orchestrator": orchestrator_status,
                "function_calling": {
                    "tools_available": len(function_calling_engine.get_available_tools()),
                    "status": "online"
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global agent instance
def create_agent(provider: str = "openai", api_key: Optional[str] = None, 
                model_name: Optional[str] = None) -> MerchantFinancialAgent:
    """Create a new Merchant Financial Agent instance"""
    # Auto-select provider if not specified explicitly
    if provider == "openai" and not os.getenv("OPENAI_API_KEY") and os.getenv("HUGGINGFACE_API_TOKEN"):
        provider = "huggingface"
    env_provider = os.getenv("LLM_PROVIDER")
    if env_provider:
        provider = env_provider
    return MerchantFinancialAgent(provider, api_key, model_name)


# Example usage
async def example_conversation():
    """Example conversation with the agent"""
    
    # Create agent (you would need to set your API key)
    agent = create_agent("openai", os.getenv("OPENAI_API_KEY"))
    
    # Example conversation
    messages = [
        "Show me my financial summary for last month",
        "Convert 1000 USD to EUR",
        "Schedule a meeting with my accountant next Tuesday at 2 PM"
    ]
    
    for message in messages:
        print(f"\nUser: {message}")
        
        try:
            response = await agent.process_message(merchant_id=1, user_input=message)
            print(f"Agent: {response['content']}")
            
            if response.get('tool_results'):
                print(f"Tool executions: {len(response['tool_results'])}")
                
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(example_conversation())
