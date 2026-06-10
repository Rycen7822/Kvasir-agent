from .schemas import TOOL_NAMES, TOOLSET
from .tools import HANDLERS, schema_for


def register(ctx):
    for name in TOOL_NAMES:
        ctx.register_tool(
            name=name,
            toolset=TOOLSET,
            schema=schema_for(name),
            handler=HANDLERS[name],
        )
