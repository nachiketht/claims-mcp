from mcp.server.mcpserver import MCPServer

from tools import get_employee_info as lookup_employee

server = MCPServer("claims")


@server.tool()
def get_employee_info(employee_id: str) -> dict:
    return lookup_employee(employee_id)


if __name__ == "__main__":
    server.run("stdio")
