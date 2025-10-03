"""
Base MCP Server Implementation

This module provides the foundational MCP server class that all specialized
servers inherit from, ensuring consistent protocol implementation and security.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import asyncio
from jsonrpc_base import JSONRPC20Request, JSONRPC20Response

logger = logging.getLogger(__name__)


class MCPServerError(Exception):
    """Base exception for MCP server errors"""
    pass


class MCPAuthenticationError(MCPServerError):
    """Authentication/authorization error"""
    pass


class MCPValidationError(MCPServerError):
    """Request validation error"""
    pass


class BaseMCPServer(ABC):
    """
    Base MCP Server class providing common functionality for all MCP servers.
    
    Implements the Model Context Protocol for standardized communication
    with the AI agent core, including security, validation, and error handling.
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools = {}
        self.resources = {}
        self.prompts = {}
        self._initialize_tools()
        logger.info(f"Initialized MCP Server: {name} v{version}")
    
    @abstractmethod
    def _initialize_tools(self):
        """Initialize server-specific tools and their schemas"""
        pass
    
    def get_server_info(self) -> Dict[str, Any]:
        """Return server information following MCP specification"""
        return {
            "name": self.name,
            "version": self.version,
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "prompts": {"listChanged": True}
            }
        }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """Return list of available tools with their schemas"""
        return list(self.tools.values())
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """Return list of available resources"""
        return list(self.resources.values())
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """Return list of available prompts"""
        return list(self.prompts.values())
    
    async def handle_request(self, request: Union[Dict, str]) -> JSONRPC20Response:
        """
        Handle incoming MCP request and route to appropriate handler
        
        Args:
            request: JSON-RPC 2.0 request (dict or JSON string)
            
        Returns:
            JSON-RPC 2.0 response
        """
        try:
            if isinstance(request, str):
                request = json.loads(request)
            
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            logger.debug(f"Handling MCP request: {method}")
            
            # Route to appropriate handler
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                result = await self._handle_tool_call(params)
            elif method == "resources/list":
                result = {"resources": self.list_resources()}
            elif method == "resources/read":
                result = await self._handle_resource_read(params)
            elif method == "prompts/list":
                result = {"prompts": self.list_prompts()}
            elif method == "prompts/get":
                result = await self._handle_prompt_get(params)
            else:
                raise MCPServerError(f"Unknown method: {method}")
            
            return JSONRPC20Response(result=result, _id=request_id)
            
        except MCPServerError as e:
            logger.error(f"MCP Server Error: {e}")
            return JSONRPC20Response(error={
                "code": -32603,
                "message": str(e),
                "data": {"server": self.name}
            }, _id=request_id)
        except Exception as e:
            logger.error(f"Unexpected error in MCP server {self.name}: {e}")
            return JSONRPC20Response(error={
                "code": -32603,
                "message": "Internal server error",
                "data": {"server": self.name, "error": str(e)}
            }, _id=request_id)
    
    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "prompts": {"listChanged": True}
            },
            "serverInfo": self.get_server_info()
        }
    
    async def _handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            raise MCPValidationError(f"Unknown tool: {tool_name}")
        
        # Validate arguments against tool schema
        self._validate_tool_arguments(tool_name, arguments)
        
        # Execute tool
        result = await self._execute_tool(tool_name, arguments)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, default=str)
                }
            ]
        }
    
    def _validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        """Validate tool arguments against schema"""
        tool_schema = self.tools[tool_name]["inputSchema"]
        required_properties = tool_schema.get("properties", {})
        required_fields = tool_schema.get("required", [])
        
        # Check required fields
        for field in required_fields:
            if field not in arguments:
                raise MCPValidationError(f"Missing required argument: {field}")
        
        # Validate field types and constraints
        for field, value in arguments.items():
            if field in required_properties:
                field_schema = required_properties[field]
                self._validate_field_value(field, value, field_schema)
    
    def _validate_field_value(self, field_name: str, value: Any, schema: Dict[str, Any]):
        """Validate individual field value against schema"""
        expected_type = schema.get("type")
        
        if expected_type == "string" and not isinstance(value, str):
            raise MCPValidationError(f"Field {field_name} must be a string")
        elif expected_type == "number" and not isinstance(value, (int, float)):
            raise MCPValidationError(f"Field {field_name} must be a number")
        elif expected_type == "boolean" and not isinstance(value, bool):
            raise MCPValidationError(f"Field {field_name} must be a boolean")
        elif expected_type == "array" and not isinstance(value, list):
            raise MCPValidationError(f"Field {field_name} must be an array")
        elif expected_type == "object" and not isinstance(value, dict):
            raise MCPValidationError(f"Field {field_name} must be an object")
    
    @abstractmethod
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the specified tool with given arguments"""
        pass
    
    async def _handle_resource_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resource read request"""
        uri = params.get("uri")
        
        if uri not in self.resources:
            raise MCPValidationError(f"Unknown resource: {uri}")
        
        # Implementation depends on specific server
        return {"contents": []}
    
    async def _handle_prompt_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompt get request"""
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if name not in self.prompts:
            raise MCPValidationError(f"Unknown prompt: {name}")
        
        # Implementation depends on specific server
        return {"messages": []}
    
    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any]):
        """Register a tool with the server"""
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema
        }
        logger.debug(f"Registered tool: {name}")
    
    def register_resource(self, uri: str, name: str, description: str, mime_type: str = "text/plain"):
        """Register a resource with the server"""
        self.resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "mimeType": mime_type
        }
        logger.debug(f"Registered resource: {uri}")
    
    def register_prompt(self, name: str, description: str, arguments_schema: Dict[str, Any]):
        """Register a prompt with the server"""
        self.prompts[name] = {
            "name": name,
            "description": description,
            "arguments": arguments_schema
        }
        logger.debug(f"Registered prompt: {name}")
