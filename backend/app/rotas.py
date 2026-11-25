import os
import threading
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from .agenda import (Agenda, ConflitoHorario, EventoNaoEncontrado, PassaDaMeiaNoite,
                     VersaoDesatualizada)
from .esquemas import EventoEntrada, EventoParcial, EventoSaida, validar_data

router = APIRouter()

# Banco padrão: backend/agenda.db.
CAMINHO_DB = os.environ.get("AGENDA_DB", str(Path(__file__).resolve().parent.parent / "agenda.db"))

_agenda: Agenda | None = None
_criando = threading.Lock()


def obter_agenda() -> Agenda:
    """Cria a agenda na primeira requisição"""
    global _agenda
    if _agenda is None:
        with _criando:
            if _agenda is None:
                _agenda = Agenda(CAMINHO_DB)
    return _agenda


def etag(versao: int) -> str:
    return f'"{versao}"'


@router.get("/health", tags=["status"])
def health(agenda: Agenda = Depends(obter_agenda)):
    return {"status": "ok", "eventos": agenda.total()}


@router.get("/eventos", response_model=list[EventoSaida], tags=["eventos"])
def listar_eventos(data: str | None = Query(default=None, description="AAAA-MM-DD"),
                   agenda: Agenda = Depends(obter_agenda)):
    filtro: date | None = None
    if data is not None:
        try:
            filtro = validar_data(data)
        except ValueError as e:
            raise HTTPException(422, str(e))
    return [e.para_json() for e in agenda.listar(filtro)]


@router.get("/eventos/{id_evento}", response_model=EventoSaida, tags=["eventos"],
            responses={404: {"description": "evento nao encontrado"}})
def obter_evento(id_evento: int, response: Response, agenda: Agenda = Depends(obter_agenda)):
    evento = agenda.obter(id_evento)
    if evento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"evento {id_evento} nao encontrado")
    response.headers["ETag"] = etag(evento.versao)
    return evento.para_json()


@router.post("/eventos", response_model=EventoSaida, status_code=status.HTTP_201_CREATED,
             tags=["eventos"], responses={409: {"description": "conflito de horario"}})
def criar_evento(dados: EventoEntrada, response: Response, agenda: Agenda = Depends(obter_agenda)):
    try:
        evento = agenda.criar(dados)
    except ConflitoHorario as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    response.headers["Location"] = f"/eventos/{evento.id}"
    response.headers["ETag"] = etag(evento.versao)
    return evento.para_json()


def versao_do_if_match(if_match: str | None) -> int:
    if if_match is None:
        raise HTTPException(status.HTTP_428_PRECONDITION_REQUIRED,
                            "envie o cabecalho If-Match com a versao do evento")
    valor = if_match.strip('"')
    if not valor.isdigit():
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, str(VersaoDesatualizada()))
    return int(valor)


@router.patch("/eventos/{id_evento}", response_model=EventoSaida, tags=["eventos"])
def atualizar_evento(id_evento: int, dados: EventoParcial, response: Response,
                     if_match: str | None = Header(default=None),
                     agenda: Agenda = Depends(obter_agenda)):
    versao = versao_do_if_match(if_match)
    try:
        evento = agenda.atualizar(id_evento, versao, dados.model_dump(exclude_unset=True))
    except EventoNaoEncontrado as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except VersaoDesatualizada as e:
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, str(e))
    except ConflitoHorario as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except PassaDaMeiaNoite as e:
        raise HTTPException(422, str(e))
    response.headers["ETag"] = etag(evento.versao)
    return evento.para_json()


@router.delete("/eventos/{id_evento}", status_code=status.HTTP_204_NO_CONTENT, tags=["eventos"])
def remover_evento(id_evento: int, if_match: str | None = Header(default=None),
                   agenda: Agenda = Depends(obter_agenda)):
    versao = versao_do_if_match(if_match)
    try:
        agenda.remover(id_evento, versao)
    except EventoNaoEncontrado as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except VersaoDesatualizada as e:
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
