import logging
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .rotas import router

HOST = "0.0.0.0"
PORTA = 5050

app = FastAPI(
    title="Agenda compartilhada - Equipe 02",
    description="APS 03 de Sistemas Distribuidos: agenda de compromissos via REST.",
    version="0.3.0",
)
app.include_router(router)

ORIGENS = os.environ.get(
    "AGENDA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ORIGENS if o.strip()],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "If-Match"],
    expose_headers=["ETag", "Location"],
)

log = logging.getLogger("agenda")
if not log.handlers:
    _saida = logging.StreamHandler()
    _saida.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    log.addHandler(_saida)
    log.setLevel(logging.INFO)
logging.getLogger("uvicorn.access").disabled = True


@app.middleware("http")
async def registrar_requisicao(request: Request, call_next):
    cliente = f"{request.client.host}:{request.client.port}" if request.client else "?"
    resposta = await call_next(request)
    rota = f"{request.url.path}?{request.url.query}" if request.url.query else request.url.path
    log.info("%s %s cliente=%s resultado=%d",
             request.method, rota, cliente, resposta.status_code)
    return resposta


MENSAGENS = {
    "missing": "campo obrigatorio",
    "extra_forbidden": "campo nao permitido",
    "string_too_short": "nao pode ser vazio",
    "string_too_long": "maximo de {max_length} caracteres",
    "greater_than": "deve ser maior que {gt}",
    "less_than_equal": "deve ser no maximo {le}",
    "int_type": "deve ser um numero inteiro",
    "string_type": "deve ser um texto",
    "json_invalid": "JSON invalido",
}


def traduzir(erro: dict) -> str:
    modelo = MENSAGENS.get(erro["type"])
    if modelo is None:
        return erro["msg"].removeprefix("Value error, ")
    return modelo.format(**erro.get("ctx", {}))


@app.exception_handler(StarletteHTTPException)
def erro_http(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"erro": exc.detail}, status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
def erro_validacao(request: Request, exc: RequestValidationError):
    detalhes = []
    for e in exc.errors():
        campo = ".".join(str(p) for p in e["loc"] if p != "body" and not isinstance(p, int)) or "corpo"
        detalhes.append({"campo": campo, "mensagem": traduzir(e)})
    return JSONResponse({"erro": "dados invalidos", "detalhes": detalhes}, status_code=422)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORTA, access_log=False)
