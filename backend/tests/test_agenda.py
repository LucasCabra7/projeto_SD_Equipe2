import threading


def novo(cliente, hora, duracao=60, data="2026-11-10", titulo="Evento"):
    return cliente.post("/eventos", json={"titulo": titulo, "data": data,
                                         "hora": hora, "duracao": duracao})


def test_conflito_de_horario(cliente):
    assert novo(cliente, "14:00").status_code == 201
    r = novo(cliente, "14:30", 30)
    assert r.status_code == 409
    assert "evento 1" in r.json()["erro"]
    assert novo(cliente, "13:30", 60).status_code == 409
    assert novo(cliente, "13:00", 60).status_code == 201
    assert novo(cliente, "15:00", 30).status_code == 201
    assert novo(cliente, "14:00", data="2026-11-11").status_code == 201


def test_evento_que_engloba_outro(cliente):
    assert novo(cliente, "10:00", 30).status_code == 201
    assert novo(cliente, "09:00", 180).status_code == 409


def test_listar_por_data_ordenado(cliente):
    novo(cliente, "16:00", titulo="B")
    novo(cliente, "09:00", titulo="A")
    novo(cliente, "09:00", data="2026-11-11", titulo="C")
    r = cliente.get("/eventos?data=2026-11-10")
    assert [e["titulo"] for e in r.json()] == ["A", "B"]
    assert len(cliente.get("/eventos").json()) == 3


def test_obter_por_id(cliente):
    novo(cliente, "10:00")
    r = cliente.get("/eventos/1")
    assert r.status_code == 200 and r.headers["ETag"] == '"1"'
    assert cliente.get("/eventos/99").status_code == 404


def test_post_simultaneo_no_mesmo_horario(cliente):
    n = 50
    barreira = threading.Barrier(n)
    status = []

    def tarefa(i):
        barreira.wait()
        status.append(novo(cliente, "10:00", titulo=f"Cliente {i}").status_code)

    threads = [threading.Thread(target=tarefa, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert status.count(201) == 1
    assert status.count(409) == n - 1


def test_ids_unicos_com_post_simultaneo(cliente):
    n = 60
    barreira = threading.Barrier(n)
    ids = []

    def tarefa(i):
        barreira.wait()
        hora = f"{8 + i // 60:02d}:{i % 60:02d}"
        ids.append(novo(cliente, hora, duracao=1).json()["id"])

    threads = [threading.Thread(target=tarefa, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == n
