# Agenda compartilhada (Equipe 02)

Projeto de Sistemas Distribuídos.

Fizemos uma API REST de uma agenda de compromissos usada por vários clientes ao mesmo tempo, em que cada evento tem título, data, hora, duração e descrição. Nosso desafio é manter a agenda consistente: dois eventos não podem ocupar o mesmo horário, e uma edição não pode sobrescrever sem aviso a edição que outra pessoa salvou antes.

Estão implementadas as rotas `GET /health`, `POST /eventos`, `GET /eventos`, `GET /eventos/{id}`, `PATCH /eventos/{id}` e `DELETE /eventos/{id}`.

## Tecnologia

Usamos Python com FastAPI, rodando no Uvicorn, e Pydantic para validar os dados.

Escolhemos o FastAPI porque ele resolve sozinho boa parte do trabalho de uma API REST: cada rota é declarada com o verbo HTTP, o JSON que chega é validado antes de entrar no nosso código e a documentação sai pronta em `/docs` (dá para testar tudo pelo navegador). As rotas são `def` e não `async def`, então cada requisição roda numa thread separada, parecido com o "uma thread por cliente" das APS com sockets. É por isso que a agenda usa lock.

## Estrutura

```
backend/
├── requirements.txt
├── app/
│   ├── main.py       sobe o servidor na porta 5050, formata os erros e loga cada requisição
│   ├── rotas.py      rotas HTTP
│   ├── esquemas.py   payloads e validações
│   └── agenda.py     estado em memória, lock e conflito de horário
└── tests/
```

## Como rodar

Precisa de Python 3.10 ou mais novo. Dentro da pasta `backend`:

```bash
python3 -m venv .venv            # no Windows: python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m app.main      # servidor em http://localhost:5050 (docs em /docs)
python -m pytest        # testes
```

## Estado

Os eventos ficam em memória, dentro de um objeto `Agenda`, em duas estruturas:

```python
_eventos:  dict[int, Evento]                       # id -> evento
_por_data: dict[date, list[tuple[int, int, int]]]  # data -> [(inicio, fim, id)] ordenada pelo início
```

Cada evento tem `id`, `titulo`, `data`, `hora`, `duracao` (em minutos), `descricao` e `versao`. A versão começa em 1, aumenta a cada alteração e é mandada para o cliente no cabeçalho `ETag`.

O `_por_data` serve para achar conflito de horário rápido. Como a agenda nunca aceita dois eventos sobrepostos, a lista de um dia ordenada pelo início acaba ordenada pelo fim também. Então é só fazer uma busca binária para saber onde o evento novo entraria e comparar com o evento anterior e o seguinte, sem percorrer o dia todo. Para isso dar certo, o evento tem que terminar no mesmo dia (até 24:00).

## Rotas

O contrato da API está em [docs/contrato-api.md](docs/contrato-api.md), e os fluxos de criar, editar e remover evento (incluindo o caso de Ana e Bruno) estão desenhados em [docs/diagrama-negocio.md](docs/diagrama-negocio.md).

| Método | Rota | Respostas |
|---|---|---|
| GET | `/health` | 200 |
| GET | `/eventos` (filtro opcional `?data=AAAA-MM-DD`) | 200, 422 |
| GET | `/eventos/{id}` | 200 com `ETag`, 404 |
| POST | `/eventos` | 201 com `Location` e `ETag`, 409, 422 |
| PATCH | `/eventos/{id}` (exige `If-Match`) | 200 com `ETag`, 404, 409, 412, 422, 428 |
| DELETE | `/eventos/{id}` (exige `If-Match`) | 204, 404, 412, 428 |

Exemplo de corpo do `POST /eventos` (a `descricao` pode ficar de fora):

```json
{"titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "14:00", "duracao": 60, "descricao": "revisar a entrega"}
```

A resposta volta com o evento completo, já com `id` e `versao`. Quando dá erro, o corpo é `{"erro": "..."}`. No 422 vem também uma lista `detalhes` dizendo qual campo está errado e por quê, e no 409 a mensagem diz qual evento já ocupa aquele horário.

No `PATCH` só é preciso mandar os campos que vão mudar.

## Exemplos com curl

Os comandos usam a sintaxe do bash; no Windows, rode no Git Bash.

```bash
# saúde do servidor
curl -s http://localhost:5050/health

# criar evento -> 201, com Location: /eventos/1 e ETag: "1"
curl -si -X POST http://localhost:5050/eventos \
  -H "Content-Type: application/json" \
  -d '{"titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "14:00", "duracao": 60, "descricao": "revisar a entrega"}'

# listar todos, ou só os de um dia
curl -s http://localhost:5050/eventos
curl -s "http://localhost:5050/eventos?data=2026-11-20"

# buscar um evento -> 200 com ETag: "1"
curl -si http://localhost:5050/eventos/1

# editar -> 200 com ETag: "2"
curl -si -X PATCH http://localhost:5050/eventos/1 \
  -H "Content-Type: application/json" \
  -H 'If-Match: "1"' \
  -d '{"hora": "15:00"}'

# remover -> 204
curl -si -X DELETE http://localhost:5050/eventos/1 -H 'If-Match: "2"'
```

## Duas edições simultâneas

Ana e Bruno abrem o mesmo evento na versão 1 e mandam o `PATCH` ao mesmo tempo, os dois com `If-Match: "1"`. Os dois `curl` terminados em `&` rodam em paralelo.

Os comandos supõem o servidor recém-iniciado, em que o `POST` cria o evento com id 1. Se já houver eventos criados antes, troque o `1` de `/eventos/1` pelo `id` que o `POST` devolver.

```bash
curl -s -X POST http://localhost:5050/eventos \
  -H "Content-Type: application/json" \
  -d '{"titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "14:00", "duracao": 60}'

curl -s -o /dev/null -w "Ana: %{http_code}\n" -X PATCH http://localhost:5050/eventos/1 \
  -H "Content-Type: application/json" -H 'If-Match: "1"' \
  -d '{"titulo": "Reuniao com o professor"}' &
curl -s -o /dev/null -w "Bruno: %{http_code}\n" -X PATCH http://localhost:5050/eventos/1 \
  -H "Content-Type: application/json" -H 'If-Match: "1"' \
  -d '{"hora": "16:00"}' &
wait

curl -s http://localhost:5050/eventos/1
```

Saída de uma execução:

```
Ana: 200
Bruno: 412
{"id":1,"titulo":"Reuniao com o professor","data":"2026-11-20","hora":"14:00","duracao":60,"descricao":null,"versao":2}
```

Só um dos dois vence; qual deles depende de quem pega o lock primeiro. Dentro do lock, a versão do `If-Match` é comparada com a atual e a gravação acontece na mesma operação. Por isso, quando a segunda requisição entra, o evento já está na versão 2 e ela recebe 412 em vez de sobrescrever a edição da outra pessoa.

## Validações

- `titulo` é obrigatório, tem até 100 caracteres e não pode ser só espaço.
- `data` tem que estar em ISO 8601 (`AAAA-MM-DD`) e existir de verdade, então `2026-02-30` não passa.
- `hora` é `HH:MM`, no formato 24h.
- `duracao` é um inteiro de 1 a 1440 minutos, e o evento tem que acabar até 24:00.
- `descricao` é opcional, com até 500 caracteres.
- Campo que não faz parte do modelo (como `id` ou `versao`) é recusado.

## Concorrência

Aqui tem dois problemas diferentes.

O primeiro acontece dentro do servidor. Duas requisições podem tentar o mesmo horário no mesmo instante, e as duas poderiam ver o horário livre e gravar. Para evitar isso, a verificação de conflito, a geração do id e a gravação ficam dentro do mesmo `threading.Lock`: uma requisição grava, e quando a outra entra o evento já está lá e ela recebe 409. Testamos com 50 POST simultâneos no mesmo horário e só um recebeu 201.

O segundo é entre requisições. O lock não ajuda quando o usuário abre um evento, passa um tempo olhando e só depois salva, porque o HTTP não guarda estado de uma requisição para outra. A solução que usamos é o controle otimista: o `PATCH` e o `DELETE` exigem o cabeçalho `If-Match` com a versão que o cliente leu. Se alguém mudou o evento nesse meio-tempo, a versão não bate e a resposta é 412; se o cabeçalho não vier, é 428. Por exemplo, se Ana e Bruno abrem o evento na versão 1 e Ana salva primeiro, o evento vai para a versão 2 e o `PATCH` do Bruno com `If-Match: "1"` volta 412.
