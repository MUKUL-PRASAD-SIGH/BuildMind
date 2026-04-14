"""
Test 2: Fake MCP Session Unit Test.
Verifies sampling/createMessage fires correctly without a real IDE.
Run: python tests\test_2_fake_session.py
"""
import sys
import json
import asyncio

print("Test 2: Fake MCP Session (Inverted Sampling)")
print("=" * 50)

# Build a fake async session that records sampling calls
class DummySession:
    calls = []

    async def create_message(self, messages, system_prompt=None, max_tokens=4096, **kwargs):
        call_num = len(self.calls) + 1
        
        # Extract prompt preview
        prompt = ""
        if messages and hasattr(messages[0], 'content'):
            content = messages[0].content
            prompt = getattr(content, 'text', str(content))[:80]
        
        self.calls.append({"num": call_num, "prompt_preview": prompt})
        print(f"  [SAMPLING #{call_num}] fired -> IDE proxy")
        print(f"     Prompt: {prompt[:60]}...")

        # Call 1 = decomposition, Call 2 = classification
        if call_num == 1:
            resp = json.dumps({"tasks": [
                {"id": "t1", "title": "Choose backend framework",
                 "description": "FastAPI vs Flask vs Django",
                 "estimated_complexity": "medium", "dependencies": []},
                {"id": "t2", "title": "Implement REST endpoints",
                 "description": "CRUD routes with auth middleware",
                 "estimated_complexity": "high", "dependencies": ["t1"]},
                {"id": "t3", "title": "Write API documentation",
                 "description": "OpenAPI spec and README examples",
                 "estimated_complexity": "low", "dependencies": ["t2"]},
            ]})
        else:
            resp = json.dumps({"classifications": [
                {"task_id": "t1", "type": "HUMAN_REQUIRED",
                 "reason": "Framework choice requires team alignment"},
                {"task_id": "t2", "type": "AI_EXECUTABLE",
                 "reason": "Well-defined CRUD once framework chosen"},
                {"task_id": "t3", "type": "AI_EXECUTABLE",
                 "reason": "Documentation can be auto-generated"},
            ]})

        class FakeContent:
            text = resp
        class FakeResult:
            content = FakeContent()
        return FakeResult()

# Wire session into LLM client
import buildmind.llm.client as llm_client
session = DummySession()
llm_client.ACTIVE_MCP_SESSION = session
llm_client.set_mcp_session(session)

# Run the CLI start command with the fake session active
from typer.testing import CliRunner
import buildmind.cli as cli

print()
print("Invoking: buildmind start 'build a simple REST API'")
print("-" * 50)

runner = CliRunner()
result = runner.invoke(cli.app, ["start", "build a simple REST API"])

print()
print("-" * 50)
print(f"Exit code: {result.exit_code}")
print(f"Sampling calls fired: {len(session.calls)}")

# Verify
errors = []
if result.exit_code != 0:
    errors.append(f"Non-zero exit code: {result.exit_code}")
    if result.exception:
        import traceback
        tb = traceback.format_exception(
            type(result.exception), result.exception,
            result.exception.__traceback__
        )
        errors.append("".join(tb))

if len(session.calls) < 2:
    errors.append(f"Expected >= 2 sampling calls, got {len(session.calls)}")

print()
if errors:
    print("[FAIL] Test 2 failed:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("[PASS] Test 2: Inverted MCP sampling works correctly!")
    print("       BuildMind fired sampling/createMessage for BOTH decompose + classify.")
    print("       Zero API keys used.")
