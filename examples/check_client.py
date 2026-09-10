"""Use the local demo through authenticated Streamable HTTP."""
import asyncio
import os

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp", auth=os.environ["MCP_GATEWAY_TOKEN"]) as client:
        print([tool.name for tool in await client.list_tools()])
        print(await client.call_tool("catalog_list_items", {}))


if __name__ == "__main__":
    asyncio.run(main())
