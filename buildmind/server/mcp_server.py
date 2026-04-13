"""
MCP Server entry point for IDE logic integration.
Provides stdio interfacing exposing BuildMind capabilities to Anthropic / Gemini IDE models.
"""
import sys

def start_mcp_server() -> None:
    """
    Initializes a basic stdio MCP loop exposing orchestrator methods.
    Currently a mock/stub for Phase 15.
    """
    sys.stdout.write(
        "{\n"
        "  \"jsonrpc\": \"2.0\",\n"
        "  \"method\": \"initialize\",\n"
        "  \"params\": {\n"
        "    \"serverInfo\": {\"name\": \"buildmind\", \"version\": \"0.1.0\"},\n"
        "    \"capabilities\": {\"tools\": {}}\n"
        "  }\n"
        "}\n"
    )
    sys.stdout.flush()
    
    # Loop over stdin mimicking MCP protocol listener
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            # Here we would normally route to FastMCP/mcp library
            # For now in MVP dummy mode, we just silently consume and reply generic empty response.
            sys.stdout.write('{"jsonrpc": "2.0", "result": "BuildMind MCP Dummy Mock Acknowledged"}\n')
            sys.stdout.flush()
            
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    start_mcp_server()
