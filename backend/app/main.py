import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .rotas import router

HOST = "0.0.0.0"
PORTA = 5050

app = FastAPI(
    title="Agenda compartilhada - Equipe 02",
    description="APS 03 de Sistemas Distribuidos: agenda de compromissos via REST.",
    version="0.1.0",
)
app.include_router(router)


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
    uvicorn.run(app, host=HOST, port=PORTA)
