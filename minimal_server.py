from mcp.server.mcpserver import MCPServer

server = MCPServer("claims")


@server.tool()
def ding() -> str:
    return "dong"


if __name__ == "__main__":
    server.run("stdio")
