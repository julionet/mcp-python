"""
Servidor MCP: Notas Pessoais — HTTP com AUTENTICAÇÃO (nível a)

Conceitos desta aula:
- No MCP sobre HTTP, o servidor é um OAuth RESOURCE SERVER: ele não emite
  tokens, apenas VALIDA o Bearer token que chega em cada requisição.
- TokenVerifier: protocolo com UM método — verify_token(token) que devolve:
    * um AccessToken  -> requisição autorizada (segue para as tools)
    * None            -> o SDK responde 401 automaticamente
- AuthSettings: diz "quem sou eu" (resource_server_url = audience) e
  "quem emite meus tokens" (issuer_url). Esses dados são publicados em
  /.well-known/oauth-protected-resource para clientes descobrirem o AS.

NESTA AULA (nível a): validamos contra uma lista fixa de tokens — sem
Authorization Server de verdade — só para ver o 401/200 e o Bearer fluindo.
Em produção, verify_token validaria um JWT (assinatura, expiração,
audience) ou consultaria o endpoint de introspecção do AS.
"""

import uuid

from pydantic import AnyHttpUrl

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

# ---------------------------------------------------------------------------
# "Banco" de tokens — fixo, didático. Cada token conhece seu dono e escopos.
# NUNCA faça isso em produção: tokens vivem no AS, não no código.
# ---------------------------------------------------------------------------
TOKENS_VALIDOS = {
    "token-secreto-do-julio": {
        "client_id": "julio",
        "scopes": ["notas:ler", "notas:escrever"],
    },
    "token-do-estagiario": {
        "client_id": "estagiario",
        "scopes": [],  # sem escopos -> barrado pelo required_scopes (403)
    },
}


class VerificadorEstatico(TokenVerifier):
    """Valida o Bearer contra a lista fixa acima."""

    async def verify_token(self, token: str) -> AccessToken | None:
        dados = TOKENS_VALIDOS.get(token)
        if dados is None:
            return None  # token desconhecido -> o SDK responde 401
        return AccessToken(
            token=token,
            client_id=dados["client_id"],
            scopes=dados["scopes"],
            expires_at=None,  # aqui entraria a expiração do token real
        )


mcp = MCPServer(
    "Notas Pessoais (HTTP Seguro)",
    token_verifier=VerificadorEstatico(),
    auth=AuthSettings(
        # Em produção: a URL do seu Authorization Server (Keycloak, Auth0...).
        # Sem AS real nesta aula, apontamos para nós mesmos.
        issuer_url=AnyHttpUrl("http://127.0.0.1:8001"),
        # Quem EU sou — o "audience" que o token precisa ter sido emitido para.
        resource_server_url=AnyHttpUrl("http://127.0.0.1:8001/mcp"),
        # Escopo mínimo para falar comigo; sem ele o SDK responde 403.
        required_scopes=["notas:ler"],
    ),
)

# Mesmo modelo da aula anterior: id (GUID) -> {"titulo": ..., "conteudo": ...}
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


@mcp.tool()
def ler_nota(id: str) -> dict[str, str]:
    """Retorna a nota (título e conteúdo) com o id informado."""
    if id not in notas:
        return {"erro": f"Não existe nota com id '{id}'."}
    nota = notas[id]
    return {"id": id, "titulo": nota["titulo"], "conteudo": nota["conteudo"]}


@mcp.tool()
def remover_nota(id: str) -> str:
    """Remove a nota com o id informado."""
    if id not in notas:
        return f"Erro: não existe nota com id '{id}'."
    titulo = notas.pop(id)["titulo"]
    return f"Nota '{titulo}' (id {id}) removida."


if __name__ == "__main__":
    print("Servidor MCP SEGURO ouvindo em http://127.0.0.1:8001/mcp")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)
