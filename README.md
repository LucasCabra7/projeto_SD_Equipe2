# Agenda compartilhada (Equipe 02)

Projeto de CIN0143 (Sistemas Distribuídos), CIn/UFPE, 2026.2.

API REST de uma agenda de compromissos usada por vários clientes ao mesmo tempo. Cada evento tem título, data, hora, duração e descrição. O desafio é manter a agenda consistente: dois eventos não podem ocupar o mesmo horário, e uma edição não pode sobrescrever sem aviso a edição que outra pessoa salvou antes.

Na Entrega 1 já funcionam `GET /health`, `POST /eventos`, `GET /eventos` e `GET /eventos/{id}`. `PATCH` e `DELETE` estão com o contrato definido abaixo e respondem 501 até a Entrega 2.

## Tecnologia

Python com FastAPI (servidor Uvicorn) e Pydantic para validação.

O FastAPI declara cada rota pelo verbo HTTP, valida o JSON de entrada antes de chegar no nosso código e gera a documentação em `/docs`, onde dá para testar a API pelo navegador. As rotas são `def` (não `async def`), então cada requisição roda numa thread do pool, o mesmo modelo de "uma thread por cliente" das APS com sockets. Por isso o estado compartilhado é protegido com lock.

## Estrutura

```
backend/
├── requirements.txt
├── app/
│   ├── main.py       sobe o servidor na porta 5050 e formata os erros
│   ├── rotas.py      rotas HTTP
│   ├── esquemas.py   payloads e validações
│   └── agenda.py     estado em memória, lock e detecção de conflito
└── tests/
```

## Como rodar

Python 3.10 ou mais novo. De dentro de `backend`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m app.main      # servidor em http://localhost:5050 (docs em /docs)
python -m pytest        # testes
```

## Estado

Os eventos ficam em memória, num objeto `Agenda`:

```python
_eventos:  dict[int, Evento]                       # id -> evento
_por_data: dict[date, list[tuple[int, int, int]]]  # data -> [(inicio, fim, id)] ordenada pelo início
```

Evento: `id`, `titulo`, `data`, `hora`, `duracao` (minutos), `descricao` e `versao`. A `versao` começa em 1, sobe a cada alteração e é enviada como `ETag`.

`_por_data` é o índice para achar conflito de horário. Como a agenda nunca guarda dois eventos sobrepostos, a lista do dia ordenada pelo início também fica ordenada pelo fim. Basta uma busca binária para achar a posição do evento novo e comparar com o vizinho anterior e o seguinte. Por isso todo evento precisa terminar no mesmo dia (até 24:00).

## Rotas

| Método | Rota | Respostas |
|---|---|---|
| GET | `/health` | 200 |
| GET | `/eventos` (filtro opcional `?data=AAAA-MM-DD`) | 200, 422 |
| GET | `/eventos/{id}` | 200 com `ETag`, 404 |
| POST | `/eventos` | 201 com `Location` e `ETag`, 409, 422 |
| PATCH | `/eventos/{id}` (Entrega 2) | 200, 404, 409, 412, 422, 428 |
| DELETE | `/eventos/{id}` (Entrega 2) | 204, 404, 412, 428 |

Corpo do `POST /eventos` (`descricao` é opcional):

```json
{"titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "14:00", "duracao": 60, "descricao": "revisar a entrega"}
```

A resposta devolve o evento com `id` e `versao`. Erros vêm como `{"erro": "..."}`; nos de validação (422) há também `detalhes`, com o campo e a mensagem. Em horário ocupado, o 409 diz com qual evento houve conflito.

No `PATCH` o cliente manda só os campos que quer mudar.

## Validações

- `titulo`: obrigatório, até 100 caracteres, não pode ser só espaços.
- `data`: ISO 8601 (`AAAA-MM-DD`) e precisa existir (`2026-02-30` é recusada).
- `hora`: `HH:MM` em 24h.
- `duracao`: inteiro de 1 a 1440 minutos, e o evento termina até 24:00.
- `descricao`: opcional, até 500 caracteres.
- Campos fora do modelo, como `id` e `versao`, são recusados.

## Concorrência

Lock, dentro de uma requisição. Verificar conflito, gerar o id e gravar acontecem dentro do mesmo `threading.Lock`. Se duas requisições tentam o mesmo horário ao mesmo tempo, uma grava e a outra já vê o evento e recebe 409. Há um teste com 50 POST simultâneos no mesmo horário: exatamente um recebe 201.

ETag e `If-Match`, entre requisições (Entrega 2). O lock não cobre o tempo em que o usuário fica olhando a tela antes de salvar, e o HTTP não guarda estado entre uma requisição e outra. Por isso o `PATCH` e o `DELETE` exigem o cabeçalho `If-Match` com a versão que o cliente leu. Se alguém alterou o evento nesse meio-tempo, a versão não bate e a resposta é 412; sem o cabeçalho, 428. Exemplo: Ana e Bruno leem a versão 1, Ana salva e o evento vai para a versão 2, e o `PATCH` de Bruno com `If-Match: "1"` recebe 412.
