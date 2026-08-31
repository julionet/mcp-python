"""
Cliente MCP que faz login do usuário para obter JWT e usa o token em Bearer.

Fluxo:
1. Solicita username e password ao usuário
2. POST /login no servidor de autenticação
3. Recebe access_token JWT
4. Usa Authorization: Bearer <token> no cliente MCP
5. Chama as tools autenticadas
"""

import asyncio
import json
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

LOGIN_URL = "http://127.0.0.1:8002/auth/login"
REGISTER_URL = "http://127.0.0.1:8002/auth/register"
MCP_URL = "http://127.0.0.1:8001/mcp"


def solicitar_credenciais() -> tuple[str, str]:
    if len(sys.argv) >= 3:
        return sys.argv[1], sys.argv[2]

    username = input("Usuário: ").strip()
    password = input("Senha: ").strip()
    return username, password


async def cadastrar_usuario(username: str, password: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            REGISTER_URL,
            json={"username": username, "password": password},
            timeout=10,
        )

    if resp.status_code not in {200, 201}:
        raise RuntimeError(f"Falha no cadastro: {resp.status_code} - {resp.text}")

    print(f"Usuário '{username}' cadastrado com sucesso.")


async def obter_token(username: str, password: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            LOGIN_URL,
            json={"username": username, "password": password},
            timeout=10,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Falha no login: {resp.status_code} - {resp.text}")

    data = resp.json()
    return data["access_token"]


async def main() -> None:
    username, password = solicitar_credenciais()

    try:
        await cadastrar_usuario(username, password)
    except RuntimeError as exc:
        print(f"Cadastro: {exc}")

    token = await obter_token(username, password)
    print(f"Token recebido para '{username}'")

    http = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"})
    async with http:
        async with streamable_http_client(MCP_URL, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                print(f"Conectado ao servidor: {init.server_info.name}\n")

                r = await session.call_tool(
                    "adicionar_nota",
                    {"titulo": "login-token", "conteudo": "acesso com usuário cadastrado"},
                )
                print("adicionar_nota ->", r.structured_content)

                r = await session.call_tool("listar_notas", {})
                print("listar_notas   ->", r.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
