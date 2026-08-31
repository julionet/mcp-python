"""
Servidor MCP com autenticação por usuário cadastrado e token JWT.

Fluxo:
1. Cliente faz POST /login com username/password
2. Servidor valida usuário cadastrado
3. Emite um JWT assinado localmente pelo servidor
4. Cliente envia Authorization: Bearer <jwt> nas chamadas MCP
5. O servidor valida o token e só então libera as tools

Objetivo: permitir acesso apenas a usuários cadastrados.
"""

import base64
import hashlib
import hmac
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pydantic import AnyHttpUrl

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

MCP_PORT = 8001
LOGIN_PORT = 8002
SECRET_KEY = "mcp-demo-secret-key"  # em produção, use variável de ambiente
USERS = {
    "admin": "123456",
    "julio": "senha123",
    "maria": "abc123",
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(username: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "username": username,
        "scopes": ["notas:ler", "notas:escrever"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)

        if not hmac.compare_digest(actual, expected):
            return None

        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None

        username = payload.get("username")
        if not username or username not in USERS:
            return None

        return payload
    except Exception:
        return None


class VerificadorJWT(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        payload = verify_token(token)
        if payload is None:
            return None

        return AccessToken(
            token=token,
            client_id=payload["username"],
            scopes=payload.get("scopes", ["notas:ler"]),
            expires_at=int(payload["exp"]),
        )


mcp = MCPServer(
    "Notas Pessoais (HTTP + Token JWT)",
    token_verifier=VerificadorJWT(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("http://127.0.0.1:8001"),
        resource_server_url=AnyHttpUrl("http://127.0.0.1:8001/mcp"),
        required_scopes=["notas:ler"],
    ),
)

notas: dict[str, dict[str, str]] = {}


@mcp.tool()
def adicionar_nota(titulo: str, conteudo: str) -> dict[str, str]:
    """Adiciona uma nova nota e retorna o id gerado."""
    id_nota = str(uuid.uuid4())
    notas[id_nota] = {"titulo": titulo, "conteudo": conteudo}
    return {"id": id_nota, "titulo": titulo, "mensagem": f"Nota '{titulo}' adicionada com sucesso."}


@mcp.tool()
def listar_notas() -> list[dict[str, str]]:
    """Lista todas as notas existentes."""
    return [{"id": id_nota, "titulo": nota["titulo"]} for id_nota, nota in notas.items()]


# ---------------------------------------------------------------------------
# Login HTTP simples para gerar o JWT para usuários cadastrados.
# ---------------------------------------------------------------------------
class LoginHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path not in {"/auth/login", "/auth/register"}:
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "JSON inválido"}).encode())
            return

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "username e password são obrigatórios"}).encode())
            return

        if self.path == "/auth/register":
            if username in USERS:
                self.send_response(409)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "usuário já cadastrado"}).encode())
                return

            USERS[username] = password
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": f"usuário '{username}' cadastrado com sucesso"}).encode())
            return

        if USERS.get(username) != password:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "usuário ou senha inválidos"}).encode())
            return

        token = create_token(username)
        body = json.dumps({"access_token": token, "token_type": "Bearer", "expires_in": 3600}).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def run_login_server() -> None:
    print(f"[login] Endpoints em http://127.0.0.1:{LOGIN_PORT}/auth/login e /auth/register")
    server = ThreadingHTTPServer(("127.0.0.1", LOGIN_PORT), LoginHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def run_mcp_server() -> None:
    print(f"[mcp] Servidor MCP em http://127.0.0.1:{MCP_PORT}/mcp")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=MCP_PORT)


if __name__ == "__main__":
    threading.Thread(target=run_mcp_server, daemon=True).start()
    time.sleep(1)  # pequeno delay para subir o MCP antes do login
    run_login_server()
