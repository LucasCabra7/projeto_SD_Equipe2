import threading


def test_patch_altera_evento(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    r = cliente.patch("/eventos/1", json={"hora": "15:00"}, headers={"If-Match": '"1"'})
    assert r.status_code == 200
    assert r.headers["ETag"] == '"2"'
    corpo = r.json()
    assert corpo["hora"] == "15:00" and corpo["versao"] == 2
    assert corpo["titulo"] == evento_valido["titulo"]


def test_patch_sem_if_match(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    assert cliente.patch("/eventos/1", json={"hora": "15:00"}).status_code == 428


def test_patch_versao_desatualizada(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    r = cliente.patch("/eventos/1", json={"hora": "15:00"}, headers={"If-Match": '"2"'})
    assert r.status_code == 412
    assert cliente.get("/eventos/1").json()["versao"] == 1


def test_patch_evento_inexistente(cliente):
    r = cliente.patch("/eventos/99", json={"hora": "15:00"}, headers={"If-Match": '"1"'})
    assert r.status_code == 404


def test_patch_conflito_de_horario(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    cliente.post("/eventos", json={**evento_valido, "hora": "16:00"})
    r = cliente.patch("/eventos/2", json={"hora": "14:30"}, headers={"If-Match": '"1"'})
    assert r.status_code == 409
    assert "evento 1" in r.json()["erro"]
    assert cliente.get("/eventos/2").json()["hora"] == "16:00"


def test_patch_dados_invalidos(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    r = cliente.patch("/eventos/1", json={"hora": "25:00"}, headers={"If-Match": '"1"'})
    assert r.status_code == 422


def test_delete_remove_evento(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    r = cliente.delete("/eventos/1", headers={"If-Match": '"1"'})
    assert r.status_code == 204
    assert cliente.get("/eventos/1").status_code == 404


def test_delete_sem_if_match(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    assert cliente.delete("/eventos/1").status_code == 428
    assert cliente.get("/eventos/1").status_code == 200


def test_delete_versao_desatualizada(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    cliente.patch("/eventos/1", json={"hora": "15:00"}, headers={"If-Match": '"1"'})
    assert cliente.delete("/eventos/1", headers={"If-Match": '"1"'}).status_code == 412
    assert cliente.get("/eventos/1").status_code == 200


def test_delete_evento_inexistente(cliente):
    assert cliente.delete("/eventos/99", headers={"If-Match": '"1"'}).status_code == 404


def test_duas_edicoes_simultaneas_na_mesma_versao(cliente, evento_valido):
    cliente.post("/eventos", json=evento_valido)
    barreira = threading.Barrier(2)
    status = []

    def tarefa(titulo):
        barreira.wait()
        r = cliente.patch("/eventos/1", json={"titulo": titulo}, headers={"If-Match": '"1"'})
        status.append(r.status_code)

    threads = [threading.Thread(target=tarefa, args=(t,)) for t in ("Ana", "Bruno")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(status) == [200, 412]
    assert cliente.get("/eventos/1").json()["versao"] == 2
