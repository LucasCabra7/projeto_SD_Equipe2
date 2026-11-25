"""Persistência dos eventos em SQLite."""
import sqlite3
from datetime import date, time

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id        INTEGER PRIMARY KEY,
    titulo    TEXT    NOT NULL,
    data      TEXT    NOT NULL,   -- AAAA-MM-DD
    hora      TEXT    NOT NULL,   -- HH:MM
    duracao   INTEGER NOT NULL,
    descricao TEXT,
    versao    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor INTEGER NOT NULL
);
"""


class RepositorioSQLite:
    def __init__(self, caminho: str = ":memory:"):
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        self._con.executescript(_ESQUEMA)
        self._con.commit()

    def carregar(self) -> tuple[list[dict], int]:
        linhas = self._con.execute(
            "SELECT id, titulo, data, hora, duracao, descricao, versao FROM eventos"
        ).fetchall()
        eventos = [
            {
                "id": i,
                "titulo": titulo,
                "data": date.fromisoformat(d),
                "hora": time.fromisoformat(h),
                "duracao": duracao,
                "descricao": descricao,
                "versao": versao,
            }
            for i, titulo, d, h, duracao, descricao, versao in linhas
        ]
        linha = self._con.execute(
            "SELECT valor FROM meta WHERE chave = 'proximo_id'"
        ).fetchone()
        maior = max((e["id"] for e in eventos), default=0)
        proximo = max(linha[0] if linha else 1, maior + 1)
        return eventos, proximo

    def inserir(self, evento, proximo_id: int) -> None:
        with self._con:
            self._con.execute(
                "INSERT INTO eventos (id, titulo, data, hora, duracao, descricao, versao) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                self._valores(evento),
            )
            self._con.execute(
                "INSERT INTO meta (chave, valor) VALUES ('proximo_id', ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                (proximo_id,),
            )

    def atualizar(self, evento) -> None:
        with self._con:
            self._con.execute(
                "UPDATE eventos SET titulo = ?, data = ?, hora = ?, duracao = ?, "
                "descricao = ?, versao = ? WHERE id = ?",
                self._valores(evento)[1:] + (evento.id,),
            )

    def remover(self, id_evento: int) -> None:
        with self._con:
            self._con.execute("DELETE FROM eventos WHERE id = ?", (id_evento,))

    def fechar(self) -> None:
        self._con.close()

    @staticmethod
    def _valores(evento) -> tuple:
        return (
            evento.id,
            evento.titulo,
            evento.data.isoformat(),
            evento.hora.strftime("%H:%M"),
            evento.duracao,
            evento.descricao,
            evento.versao,
        )
