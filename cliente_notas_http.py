"""
Cliente MCP que conecta ao servidor_notas_http.py via Streamable HTTP.

Conceitos desta aula:
- O servidor JÁ DEVE ESTAR RODANDO (python servidor_notas_http.py) —
  diferente do stdio, o cliente NÃO inicia o servidor: só conecta na URL.
- streamable_http_client: abre a conexão HTTP e dá os mesmos dois streams
  (leitura/escrita) que o stdio_client dava. A partir daí, NADA muda:
  o ClientSession é o mesmo, o protocolo é o mesmo.
- A sessão HTTP (header mcp-session-id) é gerenciada pelo transporte
  automaticamente — aquilo que fizemos "à mão" com Invoke-WebRequest.
- Ao sair do `async with`, o transporte envia um DELETE para encerrar
  a sessão no servidor (terminate_on_close=True, o padrão).

Para rodar:
    # terminal 1
    python servidor_notas_http.py
    # terminal 2
    python cliente_notas_http.py
"""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:8000/mcp"


async def main() -> None:
    # Única mudança real em relação ao cliente stdio: em vez de
    # StdioServerParameters (comando p/ iniciar subprocesso), uma URL.
    async with streamable_http_client(URL) as (read, write):
        async with ClientSession(read, write) as session:

            # Daqui para baixo o código é IDÊNTICO ao cliente_notas.py —
            # prova de que o protocolo MCP independe do transporte.

            # 1. Handshake obrigatório do protocolo.
            init = await session.initialize()
            print(f"Conectado ao servidor: {init.server_info.name}\n")

            # 2. Descobrir quais ferramentas o servidor oferece.
            tools = await session.list_tools()
            print("Ferramentas disponíveis:")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")
            print()

            # 3. Chamar ferramentas.
            # As tools retornam dict/list — structured_content entrega o valor
            # tipado já desserializado; guardamos o id (GUID) gerado no servidor.
            r = await session.call_tool(
                "adicionar_nota",
                {"titulo": "mercado", "conteudo": "comprar café e pão"},
            )
            print("adicionar_nota ->", r.structured_content)

            r = await session.call_tool(
                "adicionar_nota",
                {"titulo": "estudo", "conteudo": "aprender MCP com HTTP"},
            )
            print("adicionar_nota ->", r.structured_content)
            id_estudo = r.structured_content["id"]

            r = await session.call_tool("listar_notas", {})
            print("listar_notas   ->", r.structured_content)

            # A pesquisa agora é pelo id, não mais pelo título.
            r = await session.call_tool("ler_nota", {"id": id_estudo})
            print("ler_nota       ->", r.structured_content)

            # 4. Ler um resource.
            res = await session.read_resource("notas://resumo")
            print("\nResource notas://resumo:")
            print(res.contents[0].text)

            # 5. Usar um prompt.
            prompt = await session.get_prompt("organizar_notas")
            print("\nPrompt organizar_notas:")
            for msg in prompt.messages:
                print(f"[{msg.role}] {msg.content.text}")

    # Lembrete: rode este cliente DUAS vezes com o servidor de pé e observe —
    # na segunda execução, adicionar_nota devolve "Erro: já existe...".
    # O estado vive no PROCESSO do servidor, não na sessão do cliente.


if __name__ == "__main__":
    asyncio.run(main())
