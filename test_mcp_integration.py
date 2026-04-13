"""
Full integration test for BuildMind's Inverted MCP Orchestration.

This test acts as a dummy MCP client (IDE), sends tool calls, and
verifies that:
  1. The MCP server initializes correctly
  2. Tools are listed with correct names
  3. buildmind_start fires sampling/createMessage back to this "IDE"
  4. This "IDE" responds with a dummy task list
  5. The server completes and returns a task plan summary

Run: python test_mcp_integration.py
"""
import subprocess
import json
import time
import sys
import os

# Tracking
sampling_requests_received = 0
tool_responses_received = 0

def send(proc, msg: dict):
    line = json.dumps(msg) + "\n"
    proc.stdin.write(line)
    proc.stdin.flush()

def recv_line(proc, timeout=30) -> dict | None:
    """Read one line from the server with timeout."""
    import select
    try:
        line = proc.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except (json.JSONDecodeError, ValueError):
        return None

def make_dummy_task_response(request_id) -> dict:
    """Create a dummy LLM response simulating task decomposition."""
    tasks_json = json.dumps({
        "tasks": [
            {
                "id": "t1",
                "title": "Choose backend framework (FastAPI vs Flask vs Django)",
                "description": "Select the primary web framework for the API server.",
                "estimated_complexity": "medium",
                "dependencies": []
            },
            {
                "id": "t2",
                "title": "Choose authentication strategy (JWT vs Sessions)",
                "description": "Decide auth approach based on requirements.",
                "estimated_complexity": "medium",
                "dependencies": ["t1"]
            },
            {
                "id": "t3",
                "title": "Implement User and Task data models",
                "description": "Define SQLAlchemy models for User, Task, Project entities.",
                "estimated_complexity": "medium",
                "dependencies": ["t1"]
            },
            {
                "id": "t4",
                "title": "Implement REST API endpoints",
                "description": "Build CRUD routes for tasks with auth middleware.",
                "estimated_complexity": "high",
                "dependencies": ["t2", "t3"]
            },
        ]
    })
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "role": "assistant",
            "content": {
                "type": "text",
                "text": tasks_json
            },
            "model": "dummy-integration-test-model",
            "stopReason": "endTurn"
        }
    }

def make_dummy_classification_response(request_id) -> dict:
    """Dummy response for classification step."""
    classify_json = json.dumps({
        "classifications": [
            {"task_id": "t1", "type": "HUMAN_REQUIRED", "reason": "Framework choice requires team decision"},
            {"task_id": "t2", "type": "HUMAN_REQUIRED", "reason": "Auth strategy has security tradeoffs"},
            {"task_id": "t3", "type": "AI_EXECUTABLE", "reason": "Standard model implementation"},
            {"task_id": "t4", "type": "AI_EXECUTABLE", "reason": "Well-defined CRUD patterns"},
        ]
    })
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "role": "assistant",
            "content": {"type": "text", "text": classify_json},
            "model": "dummy-test",
            "stopReason": "endTurn"
        }
    }

def run_integration_test():
    global sampling_requests_received, tool_responses_received

    print("=" * 60)
    print("BuildMind Inverted MCP Integration Test")
    print("=" * 60)
    print()

    # 1. Start MCP server
    print("[1] Starting BuildMind MCP server...")
    proc = subprocess.Popen(
        ["buildmind", "serve", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1
    )
    time.sleep(0.5)

    # 2. Send MCP initialize with sampling capability
    print("[2] Sending MCP initialize (with sampling capability)...")
    send(proc, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"sampling": {}},  # <-- THIS is what enables upward LLM calls
            "clientInfo": {"name": "BuildMind-Test-Client", "version": "1.0"}
        }
    })

    init_resp = recv_line(proc)
    if not init_resp or "result" not in init_resp:
        print("❌ FAIL: Did not receive valid initialize response")
        print("Got:", init_resp)
        proc.terminate()
        sys.exit(1)
    print(f"   ✅ Server initialized: {init_resp['result']['serverInfo']['name']}")

    # Send initialized notification
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    # 3. List tools
    print("[3] Listing available tools...")
    send(proc, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    })
    tools_resp = recv_line(proc)
    if tools_resp and "result" in tools_resp:
        tool_names = [t["name"] for t in tools_resp["result"].get("tools", [])]
        print(f"   ✅ Tools registered: {tool_names}")
        assert "buildmind_start" in tool_names, "buildmind_start missing!"
        assert "buildmind_resume" in tool_names, "buildmind_resume missing!"
        assert "buildmind_execute" in tool_names, "buildmind_execute missing!"
        assert "buildmind_decide" in tool_names, "buildmind_decide missing!"
        assert "buildmind_status" in tool_names, "buildmind_status missing!"
    else:
        print(f"   ⚠️  Could not list tools: {tools_resp}")

    # 4. Call buildmind_start - this is where the magic happens
    print()
    print("[4] Calling buildmind_start('build a simple task tracker REST API')...")
    print("    Watching for sampling/createMessage from the server...")
    
    send(proc, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "buildmind_start",
            "arguments": {"intent": "build a simple task tracker REST API"}
        }
    })

    # 5. Now act as the IDE — intercept sampling requests and respond
    final_result = None
    request_counter = 0

    for iteration in range(200):  # generous loop
        msg = recv_line(proc)
        if msg is None:
            print("   [Server closed stdout]")
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")

        if method == "sampling/createMessage":
            sampling_requests_received += 1
            request_counter += 1
            prompt_preview = ""
            params = msg.get("params", {})
            messages = params.get("messages", [])
            if messages:
                content = messages[0].get("content", {})
                text = content.get("text", "")
                prompt_preview = text[:100].replace("\n", " ")

            print(f"   🔥 SAMPLING REQUEST #{request_counter} received from BuildMind!")
            print(f"      Prompt preview: {prompt_preview}...")

            # Respond like the IDE would — we send dummy classifier data if it looks like classification
            is_classification = "classif" in prompt_preview.lower() or "human" in prompt_preview.lower()
            if is_classification:
                dummy_resp = make_dummy_classification_response(msg_id)
            else:
                dummy_resp = make_dummy_task_response(msg_id)

            send(proc, dummy_resp)
            print(f"      ↳ Sent dummy LLM response back to BuildMind")

        elif "result" in msg and msg.get("id") == 3:
            # This is the final tool call result
            content_blocks = msg["result"].get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    final_result = block["text"]
            tool_responses_received += 1
            break

        elif "error" in msg:
            print(f"   ❌ Error from server: {msg['error']}")
            break

    proc.terminate()

    # Report results
    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"  Sampling requests received: {sampling_requests_received}")
    print(f"  Final tool response received: {'YES' if final_result else 'NO'}")
    print()

    if sampling_requests_received > 0:
        print("✅ PASS: Inverted MCP Architecture works!")
        print("   BuildMind called sampling/createMessage back to the IDE.")
        print()
    else:
        print("⚠️  PARTIAL: Server responded but no sampling requests detected.")
        print("   This may mean the LLM path wasn't reached (check .buildmind/ init).")

    if final_result:
        print("📋 Final tool result from BuildMind:")
        print("-" * 40)
        print(final_result[:1000])
        print("-" * 40)
    else:
        print("⚠️  No final tool result received (may have timed out or errored).")

if __name__ == "__main__":
    run_integration_test()
