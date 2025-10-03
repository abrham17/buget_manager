"""
MCP Orchestrator

Manages multiple MCP servers and provides a unified interface for the
Merchant Financial Agent. Handles server discovery, routing, and coordination
between the FinancialDB Adapter, Google Calendar Server, and Currency Service.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_mcp_server import BaseMCPServer, JSONRPC20Response
from .financial_db_adapter.financial_db_adapter import financial_db_adapter
from .google_calendar_server.calendar_server import calendar_server
from .currency_service.currency_service import currency_service

logger = logging.getLogger(__name__)


class MCPOrchestrator:
    """
    MCP Orchestrator for the Merchant Financial Agent
    
    Coordinates between multiple MCP servers and provides a unified interface
    for the AI agent core. Handles server discovery, request routing, and
    context management across multi-step operations.
    """
    
    def __init__(self):
        self.servers = {
            "financial_db_adapter": financial_db_adapter,
            "google_calendar_server": calendar_server,
            "currency_service": currency_service
        }
        self.server_tools = {}
        self._initialize_server_tools()
        logger.info("MCP Orchestrator initialized with {} servers".format(len(self.servers)))
    
    def _initialize_server_tools(self):
        """Initialize and catalog all available tools from all servers"""
        for server_name, server in self.servers.items():
            tools = server.list_tools()
            self.server_tools[server_name] = {tool["name"]: tool for tool in tools}
            logger.debug(f"Registered {len(tools)} tools from {server_name}")
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools from all servers"""
        all_tools = []
        for server_name, server in self.servers.items():
            tools = server.list_tools()
            for tool in tools:
                tool["server"] = server_name
                all_tools.append(tool)
        return all_tools
    
    def find_tool_server(self, tool_name: str) -> Optional[str]:
        """Find which server provides a specific tool"""
        for server_name, tools in self.server_tools.items():
            if tool_name in tools:
                return server_name
        return None
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], 
                          merchant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a tool on the appropriate server
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            merchant_id: Optional merchant ID for context
            
        Returns:
            Tool execution result
        """
        server_name = self.find_tool_server(tool_name)
        if not server_name:
            raise ValueError(f"Tool '{tool_name}' not found in any server")
        
        # Add merchant_id to arguments if provided
        if merchant_id and "merchant_id" not in arguments:
            arguments["merchant_id"] = merchant_id
        
        server = self.servers[server_name]
        
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
        
        # Execute on server
        response = await server.handle_request(request)
        
        if response.error:
            raise Exception(f"Tool execution failed: {response.error}")
        
        return response.result
    
    async def execute_chained_operations(self, operations: List[Dict[str, Any]], 
                                       merchant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Execute a chain of operations, where each operation can use results from previous ones
        
        Args:
            operations: List of operation dictionaries with 'tool', 'arguments', and 'result_key'
            merchant_id: Optional merchant ID for context
            
        Returns:
            List of operation results
        """
        results = []
        context = {}
        
        for i, operation in enumerate(operations):
            tool_name = operation["tool"]
            arguments = operation.get("arguments", {})
            result_key = operation.get("result_key", f"operation_{i}")
            
            # Inject context from previous operations
            for key, value in context.items():
                if key in arguments:
                    arguments[key] = value
            
            # Execute tool
            try:
                result = await self.execute_tool(tool_name, arguments, merchant_id)
                results.append({
                    "operation": operation,
                    "result": result,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Store result in context for next operations
                context[result_key] = result
                
            except Exception as e:
                logger.error(f"Operation {i} failed: {e}")
                results.append({
                    "operation": operation,
                    "error": str(e),
                    "success": False,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Stop execution on failure (could be configurable)
                break
        
        return results
    
    async def handle_mcp_request(self, request: Dict[str, Any]) -> JSONRPC20Response:
        """
        Handle MCP requests and route to appropriate servers
        
        Args:
            request: MCP request dictionary
            
        Returns:
            MCP response
        """
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = {"tools": self.get_all_tools()}
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = await self.execute_tool(tool_name, arguments)
            elif method == "orchestrator/chained_operations":
                operations = params.get("operations", [])
                merchant_id = params.get("merchant_id")
                results = await self.execute_chained_operations(operations, merchant_id)
                result = {"chained_results": results}
            else:
                raise ValueError(f"Unknown method: {method}")
            
            return JSONRPC20Response(result=result, _id=request_id)
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            return JSONRPC20Response(error={
                "code": -32603,
                "message": str(e),
                "data": {"orchestrator": True}
            }, _id=request_id)
    
    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
                "orchestrator": {"chained_operations": True}
            },
            "serverInfo": {
                "name": "MCP Orchestrator",
                "version": "1.0.0",
                "description": "Orchestrates multiple MCP servers for the Merchant Financial Agent"
            }
        }
    
    def get_server_status(self) -> Dict[str, Any]:
        """Get status of all servers"""
        status = {}
        
        for server_name, server in self.servers.items():
            try:
                # Test server by listing tools
                tools = server.list_tools()
                status[server_name] = {
                    "status": "online",
                    "tool_count": len(tools),
                    "last_checked": datetime.now().isoformat()
                }
            except Exception as e:
                status[server_name] = {
                    "status": "offline",
                    "error": str(e),
                    "last_checked": datetime.now().isoformat()
                }
        
        return {
            "servers": status,
            "total_servers": len(self.servers),
            "online_servers": sum(1 for s in status.values() if s["status"] == "online"),
            "total_tools": sum(len(tools) for tools in self.server_tools.values())
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all servers"""
        health_status = {
            "overall_status": "healthy",
            "servers": {},
            "timestamp": datetime.now().isoformat()
        }
        
        for server_name, server in self.servers.items():
            try:
                # Test basic functionality
                tools = server.list_tools()
                health_status["servers"][server_name] = {
                    "status": "healthy",
                    "tools_available": len(tools),
                    "response_time": "< 1s"
                }
            except Exception as e:
                health_status["servers"][server_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["overall_status"] = "degraded"
        
        return health_status


# Global orchestrator instance
mcp_orchestrator = MCPOrchestrator()


# Example usage and testing
async def example_chained_operations():
    """Example of chained operations using the orchestrator"""
    
    # Example: Get financial summary, convert to different currency, and schedule review meeting
    operations = [
        {
            "tool": "generate_summary",
            "arguments": {
                "merchant_id": 1,
                "timeframe": "month",
                "include_categories": True
            },
            "result_key": "financial_summary"
        },
        {
            "tool": "convert_currency",
            "arguments": {
                "amount": 1000,  # This would be extracted from financial_summary
                "from_currency": "USD",
                "to_currency": "EUR"
            },
            "result_key": "currency_conversion"
        },
        {
            "tool": "calendar_create_event",
            "arguments": {
                "merchant_id": 1,
                "title": "Monthly Financial Review",
                "description": "Review monthly financial summary and currency conversions",
                "start_datetime": "2024-01-15T10:00:00Z",
                "end_datetime": "2024-01-15T11:00:00Z",
                "is_meeting": True
            },
            "result_key": "scheduled_meeting"
        }
    ]
    
    try:
        results = await mcp_orchestrator.execute_chained_operations(operations, merchant_id=1)
        
        print("Chained Operations Results:")
        for i, result in enumerate(results):
            print(f"\nOperation {i + 1}:")
            print(f"Tool: {result['operation']['tool']}")
            print(f"Success: {result['success']}")
            if result['success']:
                print(f"Result: {json.dumps(result['result'], indent=2, default=str)}")
            else:
                print(f"Error: {result['error']}")
                
    except Exception as e:
        print(f"Chained operations failed: {e}")


if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Test orchestrator
        print("MCP Orchestrator Health Check:")
        health = await mcp_orchestrator.health_check()
        print(json.dumps(health, indent=2))
        
        print("\nAll Available Tools:")
        tools = mcp_orchestrator.get_all_tools()
        for tool in tools:
            print(f"- {tool['name']} (from {tool['server']}): {tool['description']}")
        
        print("\nExample Chained Operations:")
        await example_chained_operations()
    
    asyncio.run(main())
