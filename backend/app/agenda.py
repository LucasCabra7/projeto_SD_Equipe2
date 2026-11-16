import threading
from bisect import bisect_left, insort
from dataclasses import dataclass
from datetime import date, time

from .esquemas import EventoEntrada, minutos

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
        
class Agenda:
    def __init__(self):
        self._eventos: dict[int, Evento] = {}
        self._por_data: dict[date, list[tuple[int, int, int]]] = {}
        self._proximo_id = 1
        self._lock = threading.Lock()
        
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
            self._eventos[evento.id] = evento
            insort(self._por_data.setdefault(dados.data, []), (inicio, fim, evento.id))
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
    
    def total(self) -> int:
        with self._lock:
            return len(self._eventos)
    
    def _buscar_conflito(self, data: date, inicio: int, fim: int) -> Evento | None:
        lista = self._por_data.get(data, [])
        pos = bisect_left(lista, (inicio,))
        for vizinho in lista[max(pos - 1, 0):pos + 1]:
            ini_v, fim_v, id_v = vizinho
            if ini_v < fim and inicio < fim_v:
                return self._eventos[id_v]
        return None