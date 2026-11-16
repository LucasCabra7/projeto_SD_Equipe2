# Formato dos payloads JSON que entram e saem da API, com as validacoes.
# O FastAPI usa essas classes (Pydantic) para validar o corpo das requisicoes:
# se algo estiver errado, a requisicao nem chega na agenda e volta 422.
import re
from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TITULO_MAX = 100
DESCRICAO_MAX = 500
DURACAO_MAX = 24 * 60  # minutos

_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_HORA = re.compile(r"^\d{2}:\d{2}$")


def validar_data(valor):
    if not isinstance(valor, str) or not _RE_DATA.match(valor):
        raise ValueError("data deve estar no formato ISO 8601 AAAA-MM-DD")
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ValueError(f"data inexistente: {valor}") from None


def validar_hora(valor):
    if not isinstance(valor, str) or not _RE_HORA.match(valor):
        raise ValueError("hora deve estar no formato HH:MM (24h)")
    try:
        return time.fromisoformat(valor)
    except ValueError:
        raise ValueError(f"hora inexistente: {valor}") from None


def minutos(hora: time) -> int:
    return hora.hour * 60 + hora.minute


class EventoEntrada(BaseModel):
    """Corpo do POST /eventos."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str = Field(min_length=1, max_length=TITULO_MAX)
    data: date
    hora: time
    duracao: int = Field(strict=True, gt=0, le=DURACAO_MAX)
    descricao: str | None = Field(default=None, max_length=DESCRICAO_MAX)

    @field_validator("data", mode="before")
    @classmethod
    def _data(cls, v):
        return validar_data(v)

    @field_validator("hora", mode="before")
    @classmethod
    def _hora(cls, v):
        return validar_hora(v)

    @field_validator("descricao")
    @classmethod
    def _descricao(cls, v):
        return v or None  

    @model_validator(mode="after")
    def _mesmo_dia(self):
        if minutos(self.hora) + self.duracao > DURACAO_MAX:
            raise ValueError("o evento precisa terminar no mesmo dia (ate 24:00)")
        return self


class EventoParcial(BaseModel):
    """Corpo do PATCH /eventos/{id}."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=1, max_length=TITULO_MAX)
    data: date | None = None
    hora: time | None = None
    duracao: int | None = Field(default=None, strict=True, gt=0, le=DURACAO_MAX)
    descricao: str | None = Field(default=None, max_length=DESCRICAO_MAX)

    @field_validator("data", mode="before")
    @classmethod
    def _data(cls, v):
        return None if v is None else validar_data(v)

    @field_validator("hora", mode="before")
    @classmethod
    def _hora(cls, v):
        return None if v is None else validar_hora(v)

    @model_validator(mode="after")
    def _algum_campo(self):
        if not self.model_fields_set:
            raise ValueError("envie pelo menos um campo para alterar")
        return self


class EventoSaida(BaseModel):
    """Formato de um evento nas respostas."""

    id: int
    titulo: str
    data: str      # "2026-11-10"
    hora: str      # "14:00"
    duracao: int
    descricao: str | None
    versao: int
