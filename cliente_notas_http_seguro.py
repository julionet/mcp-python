"""
Cliente MCP que conecta ao servidor_notas_http_seguro.py enviando Bearer token.

Conceitos desta aula:
- O transporte HTTP aceita um httpx client customizado — é por ele que
  injetamos o header `Authorization: Bearer <token>` em TODA requisição.
- create_mcp_http_client: helper do SDK que cria o httpx.AsyncClient já
  com os timeouts recomendados para MCP (SSE de longa duração etc.).
- Num cliente de produção, no lugar do header fixo entraria o
  OAuthClientProvider (mcp.client.auth), que descobre o AS, faz o fluxo
  OAuth com PKCE e renova o token sozinho. O "encaixe" é o mesmo.

Para rodar:
    # terminal 1
    python servidor_notas_http_seguro.py
    # terminal 2
    python cliente_notas_http_seguro.py [token]
"""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import (
    create_mcp_http_client,
    streamable_http_client,
)

URL = "http://127.0.0.1:8001/mcp"

# Token vem da linha de comando; padrão é o token válido da aula.
TOKEN = sys.argv[1] if len(sys.argv) > 1 else "token-secreto-do-julio"


async def main() -> None:
    # A ÚNICA diferença para o cliente sem auth: um httpx client com o header.
    http = create_mcp_http_client(
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    async with http:
        async with streamable_http_client(URL, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                print(f"Conectado ao servidor: {init.server_info.name}\n")

                r = await session.call_tool(
                    "adicionar_nota",
                    {"titulo": "seguranca", "conteudo": "aula de OAuth no MCP"},
                )
                print("adicionar_nota ->", r.structured_content)

                r = await session.call_tool("listar_notas", {})
                print("listar_notas   ->", r.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
