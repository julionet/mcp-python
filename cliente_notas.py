"""
Cliente MCP simples que conecta ao servidor_notas.py via stdio.

Conceitos desta aula:
- O cliente INICIA o processo do servidor (stdio = o servidor é um subprocesso).
- stdio_client: abre o subprocesso e dá dois streams (leitura/escrita).
- ClientSession: implementa o protocolo MCP (JSON-RPC) sobre esses streams.
- Fluxo obrigatório: initialize() antes de qualquer outra chamada.

Para rodar:
    python cliente_notas.py
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    # Como iniciar o servidor: mesmo Python deste venv, rodando o script.
    params = StdioServerParameters(
        command=sys.executable,          # o python do venv atual
        args=["servidor_notas.py"],
    )

    # stdio_client inicia o subprocesso e conecta stdin/stdout dele a nós.
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:

            # 1. Handshake obrigatório do protocolo.
            init = await session.initialize()
            print(f"Conectado ao servidor: {init.server_info.name}\n")

            # 2. Descobrir quais ferramentas o servidor oferece.
            tools = await session.list_tools()
            print("Ferramentas disponíveis:")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")
            print()

            # 3. Chamar ferramentas (o que um LLM faria automaticamente).
            # Como as tools agora retornam dict/list, usamos structured_content:
            # o valor de retorno tipado, já desserializado — em vez de montar
            # o resultado a partir dos blocos de texto de content.
            r = await session.call_tool(
                "adicionar_nota",
                {"titulo": "mercado", "conteudo": "comprar café e pão"},
            )
            print("adicionar_nota ->", r.structured_content)

            r = await session.call_tool(
                "adicionar_nota",
                {"titulo": "estudo", "conteudo": "aprender MCP com Python"},
            )
            print("adicionar_nota ->", r.structured_content)
            # Guardamos o id (GUID) que o SERVIDOR gerou — é a chave de busca.
            id_estudo = r.structured_content["id"]

            r = await session.call_tool("listar_notas", {})
            print("listar_notas   ->", r.structured_content)

            # A pesquisa agora é pelo id, não mais pelo título.
            r = await session.call_tool("ler_nota", {"id": id_estudo})
            print("ler_nota       ->", r.structured_content)

            # 4. Ler um resource (leitura de dado, sem "ação").
            res = await session.read_resource("notas://resumo")
            print("\nResource notas://resumo:")
            print(res.contents[0].text)

            # 5. Usar um prompt (instrução pré-formatada para o LLM).
            # O servidor monta o texto com o estado ATUAL das notas;
            # num cliente real, essas mensagens seriam enviadas ao modelo.
            prompts = await session.list_prompts()
            print("\nPrompts disponíveis:")
            for p in prompts.prompts:
                print(f"  - {p.name}: {p.description}")

            prompt = await session.get_prompt("organizar_notas")
            print("\nPrompt organizar_notas:")
            for msg in prompt.messages:
                print(f"[{msg.role}] {msg.content.text}")


if __name__ == "__main__":
    asyncio.run(main())
