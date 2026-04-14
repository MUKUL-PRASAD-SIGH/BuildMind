import asyncio
from buildmind.server.mcp_server import mcp

async def test_tool():
    # Simulate a tool call locally to see if FastMCP crashes
    try:
        res = await mcp.call_tool("buildmind_start", {"intent": "test"})
        print(res)
    except Exception as e:
        print(f"Error calling tool: {e}")

asyncio.run(test_tool())
