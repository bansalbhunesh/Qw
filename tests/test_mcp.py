from auteur.mcp_server import mcp, auteur_budget

def test_mcp_server_tools():
    # Verify the tools are registered
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert "auteur_produce" in tools
    assert "auteur_budget" in tools
    assert "auteur_critique" in tools

def test_auteur_budget(tmp_path):
    # Ensure it returns an error string if no ledger is found
    res = auteur_budget(workdir=str(tmp_path))
    assert "No ledger found" in res
