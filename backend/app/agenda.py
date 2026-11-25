import threading
from bisect import bisect_left, insort
from dataclasses import dataclass, replace
from datetime import date, time

from .esquemas import DURACAO_MAX, EventoEntrada, minutos
from .persistencia import RepositorioSQLite

@dataclass
class Evento:
    id: int
    titulo: str
    data: date
    hora: time
    duracao: int
    descricao: str | None
    versao: int = 1
    
    @property
    def inicio(self) -> int:
        return minutos(self.hora)
    
    @property
    def fim(self) -> int:
        return self.inicio + self.duracao
    
    def para_json(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "data": self.data.isoformat(),
            "hora": self.hora.strftime("%H:%M"),
            "duracao": self.duracao,
            "descricao": self.descricao,
            "versao": self.versao,
        }
            
class ConflitoHorario(Exception):
    def __init__(self, outro: Evento):
        super().__init__(f"conflito de horario com o evento {outro.id} ({outro.titulo})")
        self.outro = outro


class EventoNaoEncontrado(Exception):
    def __init__(self, id_evento: int):
        super().__init__(f"evento {id_evento} nao encontrado")


class VersaoDesatualizada(Exception):
    def __init__(self):
        super().__init__("o evento foi alterado por outra pessoa, leia de novo antes de salvar")


class PassaDaMeiaNoite(Exception):
    def __init__(self):
        super().__init__("o evento precisa terminar no mesmo dia (ate 24:00)")
        
class Agenda:
    """Estado da agenda."""
    def __init__(self, caminho_db: str = ":memory:"):
        self._eventos: dict[int, Evento] = {}
        self._por_data: dict[date, list[tuple[int, int, int]]] = {}
        self._lock = threading.Lock()
        self._repo = RepositorioSQLite(caminho_db)
        linhas, self._proximo_id = self._repo.carregar()
        for linha in linhas:
            evento = Evento(**linha)
            self._eventos[evento.id] = evento
            self._por_no_indice(evento)


    def criar(self, dados: EventoEntrada) -> Evento:
        inicio = minutos(dados.hora)
        fim = inicio + dados.duracao
        with self._lock:
            outro = self._buscar_conflito(dados.data, inicio, fim)
            if outro is not None:
                raise ConflitoHorario(outro)
            evento = Evento(
                self._proximo_id,
                dados.titulo,
                dados.data,
                dados.hora,
                dados.duracao,
                dados.descricao
            )
            self._repo.inserir(evento, self._proximo_id + 1)
            self._eventos[evento.id] = evento
            self._por_no_indice(evento)
            self._proximo_id += 1
        return evento
    
    def listar(self, data: date | None = None) -> list[Evento]:
        with self._lock:
            if data is None:
                eventos = sorted(self._eventos.values(), key=lambda e: (e.data, e.inicio))
            else:
                eventos = [self._eventos[i] for _, _, i in self._por_data.get(data, [])]
            return eventos
    
    def obter(self, id_evento: int) -> Evento | None:
        with self._lock:
            return self._eventos.get(id_evento)
    
    def fechar(self) -> None:
        with self._lock:
            self._repo.fechar()

    def total(self) -> int:
        with self._lock:
            return len(self._eventos)
    
    def atualizar(self, id_evento: int, versao: int, campos: dict) -> Evento:
        with self._lock:
            atual = self._conferir(id_evento, versao)
            novo = replace(atual, **campos, versao=atual.versao + 1)
            if novo.fim > DURACAO_MAX:
                raise PassaDaMeiaNoite()
            self._tirar_do_indice(atual)
            outro = self._buscar_conflito(novo.data, novo.inicio, novo.fim)
            if outro is not None:
                self._por_no_indice(atual)
                raise ConflitoHorario(outro)
            try:
                self._repo.atualizar(novo)
            except Exception:
                self._por_no_indice(atual)
                raise
            self._por_no_indice(novo)
            self._eventos[id_evento] = novo
        return novo

    def remover(self, id_evento: int, versao: int) -> None:
        with self._lock:
            evento = self._conferir(id_evento, versao)
            self._repo.remover(id_evento)
            self._tirar_do_indice(evento)
            del self._eventos[id_evento]

    def _conferir(self, id_evento: int, versao: int) -> Evento:
        evento = self._eventos.get(id_evento)
        if evento is None:
            raise EventoNaoEncontrado(id_evento)
        if evento.versao != versao:
            raise VersaoDesatualizada()
        return evento

    def _por_no_indice(self, evento: Evento) -> None:
        insort(self._por_data.setdefault(evento.data, []), (evento.inicio, evento.fim, evento.id))

    def _tirar_do_indice(self, evento: Evento) -> None:
        lista = self._por_data[evento.data]
        lista.remove((evento.inicio, evento.fim, evento.id))
        if not lista:
            del self._por_data[evento.data]

    def _buscar_conflito(self, data: date, inicio: int, fim: int) -> Evento | None:
        lista = self._por_data.get(data, [])
        pos = bisect_left(lista, (inicio,))
        for vizinho in lista[max(pos - 1, 0):pos + 1]:
            ini_v, fim_v, id_v = vizinho
            if ini_v < fim and inicio < fim_v:
                return self._eventos[id_v]
        return None