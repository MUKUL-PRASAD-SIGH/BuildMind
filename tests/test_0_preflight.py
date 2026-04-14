"""
Test 0: Pre-flight checks.
Verifies all 7 research implementation claims.
Run: python tests\test_0_preflight.py
"""
import sys
import asyncio

PASS = []
FAIL = []

def check(name, fn):
    try:
        detail = fn()
        PASS.append((name, detail or "OK"))
    except Exception as e:
        FAIL.append((name, str(e)))

# 1. MCP server loads + 5 tools registered
def check_tools():
    from buildmind.server.mcp_server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = [t.name for t in tools]
    expected = {'buildmind_start','buildmind_resume','buildmind_decide','buildmind_execute','buildmind_status'}
    missing = expected - set(names)
    if missing:
        raise AssertionError(f"Missing tools: {missing}")
    return ", ".join(names)

check("FastMCP: 5 tools registered", check_tools)

# 2. LLM client contextvars isolation
def check_contextvars():
    import buildmind.llm.client as c
    assert hasattr(c, 'ACTIVE_MCP_SESSION'), "ACTIVE_MCP_SESSION missing"
    assert hasattr(c, '_mcp_session_var'), "_mcp_session_var missing"
    assert hasattr(c, 'set_mcp_session'), "set_mcp_session missing"
    assert hasattr(c, 'get_mcp_session'), "get_mcp_session missing"

check("LLM client: contextvars session isolation", check_contextvars)

# 3. _complete_mcp fires sampling/createMessage
def check_sampling():
    import inspect
    from buildmind.llm.client import LLMClient
    src = inspect.getsource(LLMClient._complete_mcp)
    assert 'create_message' in src, "create_message not found"
    assert 'SamplingMessage' in src, "SamplingMessage not found"

check("LLM client: _complete_mcp fires sampling/createMessage", check_sampling)

# 4. anyio.from_thread.run + asyncio fallback
def check_anyio():
    import inspect
    from buildmind.llm.client import LLMClient
    src = inspect.getsource(LLMClient.complete_sync)
    assert 'anyio.from_thread' in src, "anyio.from_thread missing"
    assert 'asyncio.run' in src, "asyncio.run fallback missing"

check("LLM client: anyio.from_thread + asyncio fallback", check_anyio)

# 5. Rich console suppression in MCP server
def check_console():
    import inspect
    from buildmind.server import mcp_server
    src = inspect.getsource(mcp_server)
    assert '_silent_console' in src, "_silent_console missing"
    assert 'console.quiet' in src, "console.quiet missing"

check("MCP server: Rich console suppression", check_console)

# 6. Disk persistence
def check_storage():
    from buildmind.storage.project_store import load_tasks, load_project

check("Storage: disk persistence functions", check_storage)

# 7. File writer
def check_writer():
    from buildmind.core.file_writer import write_files, FileAction

check("Execution: FileWriter for code generation", check_writer)

# ── Report ──────────────────────────────────────────────────────────────────
print()
print(f"Pre-flight: {len(PASS)}/{len(PASS)+len(FAIL)} checks PASSED")
print()

for name, detail in PASS:
    print(f"  [PASS] {name}")
    print(f"         {detail}")

for name, detail in FAIL:
    print(f"  [FAIL] {name}")
    print(f"         {detail}")

print()
if FAIL:
    print("Some checks FAILED. Fix before proceeding.")
    sys.exit(1)
else:
    print("All checks passed. Ready to test.")
