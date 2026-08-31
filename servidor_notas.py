"""
Servidor MCP simples: Notas Pessoais
Transporte: stdio (local)

Conceitos desta aula:
- MCPServer: a forma mais simples de criar um servidor MCP em Python.
  (No SDK 1.x chamava-se FastMCP; no 2.x foi renomeado para MCPServer.)
- Tool: uma função que o cliente (ex.: Claude) pode CHAMAR para executar uma ação.
- Resource: um dado que o cliente pode LER (como um GET, sem efeitos colaterais).

Normalmente quem inicia este processo é o CLIENTE, via stdio.
"""

import uuid

from mcp.server.mcpserver import MCPServer

# Cria o servidor. O nome aparece para o cliente que se conectar.
mcp = MCPServer("Notas Pessoais")

# "Banco de dados" em memória — simples de propósito.
# (Na aula 2 vamos persistir em arquivo JSON.)
# Chave: id (GUID gerado automaticamente) -> {"titulo": ..., "conteudo": ...}
# Com o GUID como chave, títulos repetidos passam a ser permitidos.
notas: dict[str, dict[str, str]] = {}


# ---------------------------------------------------------------------------
# TOOLS — ações que o cliente pode executar.
# O decorator @mcp.tool() transforma a função em uma ferramenta MCP.
# A docstring vira a descrição da ferramenta (é o que o LLM lê para decidir
# quando usá-la!). Os type hints viram o schema JSON dos parâmetros.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# RESOURCE — dado somente-leitura, identificado por uma URI.
# Diferença conceitual: tools são "verbos" (fazer algo),
# resources são "substantivos" (ler algo).
# ---------------------------------------------------------------------------

@mcp.resource("notas://resumo")
def resumo() -> str:
    """Um resumo do estado atual das notas."""
    if not notas:
        return "Nenhuma nota cadastrada."
    linhas = [f"- {nota['titulo']} ({len(nota['conteudo'])} caracteres) [id: {id_nota}]"
              for id_nota, nota in notas.items()]
    return f"Total de notas: {len(notas)}\n" + "\n".join(linhas)


# ---------------------------------------------------------------------------
# PROMPT — modelo de mensagem reutilizável que o cliente pode solicitar.
# Diferença conceitual: tools executam ações, resources expõem dados,
# prompts fornecem instruções/contexto pré-formatados para o LLM.
# ---------------------------------------------------------------------------

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
    # Inicia o servidor usando stdio: ele lê JSON-RPC do stdin
    # e responde no stdout. Por isso NUNCA use print() num servidor stdio —
    # isso corromperia o protocolo. Para depurar, use logging (vai p/ stderr).
    mcp.run(transport="stdio")
