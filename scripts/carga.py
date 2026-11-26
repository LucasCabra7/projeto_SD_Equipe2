import json
import random
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from urllib.parse import urlparse

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:5050"
ENDERECO = urlparse(BASE)
PREFIXO = ENDERECO.path
ANO = random.randint(2035, 2099)


def pedir(metodo, caminho, corpo=None, cabecalhos=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json", **(cabecalhos or {})})
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or "null"), time.perf_counter() - inicio
    except urllib.error.HTTPError as erro:
        return erro.code, None, time.perf_counter() - inicio
    except OSError:
        return 0, None, time.perf_counter() - inicio


def ao_mesmo_tempo(quantos, tarefa):
    barreira = threading.Barrier(quantos)
    resultados = [None] * quantos

    def rodar(i):
        barreira.wait()
        resultados[i] = tarefa(i)

    threads = [threading.Thread(target=rodar, args=(i,)) for i in range(quantos)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return resultados


def contar(codigos):
    return {c: codigos.count(c) for c in sorted(set(codigos))}


def conexao_crua():
    return socket.create_connection((ENDERECO.hostname, ENDERECO.port or 80), timeout=5)


def agenda_consistente():
    _, eventos, _ = pedir("GET", "/eventos")
    por_dia = defaultdict(list)
    for e in eventos:
        h, m = map(int, e["hora"].split(":"))
        por_dia[e["data"]].append((h * 60 + m, h * 60 + m + e["duracao"]))
    sobrepostos = sum(1 for dia in por_dia.values()
                      for a, b in zip(sorted(dia), sorted(dia)[1:]) if b[0] < a[1])
    ids = [e["id"] for e in eventos]
    return len(eventos), sobrepostos, len(ids) - len(set(ids))


def mesmo_horario():
    dia = f"{ANO}-01-15"
    codigos = ao_mesmo_tempo(50, lambda i: pedir("POST", "/eventos", {
        "titulo": f"cliente {i}", "data": dia, "hora": "10:00", "duracao": 60})[0])
    print(f"50 clientes criando no mesmo horario: {contar(codigos)}")


def mesma_versao():
    _, evento, _ = pedir("POST", "/eventos", {"titulo": "disputado", "data": f"{ANO}-02-01",
                                              "hora": "10:00", "duracao": 30})
    codigos = ao_mesmo_tempo(30, lambda i: pedir("PATCH", f"/eventos/{evento['id']}",
                                                  {"titulo": f"versao do cliente {i}"},
                                                  {"If-Match": f'"{evento["versao"]}"'})[0])
    _, final, _ = pedir("GET", f"/eventos/{evento['id']}")
    print(f"30 clientes editando a mesma versao: {contar(codigos)}, versao final {final['versao']}")


def disputa_continua(segundos=10):
    alvos = [pedir("POST", "/eventos", {"titulo": f"alvo {k}", "data": f"{ANO}-03-01",
                                         "hora": f"{9 + 2 * k:02d}:00", "duracao": 30})[1]["id"]
             for k in range(3)]
    aceitos = defaultdict(int)
    codigos = []
    trava = threading.Lock()
    fim = time.time() + segundos

    def cliente(n):
        sorteio = random.Random(n)
        while time.time() < fim:
            alvo = sorteio.choice(alvos)
            status, evento, _ = pedir("GET", f"/eventos/{alvo}")
            if status != 200:
                continue
            status, _, _ = pedir("PATCH", f"/eventos/{alvo}", {"descricao": f"cliente {n}"},
                                 {"If-Match": f'"{evento["versao"]}"'})
            with trava:
                codigos.append(status)
                if status == 200:
                    aceitos[alvo] += 1

    ao_mesmo_tempo(10, cliente)
    sem_perda = all(pedir("GET", f"/eventos/{a}")[1]["versao"] == 1 + aceitos[a] for a in alvos)
    print(f"10 clientes disputando 3 eventos por {segundos} s: {contar(codigos)}, "
          f"nenhuma edicao perdida: {'sim' if sem_perda else 'NAO'}")


def clientes_que_caem():
    for _ in range(20):
        con = conexao_crua()
        con.sendall(f"POST {PREFIXO}/eventos HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                    f"Content-Length: 200\r\n\r\n{{\"titulo\": \"meio".encode())
        con.close()
    travados = [conexao_crua() for _ in range(30)]
    for con in travados:
        con.sendall(b"GET /eve")
    tempos = [pedir("GET", "/eventos")[2] for _ in range(10)]
    status, _, _ = pedir("POST", "/eventos", {"titulo": "depois das quedas", "data": f"{ANO}-04-01",
                                              "hora": "10:00", "duracao": 30})
    for con in travados:
        con.close()
    print(f"20 clientes caindo no meio do envio e 30 travados: pior resposta dos outros "
          f"{max(tempos) * 1000:.0f} ms, escrita seguinte {status}")


def carga(clientes=20, rodadas=25):
    tempos = []
    falhas = []

    def cliente(i):
        for j in range(rodadas):
            for metodo, caminho, corpo in (
                ("POST", "/eventos", {"titulo": f"carga {i}-{j}", "data": f"{ANO}-05-{i % 28 + 1:02d}",
                                      "hora": f"{8 + j % 12:02d}:{(i * 2) % 60:02d}", "duracao": 1}),
                ("GET", "/eventos", None),
            ):
                status, _, tempo = pedir(metodo, caminho, corpo)
                tempos.append(tempo)
                if status not in (200, 201, 409):
                    falhas.append(status)

    inicio = time.perf_counter()
    ao_mesmo_tempo(clientes, cliente)
    duracao = time.perf_counter() - inicio
    tempos.sort()
    print(f"carga: {clientes} clientes, {len(tempos)} requisicoes em {duracao:.1f} s "
          f"({len(tempos) / duracao:.0f} por segundo), mediana {tempos[len(tempos) // 2] * 1000:.0f} ms, "
          f"95% abaixo de {tempos[int(len(tempos) * 0.95)] * 1000:.0f} ms, falhas {len(falhas)}")


if __name__ == "__main__":
    print(f"servidor: {BASE}\n")
    mesmo_horario()
    mesma_versao()
    disputa_continua()
    clientes_que_caem()
    carga()
    total, sobrepostos, repetidos = agenda_consistente()
    print(f"\nagenda no fim: {total} eventos, {sobrepostos} sobreposicoes, {repetidos} ids repetidos")
