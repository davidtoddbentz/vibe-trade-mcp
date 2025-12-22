"""Vibe Trade MCP Server"""

# Make 'src' imports work when package is installed
# The package is installed as 'vibe_trade_mcp' but internal code uses 'src' imports
# Use an import hook to create 'src' module on-demand
import sys
import types
from importlib.util import find_spec


class SrcModuleFinder:
    """Import hook to create 'src' module that aliases to 'vibe_trade_mcp'."""

    def find_spec(self, name, path, target=None):
        if name == 'src':
            return find_spec('vibe_trade_mcp')
        return None


# Install the import hook
if 'src' not in sys.modules:
    sys.meta_path.insert(0, SrcModuleFinder())

    # Create the 'src' module by importing vibe_trade_mcp submodules
    # This must happen before any submodule tries to import 'src'
    import types
    src_module = types.ModuleType('src')

    # Import submodules and attach to src
    import vibe_trade_mcp.api
    import vibe_trade_mcp.db
    import vibe_trade_mcp.models
    import vibe_trade_mcp.tools

    src_module.models = vibe_trade_mcp.models
    src_module.db = vibe_trade_mcp.db
    src_module.tools = vibe_trade_mcp.tools
    src_module.api = vibe_trade_mcp.api

    sys.modules['src'] = src_module
