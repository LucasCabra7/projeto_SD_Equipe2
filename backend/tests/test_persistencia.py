from datetime import date, time

import pytest

from app.agenda import Agenda, ConflitoHorario, VersaoDesatualizada
from app.esquemas import EventoEntrada


def entrada(titulo, hora, duracao=60, data="2026-12-01"):
    return EventoEntrada(titulo=titulo, data=data, hora=hora, duracao=duracao)


def test_eventos_sobrevivem_ao_reinicio(tmp_path):
    banco = str(tmp_path / "agenda.db")
    agenda = Agenda(banco)
    reuniao = agenda.criar(entrada("Reuniao", "14:00"))
    monitoria = agenda.criar(entrada("Monitoria", "16:00"))
    agenda.atualizar(reuniao.id, 1, {"titulo": "Reuniao com o professor"})
    agenda.remover(monitoria.id, 1)
    agenda.fechar()

    reaberta = Agenda(banco)
    eventos = reaberta.listar()
    assert [(e.titulo, e.versao) for e in eventos] == [("Reuniao com o professor", 2)]
    assert eventos[0].data == date(2026, 12, 1) and eventos[0].hora == time(14, 0)
    reaberta.fechar()


def test_regras_continuam_valendo_depois_do_reinicio(tmp_path):
    banco = str(tmp_path / "agenda.db")
    agenda = Agenda(banco)
    evento = agenda.criar(entrada("Reuniao", "14:00"))
    agenda.atualizar(evento.id, 1, {"hora": time(15, 0)})
    agenda.fechar()

    reaberta = Agenda(banco)
    with pytest.raises(ConflitoHorario):
        reaberta.criar(entrada("Choque", "15:30", 30))
    with pytest.raises(VersaoDesatualizada):
        reaberta.atualizar(evento.id, 1, {"titulo": "x"})
    assert reaberta.atualizar(evento.id, 2, {"titulo": "ok"}).versao == 3
    reaberta.fechar()


def test_id_nao_e_reaproveitado(tmp_path):
    banco = str(tmp_path / "agenda.db")
    agenda = Agenda(banco)
    primeiro = agenda.criar(entrada("A", "08:00"))
    segundo = agenda.criar(entrada("B", "09:00"))
    agenda.remover(segundo.id, 1)
    agenda.fechar()

    reaberta = Agenda(banco)
    novo = reaberta.criar(entrada("C", "10:00"))
    assert novo.id not in (primeiro.id, segundo.id)
    reaberta.fechar()
