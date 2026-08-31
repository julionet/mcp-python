"""
Servidor MCP: Notas Pessoais
Transporte: Streamable HTTP (rede)

Conceitos desta aula:
- No stdio, o CLIENTE inicia o servidor como subprocesso e fala com ele
  por stdin/stdout. Um servidor, um cliente, mesma máquina.
- No Streamable HTTP, o servidor é um PROCESSO INDEPENDENTE que escuta
  numa porta. Clientes conectam pela URL — de qualquer máquina, e VÁRIOS
  ao mesmo tempo. É o transporte usado por servidores MCP "remotos".
- Tudo acontece num ÚNICO endpoint (aqui: http://127.0.0.1:8000/mcp):
    * POST /mcp  -> o cliente envia mensagens JSON-RPC (initialize, tools/call...)
    * GET  /mcp  -> canal SSE opcional para o servidor enviar notificações
- SESSÃO: no initialize, o servidor devolve o header `mcp-session-id`.
  O cliente repete esse header em toda requisição seguinte — é assim que
  o servidor sabe "quem é quem" com vários clientes conectados.

As tools/resources/prompts são EXATAMENTE os mesmos do servidor_notas.py:
o protocolo MCP não muda, só o "cano" por onde ele trafega.
"""

import uuid

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("Notas Pessoais (HTTP)")

# "Banco de dados" em memória.
# ATENÇÃO: com HTTP, VÁRIOS clientes compartilham este mesmo dict —
# diferente do stdio, onde cada cliente tinha seu próprio subprocesso
# (e portanto seu próprio estado). Estado agora é compartilhado!
# Chave: id (GUID gerado automaticamente) -> {"titulo": ..., "conteudo": ...}
notas: dict[str, dict[str, str]] = {}


@mcp.tool()
def adicionar_nota(titulo: str, conteudo: str) -> dict[str, str]:
    """Adiciona uma nova nota e retorna o id (GUID) gerado automaticamente."""
    id_nota = str(uuid.uuid4())
    notas[id_nota] = {"titulo": titulo, "conteudo": conteudo}
    # Retornar um dict (em vez de str) faz o resultado chegar ao cliente
    # também como structured_content — fácil de consumir programaticamente.
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


@mcp.resource("notas://resumo")
def resumo() -> str:
    """Um resumo do estado atual das notas."""
    if not notas:
        return "Nenhuma nota cadastrada."
    linhas = [f"- {nota['titulo']} ({len(nota['conteudo'])} caracteres) [id: {id_nota}]"
              for id_nota, nota in notas.items()]
    return f"Total de notas: {len(notas)}\n" + "\n".join(linhas)


@mcp.prompt()
def organizar_notas() -> str:
    """Gera um prompt para o LLM organizar e resumir todas as notas existentes."""
    if not notas:
        return "Não há nenhuma nota cadastrada para organizar."
    itens = "\n".join(
        f"- **{nota['titulo']}**: {nota['conteudo']}" for nota in notas.values()
    )
    return (
        "Você é um assistente de organização pessoal. "
        "Analise as notas abaixo, identifique temas em comum, "
        "sugira agrupamentos e proponha um resumo executivo.\n\n"
        f"Notas:\n{itens}"
    )


if __name__ == "__main__":
    # Diferente do stdio, aqui NÓS iniciamos o servidor (python servidor_notas_http.py)
    # e ele fica rodando até ser interrompido (Ctrl+C).
    # Por baixo dos panos: MCPServer monta uma app ASGI (Starlette) e a serve
    # com uvicorn — a mesma infraestrutura de um FastAPI da vida.
    # E como o protocolo não passa mais pelo stdout, aqui print() É permitido. :)
    print("Servidor MCP ouvindo em http://127.0.0.1:8000/mcp  (Ctrl+C para parar)")
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",          # troque para "0.0.0.0" p/ aceitar outras máquinas
        port=8000,
        streamable_http_path="/mcp",
    )
