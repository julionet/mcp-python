claude mcp add --transport http notas http://127.0.0.1:8000/mcp

claude mcp add --transport http notas-seguras http://127.0.0.1:8001/mcp -H "Authorization: Bearer token-secreto-do-julio"


Nível (b) concluído e funcionando de primeira. Dois arquivos novos: servidor_notas_oauth.py (porta 9000, AS + resource server no mesmo processo) e cliente_notas_oauth.py. O log do servidor narra o fluxo inteiro da spec, requisição por requisição — vale ler com calma:

POST /mcp                                        -> 401   (1. sem token: rejeitado)
GET  /.well-known/oauth-protected-resource/mcp   -> 200   (2. "quem te protege?")
GET  /.well-known/oauth-authorization-server     -> 200   (3. metadados do AS)
POST /register                                   -> 201   (4. registro dinâmico: ganha client_id)
GET  /authorize?...code_challenge=...&resource=  -> 302   (5. Authorization Code + PKCE)
POST /token                                      -> 200   (6. troca código por token)
POST /mcp                                        -> 200   (7. agora sim, com Bearer)

Os pontos-chave do que você viu rodar:

- O cliente partiu do zero absoluto — sem token, sem client_id, sabendo só a URL /mcp. O 401 inicial não foi um erro: foi o gatilho do fluxo. Tudo o mais (descoberta, registro, PKCE, troca) o OAuthClientProvider fez sozinho, porque cada passo é descobrível pelos /.well-known. É exatamente assim que o Claude conecta num servidor MCP remoto protegido sem você configurar nada.
- PKCE em ação: na linha do /authorize dá para ver o code_challenge=wUssSe... (S256). O cliente guardou o code_verifier secreto; na troca em /token, o SDK do servidor conferiu o hash — nós não escrevemos essa validação, só armazenamos o challenge no AuthorizationCode. Também na URL: resource=http://127.0.0.1:9000/mcp — o audience (RFC 8707) viajando desde o início e carimbado no token.
- A divisão de trabalho no servidor: o SDK montou rotas, metadados, validação de PKCE e de redirect_uri; o nosso ProviderNotas só implementou armazenamento e decisões — ~6 métodos em memória. O verify_token do nível (a) virou o load_access_token (com expiração de 1h e código de uso único).
- Onde a aula "trapaceia", e está avisado nos comentários: o authorize() auto-aprova — em produção ali mora a tela de login e consentimento — e o AS vive no mesmo processo do resource server. Com um Keycloak/Auth0 real, o seu servidor voltaria ao formato do nível (a) (token_verifier validando JWTs do AS via JWKS), e o cliente não muda uma linha — só o redirect_handler viraria webbrowser.open(url).
- Detalhe fino no fim do log: o DELETE /mcp encerrando a sessão — aquele terminate_on_close do transporte que comentamos na aula do HTTP.

Com isso você percorreu a trilha completa de auth do MCP: stdio (sem auth, por design) → HTTP aberto → Bearer estático (nível a) → OAuth 2.1 completo (nível b). Os próximos degraus naturais, quando quiser: validação de JWT com JWKS contra um AS externo de verdade (Keycloak via Docker), escopos por tool, ou voltar à trilha principal (persistência em JSON, ou terminar o agente.py ligando um LLM às suas tools).

✻ Sautéed for 3m 38s · done 23:32

● Background command "Start OAuth MCP server on port 9000" failed with exit code 255

Notificação esperada: é o encerramento do servidor OAuth da porta 9000, que eu mesmo derrubei com Stop-Process ao final da demo (exit 255 = processo forçado a parar). Nenhuma porta ficou ocupada, nenhum processo fantasma. Tudo em ordem — aguardo você para o próximo passo da trilha.

vamos para o Keycloak com Docker