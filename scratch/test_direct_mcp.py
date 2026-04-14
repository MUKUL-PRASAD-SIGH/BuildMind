import asyncio
import os
import json
from mcp.server.fastmcp import Context
from buildmind.server.mcp_server import buildmind_start
import buildmind.llm.client as c

class DummyContext:
    class DummySession:
        async def create_message(self, *args, **kwargs):
            # Based on what LLMClient.complete_sync expects:
            # It expects an object with `.content.text`.
            
            # The client calls it twice: once for decomposition, once for classification.
            # We return a generic response that works for both.
            res = {
                "tasks": [
                    {"id": "t1", "title": "Auth", "description": "Auth system", "estimated_complexity": "high", "dependencies": []}
                ],
                "classifications": [
                    {"task_id": "t1", "type": "AI_EXECUTABLE", "reason": "Basic auth"}
                ]
            }
            
            class FakeContent:
                text = json.dumps(res)
            class FakeResult:
                content = FakeContent()
            return FakeResult()
    session = DummySession()
    request_context = None

try:
    print("Testing buildmind_start...")
    res = buildmind_start("build auth", project_dir=os.getcwd(), ctx=DummyContext())
    print("RESULT:")
    print(res)
except Exception as e:
    import traceback
    traceback.print_exc()
