# Agenda compartilhada (Equipe 02)

Projeto de Sistemas Distribuídos.

Fizemos uma API REST de uma agenda de compromissos usada por vários clientes ao mesmo tempo, em que cada evento tem título, data, hora, duração e descrição. Nosso desafio é manter a agenda consistente: dois eventos não podem ocupar o mesmo horário, e uma edição não pode sobrescrever sem aviso a edição que outra pessoa salvou antes.

Por enquanto (Entrega 1) já funcionam `GET /health`, `POST /eventos`, `GET /eventos` e `GET /eventos/{id}`. O `PATCH` e o `DELETE` já têm o contrato definido aqui embaixo, mas só vão ser implementados na Entrega 2; até lá respondem 501.

## Tecnologia

Usamos Python com FastAPI, rodando no Uvicorn, e Pydantic para validar os dados.

Escolhemos o FastAPI porque ele resolve sozinho boa parte do trabalho de uma API REST: cada rota é declarada com o verbo HTTP, o JSON que chega é validado antes de entrar no nosso código e a documentação sai pronta em `/docs` (dá para testar tudo pelo navegador). As rotas são `def` e não `async def`, então cada requisição roda numa thread separada, parecido com o "uma thread por cliente" das APS com sockets. É por isso que a agenda usa lock.

## Estrutura

```
backend/
├── requirements.txt
├── app/
│   ├── main.py       sobe o servidor na porta 5050 e formata os erros
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

| Método | Rota | Respostas |
|---|---|---|
| GET | `/health` | 200 |
| GET | `/eventos` (filtro opcional `?data=AAAA-MM-DD`) | 200, 422 |
| GET | `/eventos/{id}` | 200 com `ETag`, 404 |
| POST | `/eventos` | 201 com `Location` e `ETag`, 409, 422 |
| PATCH | `/eventos/{id}` (Entrega 2) | 200, 404, 409, 412, 422, 428 |
| DELETE | `/eventos/{id}` (Entrega 2) | 204, 404, 412, 428 |

Exemplo de corpo do `POST /eventos` (a `descricao` pode ficar de fora):

```json
{"titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "14:00", "duracao": 60, "descricao": "revisar a entrega"}
```

A resposta volta com o evento completo, já com `id` e `versao`. Quando dá erro, o corpo é `{"erro": "..."}`. No 422 vem também uma lista `detalhes` dizendo qual campo está errado e por quê, e no 409 a mensagem diz qual evento já ocupa aquele horário.

No `PATCH` só é preciso mandar os campos que vão mudar.

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

O segundo é entre requisições e fica para a Entrega 2. O lock não ajuda quando o usuário abre um evento, passa um tempo olhando e só depois salva, porque o HTTP não guarda estado de uma requisição para outra. A solução que vamos usar é o controle otimista: o `PATCH` e o `DELETE` vão exigir o cabeçalho `If-Match` com a versão que o cliente leu. Se alguém mudou o evento nesse meio-tempo, a versão não bate e a resposta é 412; se o cabeçalho não vier, é 428. Por exemplo, se Ana e Bruno abrem o evento na versão 1 e Ana salva primeiro, o evento vai para a versão 2 e o `PATCH` do Bruno com `If-Match: "1"` volta 412.
