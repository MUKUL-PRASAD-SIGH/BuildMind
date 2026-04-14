"""
Test 6: Verify MCP stdio is clean JSON (no Rich corruption).
Run: python tests\test_6_stdio_clean.py
"""
import sys
import json
import subprocess
import time

print("Test 6: MCP stdio Clean JSONRPC")
print("=" * 50)

print("Starting MCP server subprocess...")
proc = subprocess.Popen(
    ["buildmind", "serve", "--mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    bufsize=1,
)
time.sleep(0.5)

# Send MCP initialize
init_msg = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {"sampling": {}},
        "clientInfo": {"name": "test-stdio-clean", "version": "1.0"},
    },
}
proc.stdin.write(json.dumps(init_msg) + "\n")
proc.stdin.flush()

# Read one line
raw_line = proc.stdout.readline()
proc.terminate()

print(f"Raw line received ({len(raw_line)} chars):")
print(raw_line[:200])
print()

errors = []

# Must parse as valid JSON
try:
    data = json.loads(raw_line.strip())
except json.JSONDecodeError as e:
    errors.append(f"stdout is NOT valid JSON: {e}")
    errors.append(f"First 200 chars: {raw_line[:200]!r}")

if not errors:
    # Must be an initialize response
    if "result" not in data:
        errors.append(f"Expected 'result' in response, got: {list(data.keys())}")
    else:
        server_name = data["result"].get("serverInfo", {}).get("name", "?")
        protocol = data["result"].get("protocolVersion", "?")
        print(f"Server name: {server_name}")
        print(f"Protocol version: {protocol}")

    # Check for ANSI escape codes (Rich corruption)
    if "\x1b[" in raw_line or "\x1b(" in raw_line:
        errors.append("ANSI escape codes detected in stdout — Rich is corrupting MCP stream!")

print()
if errors:
    print("[FAIL] Test 6 failed:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("[PASS] Test 6: stdout is clean JSON — no Rich corruption detected.")
    print("       MCP JSONRPC transport is safe.")
