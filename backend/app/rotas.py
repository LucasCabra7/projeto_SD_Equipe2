# Rotas da API REST. Aqui so tem HTTP: ler a requisicao, chamar a agenda
# e montar a resposta (status, headers, JSON). A regra fica em agenda.py.
#
# As funcoes sao "def" (e nao "async def") de proposito: assim o FastAPI roda
# cada requisicao numa thread do pool, varias ao mesmo tempo, igual ao
# "uma thread por cliente" das APS 1 e 2. Por isso a agenda precisa do lock.
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from .agenda import Agenda, ConflitoHorario
from .esquemas import EventoEntrada, EventoParcial, EventoSaida, validar_data

router = APIRouter()

_agenda = Agenda()


def obter_agenda() -> Agenda:
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


# ----- planejadas para a Entrega 2 (contrato ja definido no README) -----

@router.patch("/eventos/{id_evento}", tags=["eventos"], status_code=501,
              summary="(Entrega 2) altera campos; exige If-Match")
def atualizar_evento(id_evento: int, dados: EventoParcial):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "PATCH sera implementado na Entrega 2")


@router.delete("/eventos/{id_evento}", tags=["eventos"], status_code=501,
               summary="(Entrega 2) remove; exige If-Match")
def remover_evento(id_evento: int):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "DELETE sera implementado na Entrega 2")
