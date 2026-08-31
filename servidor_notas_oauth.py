"""
Servidor MCP: Notas Pessoais — OAuth 2.1 COMPLETO (nível b)

Conceitos desta aula:
- No nível (a), o verify_token comparava com uma lista fixa. Agora o ciclo
  é completo: um AUTHORIZATION SERVER emite os tokens que o RESOURCE
  SERVER valida. O cliente não conhece token nenhum de antemão — ele
  DESCOBRE o AS, se REGISTRA, faz o fluxo Authorization Code + PKCE e
  só então recebe um token.
- OAuthAuthorizationServerProvider: o "motor" do AS. O SDK monta as rotas
  (/authorize, /token, /register, /.well-known/...) e a validação de PKCE;
  nós implementamos só o armazenamento e as decisões (emitir código,
  trocar por token, validar token).
- NESTA AULA o AS mora no MESMO processo do servidor de notas e AUTO-APROVA
  qualquer autorização (sem tela de login). Em produção, o AS é um serviço
  separado (Keycloak, Auth0, Entra ID) — e o resto do código NÃO muda:
  o resource server só validaria tokens de lá.
"""

import secrets
import time
import uuid

from pydantic import AnyHttpUrl

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    OAuthClientInformationFull,
    OAuthToken,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer

ESCOPO = "notas"


class ProviderNotas(OAuthAuthorizationServerProvider):
    """AS mínimo, em memória, que auto-aprova autorizações (didático!)."""

    def __init__(self) -> None:
        self.clientes: dict[str, OAuthClientInformationFull] = {}
        self.codigos: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}

    # -- Registro dinâmico (RFC 7591): o cliente se apresenta e ganha client_id
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clientes.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        print(f"[AS] cliente registrado: {client_info.client_name} "
              f"(client_id={client_info.client_id})")
        self.clientes[client_info.client_id] = client_info

    # -- Autorização: em produção, AQUI apareceria a tela de login/consent.
    #    Nós auto-aprovamos: geramos o código e redirecionamos de volta.
    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        codigo = f"cod-{secrets.token_hex(16)}"
        self.codigos[codigo] = AuthorizationCode(
            code=codigo,
            client_id=client.client_id,
            scopes=params.scopes or [ESCOPO],
            expires_at=time.time() + 300,          # código vale 5 min
            code_challenge=params.code_challenge,  # PKCE: o SDK confere depois
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,              # audience (RFC 8707)
        )
        print(f"[AS] autorização auto-aprovada p/ {client.client_id}")
        return construct_redirect_uri(
            str(params.redirect_uri), code=codigo, state=params.state
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        return self.codigos.get(authorization_code)

    # -- Troca do código por token (o SDK já validou PKCE e redirect_uri)
    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        del self.codigos[authorization_code.code]  # código é de USO ÚNICO
        token = f"tok-{secrets.token_hex(24)}"
        self.tokens[token] = AccessToken(
            token=token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 3600,    # token vale 1 hora
            resource=authorization_code.resource,
        )
        print(f"[AS] token emitido p/ {client.client_id}")
        return OAuthToken(
            access_token=token,
            token_type="Bearer",
            expires_in=3600,
            scope=" ".join(authorization_code.scopes),
        )

    # -- Validação (lado RESOURCE SERVER): substitui o dict fixo do nível (a)
    async def load_access_token(self, token: str) -> AccessToken | None:
        info = self.tokens.get(token)
        if info and info.expires_at and info.expires_at < time.time():
            del self.tokens[token]                 # expirado -> some
            return None
        return info

    # -- Refresh/revogação: fora do escopo da aula (o cliente não vai usar)
    async def load_refresh_token(self, client, refresh_token) -> RefreshToken | None:
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes) -> OAuthToken:
        raise NotImplementedError

    async def revoke_token(self, token) -> None:
        pass


mcp = MCPServer(
    "Notas Pessoais (OAuth)",
    auth_server_provider=ProviderNotas(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("http://127.0.0.1:9000"),        # o AS somos nós
        resource_server_url=AnyHttpUrl("http://127.0.0.1:9000/mcp"),
        client_registration_options=ClientRegistrationOptions(
            enabled=True,                    # liga o registro dinâmico (RFC 7591)
            valid_scopes=[ESCOPO],
            default_scopes=[ESCOPO],
        ),
        required_scopes=[ESCOPO],
    ),
)

# Tools reduzidas ao essencial — o foco da aula é o OAuth.
notas: dict[str, dict[str, str]] = {}


@mcp.tool()
def adicionar_nota(titulo: str, conteudo: str) -> dict[str, str]:
    """Adiciona uma nova nota e retorna o id (GUID) gerado automaticamente."""
    id_nota = str(uuid.uuid4())
    notas[id_nota] = {"titulo": titulo, "conteudo": conteudo}
    return {"id": id_nota, "titulo": titulo,
            "mensagem": f"Nota '{titulo}' adicionada com sucesso."}


@mcp.tool()
def listar_notas() -> list[dict[str, str]]:
    """Lista todas as notas existentes (id e título de cada uma)."""
    return [{"id": id_nota, "titulo": nota["titulo"]}
            for id_nota, nota in notas.items()]


if __name__ == "__main__":
    print("Servidor MCP com OAuth completo em http://127.0.0.1:9000/mcp")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=9000)
