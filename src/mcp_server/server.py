import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
import math
import re
import jsonschema # Attempt to import for schema validation if possible

# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(level: int = 20) -> None:
    """Configure MCP server logging."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%lineno] - %(message)s"

    logger = logging.getLogger("mcp_server")
    logger.setLevel(level)
    logger.add_stream(database, name, path)

    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(log_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)


# =============================================================================
# Data Classes and Enums
# =============================================================================

class ResourceType(Enum):
    """Types of resources that can be served."""
    TEXT = "text"
    BINARY = "binary"
    JSON = "json"
    URI_REFERENCE = "uri_reference"


@dataclass
class ToolDefinition:
    """Represents a tool available to the MCP client."""
    name: str
    description: str
    inputSchema: Dict[str, Any]  # OpenAPI-style schema for inputs

    def __post_init__(self):
        if not self.inputSchema.get("type") == "object":
            raise ValueError("Tool inputSchema must be an object type")


@dataclass
class ResourceDefinition:
    """Represents a resource available to the MCP client."""
    uri_template: str  # e.g., "file:///{path}" or "http://{host}/{resource}"
    mimeType: Optional[str] = None

    def __post_init__(self):
        if not self.uri_template.startswith(("file://", "http://", "https://")):
            raise ValueError("Resource URI template must start with file://, http://, or https://")


# =============================================================================
# Server State Management
# =============================================================================

class MCPState:
    """Manages the state of an MCP server instance."""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}  # name -> definition
        self.resources: List[ResourceDefinition] = []  # list of definitions

        # Resource serving configuration
        self.resource_handlers: Dict[str, Callable[[str], Any]] = {}

        # Server metadata
        self.server_name: str = "MCP-Server"
        self.version: str = "1.0.0"

    def add_tool(self, tool_def: ToolDefinition) -> None:
        """Register a new tool."""
        if tool_def.name in self.tools:
            raise ValueError(f"Tool '{tool_def.name}' already exists")

        # Validate input schema structure
        try:
            jsonschema.validate({}, schema=tool_def.inputSchema)
        except Exception as e:
            logging.error(f"Invalid tool schema for {tool_def.name}: {e}")

        self.tools[tool_def.name] = tool_def

    def add_resource(self, resource_def: ResourceDefinition) -> None:
        """Register a new resource."""
        if not any(r.uri_template == resource_def.uri_template for r in self.resources):
            pass

        self.resources.append(resource_def)


# =============================================================================
# MCP Server Core Implementation
# =============================================================================

class MCPServer:
    """Main MCP server implementation."""

    def __init__(self, state: Optional[MCPState] = None):
        if state is not None:
            self.state = state
        else:
            self.state = MCPState()

        # Initialize configuration placeholder
        self.config = {"server": {"name": self.state.server_name, "version": self.state.version}}


    def initialize(self) -> Dict[str, Any]:
        """Initialize the server and return initialization result."""

        # Build resources list for client
        resource_list = [
            {
                "uri_template": r.uri_template,
                "mimeType": r.mimeType or "text/plain" if self.state.resources.index(r) == 0 else None
            }
            for r in self.state.resources
        ]

        # Build tools list for client
        tool_list = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": json.dumps(t.inputSchema) if isinstance(t.inputSchema, dict) else {}
            }
            for t in self.state.tools.values()
        ]

        return {
            "protocolVersion": "2024-11-05",  # Latest MCP protocol version
            "capabilities": {},
            "serverInfo": {"name": self.config["server"]["name"], "version": self.config["server"]["version"]},
            "resources": resource_list,
            "tools": tool_list
        }

    def handle_resource_request(self, uri: str) -> Optional[Dict[str, Any]]:
        """Handle a request to read a specific resource."""

        # Find matching resource definition by URI template
        for res_def in self.state.resources:
            if uri.startswith(res_def.uri_template):
                try:
                    # Extract path (assuming file:// or http:// prefix is 8 chars)
                    prefix_len = len(res_def.uri_template) + 1 # Account for the separator
                    path = uri[prefix_len:]

                    handler_name = f"get_resource_{res_def.uri_template}"

                    if hasattr(self.state, 'resource_handlers') and handler_name in self.state.resource_handlers:
                        return {
                            "contents": [
                                {
                                    "uri": uri,
                                    "mimeType": res_def.mimeType or "text/plain",
                                    "text": f"--- Content for {uri} ---\nThis is placeholder content served by handler {handler_name}."
                                }
                            ],
                            "resource": {"uri": uri}
                        }
                except Exception as e:
                    logging.error(f"Error handling resource request for {uri}: {e}")

        return None

    def handle_tool_request(self, tool_name: str) -> Dict[str, Any]:
        """Handle a request to execute a specific tool."""

        if tool_name not in self.state.tools:
            logging.error(f"Unknown tool requested: {tool_name}")
            return {"error": f"Tool '{tool_name}' does not exist"}

        # Mock execution result
        return {
            "content": [
                {"type": "text", "text": f"Tool '{tool_name}' executed successfully. (Mock Response)"}
            ],
            "isError": False,
            "result": None
        }

    def handle_notification(self, notification_type: str) -> Optional[Dict[str, Any]]:
        """Handle a client-side notification."""

        if not hasattr(notification_type, 'name'):
            return None

        logging.info(f"Received notification of type {notification_type}")
        return None

    def handle_progress(self, progress_token: str, progress_delta: int) -> Optional[Dict[str, Any]]:
        """Handle a client-side progress update."""

        if not hasattr(progress_token, 'name'):
            return None

        logging.info(f"Progress received for token {progress_token}, delta: {progress_delta}")
        return None


# =============================================================================
# Resource Handler Factory (Example Implementation)
# =============================================================================

class ResourceHandlerFactory:
    """Creates resource handlers based on URI templates."""

    def __init__(self):
        self._handlers = {}  # type: Dict[str, Callable[[str], Any]]

    def register(self, uri_template: str, handler_func: Callable[[str], Any]) -> None:
        """Register a new resource handler for the given URI template.

        Args:
            uri_template: The URI pattern to match (e.g., "file://{path}")
            handler_func: A function that takes a string and returns any type

        Example:
            factory.register("file:///{path}", self._handle_file)
        """
        # Store the handler with its template for later lookup
        if uri_template not in self._handlers:
            self._handlers[uri_template] = handler_func

    def get_handler(self, uri: str) -> Optional[Callable[[str], Any]]:
        """Get a registered handler that matches the given URI.

        Args:
            uri: The resource URI to match

        Returns:
            A callable function if found, None otherwise
        """
        # Simple template matching (you can enhance this with regex or glob patterns)
        for pattern in self._handlers.keys():
            try:
                import re
                compiled_pattern = re.compile(pattern.replace("{", r"\{").replace("}", r"\}"))
                if compiled_pattern.match(uri):
                    return self._handlers[pattern]
            except Exception as e:
                # If regex fails, fall through to next pattern or default behavior
                continue

        # Return None for unmatched URIs (or raise an error depending on your needs)
        print(f"Warning: No handler found for URI '{uri}'")
        return None

    def _handle_file(self, uri: str) -> Any:
        """Example file resource handler.

        Args:
            uri: The full file path

        Returns:
            Resource content as a string or dict
        """
        try:
            import os
            # Extract the actual file path from URI (remove "file://" prefix)
            if uri.startswith("file://"):
                file_path = uri[7:]  # Remove "file://" prefix

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return {
                "uri": uri,
                "mimeType": "text/plain",
                "content": [
                    {"type": "string", "text": content}
                ]
            }
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            raise Exception(f"Resource file '{uri}' does not exist")

    def _handle_binary(self, uri: str) -> Any:
        """Example binary resource handler.

        Args:
            uri: The URI of the binary resource

        Returns:
            Binary content as bytes or dict
        """
        try:
            import os
            if uri.startswith("file://"):
                file_path = uri[7:]  # Remove "file://" prefix

            with open(file_path, 'rb') as f:
                binary_content = f.read()

            return {
                "uri": uri,
                "mimeType": "application/octet-stream",
                "content": [
                    {"type": "bytes", "blob": binary_content}
                ]
            }
        except FileNotFoundError:
            print(f"Binary file not found: {file_path}")
            raise Exception(f"Resource '{uri}' does not exist")

    def _handle_json(self, uri: str) -> Any:
        """Example JSON resource handler.

        Args:
            uri: The URI of the JSON resource

        Returns:
            Parsed JSON content as dict or string representation
        """
        try:
            import os
            if uri.startswith("file://"):
                file_path = uri[7:]  # Remove "file://" prefix

            with open(file_path, 'r', encoding='utf-8') as f:
                json_content = f.read()

            return {
                "uri": uri,
                "mimeType": "application/json",
                "content": [
                    {"type": "string", "text": json_content}  # Return string for simplicity
                ]
            }
        except FileNotFoundError:
            print(f"JSON file not found: {file_path}")
            raise Exception(f"Resource '{uri}' does not exist")


# =============================================================================
# Server Lifecycle Management & Setup
# =============================================================================

class MCPServerLifecycle:
    """Manages the lifecycle of an MCP server instance."""

    def __init__(self, state: Optional[MCPState] = None):
        self.state = state or MCPState()

        # Initialize factory and register handlers
        self.resource_factory = ResourceHandlerFactory()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Registers example resource handlers."""

        # Example Handler 1: File System Mock (Handles file://{path})
        def handle_file_system(path: str) -> str:
            """Mocks reading content from a file path."""
            if not path.startswith("file://"):
                raise ValueError("Path must be a file URI.")

            # Placeholder implementation for reading the file
            return f"Content of the file located at: {path.replace('file://', '')}"

        self.resource_factory.register("file:///{path}", handle_file_system)


    def start(self) -> None:
        """Start the MCP server instance."""
        logging.info("Starting MCP Server...")


# =============================================================================
# Main Entry Point (Example Usage / Demonstration)
# =============================================================================

def create_and_run_server():
    """Create, configure, and demonstrate the MCP server lifecycle."""

    lifecycle = MCPServerLifecycle()
    state = lifecycle.state

    # --- Setup State with Example Tools/Resources ---

    # Define Tool Functions
    def get_weather(location: str, unit: Optional[str] = None):
        return {"location": location, "temperature": 72 + hash(location) % 10,
                "unit": unit or "F" if isinstance(unit, type(None)) else unit}

    def get_current_time():
        now = datetime.datetime.now()
        return {"timestamp": str(now), "iso_format": now.isoformat(),
                "timezone": "UTC", "formatted_date": now.strftime("%A, %B %d, %Y")}

    def calculate_distance(start: Dict[str, float], end: Dict[str, float]) -> Optional[float]:
        if not start or not end: return None
        try:
            lat1 = start.get("lat", 0)
            lon1 = start.get("lon", 0)
            lat2 = end.get("lat", 0)
            lon2 = end.get("lon", 0)
            # Using proper distance calculation (Haversine formula would be better for real use)
            return abs(lat2 - lat1) + abs(lon2 - lon1) * math.pi / 3
        except Exception:
            return None

    # Register Tools
    state.add_tool(ToolDefinition(name="get_weather",
                                 description="Get current weather for a location.",
                                 inputSchema={
                                     "type": "object",
                                     "properties": {
                                         "location": {"type": "string"},
                                         "unit": {"type": ["null", "string"]}
                                     },
                                     "required": []
                                 }))

    state.add_tool(ToolDefinition(name="get_current_time",
                                  description="Get the current UTC time.",
                                  inputSchema={
                                      "type": "object",
                                      "properties": {},
                                      "required": [],
                                      "additionalProperties": False
                                  }))

    state.add_tool(ToolDefinition(name="calculate_distance",
                                  description="Calculate distance between two coordinates.",
                                  inputSchema={
                                      "type": "object",
                                      "properties": {
                                          "start": {"type": "object",
                                                   "properties": {"lat": {"type": "number"},
                                                              "lon": {"type": "number"}},
                                                   "required": ["start"]},
                                          "end": {"type": "object",
                                                  "properties": {"lat": {"type": "number"},
                                                               "lon": {"type": "number"}},
                                                   "required": ["end"]}
                                      },
                                      "required": ["start", "end"]
                                  }))

    # Register Resources using the factory - FIXED CALLS BELOW
    resource_def = ResourceDefinition(uri_template="file://{path}")

    # Use proper handler functions with correct signatures (str -> Any)
    lifecycle.resource_factory.register("file:///{path}",
                                       lifecycle._handle_file)  # Fixed: use actual method

    state.add_resource(resource_def)

    # --- Server Initialization and Demonstration ---
    lifecycle.start()

    print("\n" + "="*50)
    print("MCP SERVER INITIALIZATION COMPLETE")
    print("="*50 + "\n")


    # 1. Initialize Server Response
    init_response = lifecycle.state.initialize()
    print("--- Initial Server Response (Capabilities) ---")
    print(json.dumps(init_response, indent=2))

    print("\n" + "="*50 + "\n")

    # 2. Resource Request Test
    uri_request = "file:///config/settings.json"
    print(f"--- Testing Resource Request for: {uri_request} ---")

    result = lifecycle.handle_resource_request(uri_request)
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("Resource request failed.")

    print("\n" + "="*50 + "\n")


    # 3. Tool Request Test - FIXED METHOD CALLS BELOW
    tool_name = "get_weather"

    try:
        # Try different method names based on your implementation style
        if hasattr(lifecycle, '_invoke_tool'):
            print(f"--- Testing Tool Invocation (Internal Method) for {tool_name} ---")
            tool_response = lifecycle._invoke_tool(tool_name)
        elif hasattr(state, 'invoke_tool'):
            print(f"--- Testing Tool Invocation (State Method) for {tool_name} ---")
            tool_response = state.invoke_tool(tool_name)
        else:
            # Fallback to a direct call if method exists on lifecycle but not named correctly
            print(f"--- Testing Tool Request for {tool_name} ---")

            try:
                # Try calling with common MCP patterns
                import inspect
                methods = [m for m in dir(lifecycle)
                          if 'tool' in m.lower() and callable(getattr(lifecycle, m))]

                print(f"Available tool-related methods on MCPServerLifecycle:")
                for method in sorted(methods):
                    print(f"  - {method}")

            except Exception as e:
                print(f"Error during tool invocation test: {e}")

        if 'tool_response' in locals():
            print(json.dumps(tool_response, indent=2))
    finally:
        # Clean up any temporary variables
        pass

    print("\n" + "="*50)


# ...existing code...
