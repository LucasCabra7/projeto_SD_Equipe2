import pytest


def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "eventos": 0}


def test_cria_evento_valido(cliente, evento_valido):
    r = cliente.post("/eventos", json=evento_valido)
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["id"] == 1 and corpo["versao"] == 1
    assert r.headers["Location"] == "/eventos/1"
    assert r.headers["ETag"] == '"1"'


def test_descricao_opcional(cliente, evento_valido):
    del evento_valido["descricao"]
    r = cliente.post("/eventos", json=evento_valido)
    assert r.status_code == 201
    assert r.json()["descricao"] is None


@pytest.mark.parametrize("campo, valor", [
    ("data", "10/11/2026"),
    ("data", "2026-02-30"),
    ("data", 20261110),
    ("hora", "25:00"),
    ("hora", "9:30"),
    ("hora", "14:00:00"),
    ("duracao", 0),
    ("duracao", -10),
    ("duracao", "60"),
    ("duracao", 1441),
    ("titulo", "   "),
    ("titulo", "x" * 101),
    ("descricao", "x" * 501),
])
def test_campos_invalidos(cliente, evento_valido, campo, valor):
    evento_valido[campo] = valor
    r = cliente.post("/eventos", json=evento_valido)
    assert r.status_code == 422
    assert r.json()["erro"] == "dados invalidos"


@pytest.mark.parametrize("campo", ["titulo", "data", "hora", "duracao"])
def test_campos_obrigatorios(cliente, evento_valido, campo):
    del evento_valido[campo]
    assert cliente.post("/eventos", json=evento_valido).status_code == 422


def test_campo_desconhecido(cliente, evento_valido):
    evento_valido["versao"] = 7
    assert cliente.post("/eventos", json=evento_valido).status_code == 422


def test_evento_nao_pode_passar_da_meia_noite(cliente, evento_valido):
    evento_valido.update(hora="23:30", duracao=60)
    r = cliente.post("/eventos", json=evento_valido)
    assert r.status_code == 422
    evento_valido.update(duracao=30)
    assert cliente.post("/eventos", json=evento_valido).status_code == 201


def test_filtro_list_com_data_invalida(cliente):
    assert cliente.get("/eventos?data=amanha").status_code == 422


def test_rotas_da_entrega_2(cliente):
    assert cliente.patch("/eventos/1", json={"titulo": "x"}).status_code == 501
    assert cliente.delete("/eventos/1").status_code == 501
