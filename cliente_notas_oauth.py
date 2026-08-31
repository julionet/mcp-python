"""
Cliente MCP com OAuth 2.1 completo — conecta ao servidor_notas_oauth.py.

Conceitos desta aula:
- O cliente NÃO conhece token nenhum. O OAuthClientProvider faz tudo:
    1. tenta acessar /mcp -> recebe 401 com WWW-Authenticate;
    2. lê /.well-known/oauth-protected-resource -> descobre o AS;
    3. se registra dinamicamente (RFC 7591) -> ganha client_id;
    4. abre o fluxo Authorization Code + PKCE em /authorize;
    5. troca o código por token em /token;
    6. repete a chamada original com Authorization: Bearer <token>.
- Nós só fornecemos 3 peças:
    * TokenStorage  — onde guardar tokens/registro (aqui: memória);
    * redirect_handler — o que fazer com a URL de autorização
      (produção: webbrowser.open(url) p/ o usuário logar;
       aqui: seguimos o redirect por HTTP, pois o AS auto-aprova);
    * callback_handler — devolve o code+state que chegou no redirect.
- OAuthClientProvider É um httpx2.Auth: pluga no http client e pronto.

Para rodar:
    # terminal 1
    python servidor_notas_oauth.py
    # terminal 2
    python cliente_notas_oauth.py
"""

import asyncio
from urllib.parse import parse_qs, urlparse

import httpx2

from mcp import ClientSession
from mcp.client.auth import (
    AuthorizationCodeResult,
    OAuthClientProvider,
    TokenStorage,
)
from mcp.client.streamable_http import (
    create_mcp_http_client,
    streamable_http_client,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

URL = "http://127.0.0.1:9000/mcp"


class ArmazenamentoMemoria(TokenStorage):
    """Guarda tokens e o registro do cliente. Produção: disco/keyring."""

    def __init__(self) -> None:
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        print(f">> token recebido: {tokens.access_token[:20]}... "
              f"(expira em {tokens.expires_in}s, escopo: {tokens.scope})")
        self.tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        print(f">> registrado no AS como client_id={client_info.client_id}")
        self.client_info = client_info


# O redirect do /authorize chega aqui (code + state), fora do fluxo httpx.
_resultado: AuthorizationCodeResult | None = None


async def redirect_handler(url: str) -> None:
    """Recebe a URL de autorização. Produção: webbrowser.open(url)."""
    global _resultado
    print(f">> indo ao /authorize do AS (PKCE embutido na URL)")
    async with httpx2.AsyncClient() as http:
        resp = await http.get(url)  # AS auto-aprova e responde 302
    destino = resp.headers["location"]  # http://localhost:3030/callback?code=...
    qs = parse_qs(urlparse(destino).query)
    _resultado = AuthorizationCodeResult(
        code=qs["code"][0],
        state=qs.get("state", [None])[0],
        iss=qs.get("iss", [None])[0],
    )
    print(">> autorização concedida, código recebido no callback")


async def callback_handler() -> AuthorizationCodeResult:
    return _resultado


async def main() -> None:
    oauth = OAuthClientProvider(
        server_url=URL,
        client_metadata=OAuthClientMetadata(
            client_name="cliente-notas-oauth",
            # Para onde o AS redireciona após aprovar. Não sobe servidor
            # nenhum aqui: capturamos o redirect no redirect_handler.
            redirect_uris=["http://localhost:3030/callback"],
            grant_types=["authorization_code"],
            response_types=["code"],
            scope="notas",
        ),
        storage=ArmazenamentoMemoria(),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )

    # OAuthClientProvider é um httpx2.Auth — entra como `auth`, e o 401
    # inicial dispara o fluxo inteiro de descoberta/registro/token.
    http = create_mcp_http_client(auth=oauth)
    async with http:
        async with streamable_http_client(URL, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                print(f"\nConectado ao servidor: {init.server_info.name}\n")

                r = await session.call_tool(
                    "adicionar_nota",
                    {"titulo": "oauth", "conteudo": "fluxo completo com PKCE"},
                )
                print("adicionar_nota ->", r.structured_content)

                r = await session.call_tool("listar_notas", {})
                print("listar_notas   ->", r.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
