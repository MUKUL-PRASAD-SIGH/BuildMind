import subprocess
import json
import time
import os

def run_test():
    print("Starting MCP Server test...")
    # Make sure we use the current script environment
    env = os.environ.copy()
    
    p = subprocess.Popen(
        ["buildmind", "serve", "--mcp"], 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env
    )

    # 1. Provide MCP Initialization
    init_msg = {
        "jsonrpc": "2.0", 
        "id": 1, 
        "method": "initialize", 
        "params": {
            "protocolVersion": "2024-11-05", 
            "capabilities": {"sampling": {}}, 
            "clientInfo": {"name": "test_client", "version": "1.0"}
        }
    }
    p.stdin.write(json.dumps(init_msg) + "\n")
    p.stdin.flush()
    print("INIT RECV:", p.stdout.readline().strip())

    # 2. Notification of init completion
    init_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    p.stdin.write(json.dumps(init_notif) + "\n")
    p.stdin.flush()

    # 3. Call the buildmind_start tool
    print("Triggering buildmind_start tool...")
    call_msg = {
        "jsonrpc": "2.0", 
        "id": 2, 
        "method": "tools/call", 
        "params": {
            "name": "buildmind_start", 
            "arguments": {"intent": "build a simple calculator app"}
        }
    }
    p.stdin.write(json.dumps(call_msg) + "\n")
    p.stdin.flush()

    # 4. Wait for the server to ask the IDE for LLM completion!
    # Because it's calling the tool, BuildMind should hit Decomposer and instantly ask us for LLM samples.
    print("Waiting for Agentic Sampling Request...")
    for _ in range(50):
        line = p.stdout.readline()
        if not line:
            break
        print("RECV:", line.strip().encode("ascii", "ignore").decode("ascii"))
        if "sampling/createMessage" in line:
            print("SUCCESS! BuildMind successfully requested Agentic Sampling from the dummy IDE!")
            
            # Send dummy response back
            request_data = json.loads(line)
            req_id = request_data.get("id")
            
            # Dummy JSON response simulating Claude parsing tasks
            dummy_completion = {
                "tasks": [
                    {"id": "t1", "title": "Setup", "dependencies": [], "estimated_complexity": "low"}
                ]
            }
            
            resp_msg = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "role": "assistant",
                    "content": {
                        "type": "text",
                        "text": json.dumps(dummy_completion)
                    },
                    "model": "dummy-model"
                }
            }
            print("Sending dummy LLM response...")
            p.stdin.write(json.dumps(resp_msg) + "\n")
            p.stdin.flush()
            
    p.terminate()

if __name__ == "__main__":
    run_test()
