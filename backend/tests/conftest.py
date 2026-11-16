import pytest
from fastapi.testclient import TestClient

from app.agenda import Agenda
from app.main import app
from app.rotas import obter_agenda


@pytest.fixture
def agenda():
    return Agenda()


@pytest.fixture
def cliente(agenda):
    # cada teste usa uma agenda vazia
    app.dependency_overrides[obter_agenda] = lambda: agenda
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def evento_valido():
    return {"titulo": "Reuniao do grupo", "data": "2026-11-10", "hora": "14:00",
            "duracao": 60, "descricao": "revisar o codigo"}
