# Contrato da API 

Este documento descreve a API REST da agenda da Equipe 02: o formato dos dados, as rotas, os códigos de resposta e como tratamos a concorrência. Os fluxos de negócio estão desenhados em ["diagrama-negocio.md"](diagrama-negocio.md)

O servidor roda em "http://localhost:5050" e todos os corpos são json. A data segue o ISO 8601 ("AAAA-MM-DD") e não tem fuso horário, então vale o horário local.  A hora é "HH:MM" no formato 24h e a duração é contada em minutos.

Quando algo da errado, a resposta vem como "{"erro": "..."}". No "422" vem também uma lista detalhes com o campo que falhou e o motivo.

## Evento

| Campo | Tipo | Regras |
|:--|:--|:--|
| id | inteiro | gerado pelo servidor |
| titulo | texto | obrigatório, de 1 a 100 caracteres, não pode ser só espaço |
| data | texto | obrigatório, AAAA-MM-DD, precisa ser uma data que existe |
| hora | texto | obrigatório, de 00:00 a 23:59 |
| duracao | inteiro | obrigatório, de 1 a 1440, e o evento tem que acabar até 24:00 |
| descricao | texto ou null | opcional, até 500 caracteres. |
| versao | inteiro | gerada pelo servidor, começa em 1 e sobe a cada alteração |

O servidor recusa campos que não estão no modelo, como mandar id ou versao no corpo. Dois eventos do mesmo dia não podem ter horários sobrepostos.

## Rotas

| Método | Rota | O que enviar | O que volta | Status |
|:--|:--|:--|:--|:--|
| GET | /health | nada | {"status", "eventos"} | 200 |
| GET | /eventos?data= | filtro opcional por dia | lista de eventos | 200, 422 |
| GET | /eventos/{id} | nada | evento e ETag | 200, 404 |
| POST | /eventos | evento sem id e versao | evento, Location e ETag | 201, 409, 422 |
| PATCH | /eventos/{id} | If-Match e os campos que mudam | evento e novo ETag | 200, 404, 409, 412, 422, 428 |
| DELETE | /eventos/{id} | If-Match | corpo vazio | 204, 404, 412, 428 |

Significado dos códigos de erro:

| Status | Quando acontece |
|:--|:--|
| 404 | o evento não existe |
| 409 | o horário bate com outro evento do mesmo dia |
| 412 | a versão no If-Match não é mais a atual ou não é um número |
| 422 | algum campo está inválido, ou a edição faria o evento terminar depois das 24:00 |
| 428 | faltou o cabeçalho If-Match |

## Exemplos

Criando um evento:

```http
POST /eventos
Content-Type: application/json

{ "titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "14:00", "duracao": 60 }
```

```http
HTTP/1.1 201 Created
Location: /eventos/1
ETag: "1"

{ "id": 1, "titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "14:00", "duracao": 60, "descricao": null, "versao": 1 }
```

Tentando marcar outro evento as 14:30 do mesmo dia:

```http
POST /eventos
Content-Type: application/json

{ "titulo": "Monitoria", "data": "2026-11-20", "hora": "14:30", "duracao": 30 }
```

```http
HTTP/1.1 409 Conflict

{ "erro": "conflito de horario com o evento 1 (Reuniao do grupo)" }
```

Mandando um título vazio

```http
HTTP/1.1 422 Unprocessable Entity

{ "erro": "dados invalidos", "detalhes": [ { "campo": "titulo", "mensagem": "nao pode ser vazio" } ] }
```

Buscando um evento que não existe:

```http
GET /eventos/99
```

```http
HTTP/1.1 404 Not Found

{ "erro": "evento 99 nao encontrado" }
```

Mudando o horário:

```http
PATCH /eventos/1
Content-Type: application/json
If-Match: "1"

{ "hora": "15:00" }
```

```http
HTTP/1.1 200 OK
ETag: "2"

{ "id": 1, "titulo": "Reuniao do grupo", "data": "2026-11-20", "hora": "15:00", "duracao": 60, "descricao": null, "versao": 2 }
```

Se outra pessoa mandar o mesmo `PATCH` ainda com `If-Match: "1"`, recebe `412`. Se esquecer o cabeçalho recebe `428`:

```http
HTTP/1.1 412 Precondition Failed

{ "erro": "o evento foi alterado por outra pessoa, leia de novo antes de salvar" }
```

```http
HTTP/1.1 428 Precondition Required

{ "erro": "envie o cabecalho If-Match com a versao do evento" }
```


## Concorrência

Dentro do servidor, a busca por conflito, a geração do id e a gravação ficam no mesmo `threading.Lock`. Se dois `POST` chegam ao mesmo tempo para o mesmo horário, um deles grava e recebe `201`, e o outro já encontra o evento gravado e recebe `409`. Testamos isso com 50 requisições simultâneas e só uma passou.

Entre requisições diferentes usamos controle otimista. A versão do evento vai no cabeçalho `ETag` (como `"1"`, `"2"` e assim por diante) e sobe a cada alteração. O `PATCH` e o `DELETE` exigem o `If-Match` com a versão que o cliente leu. Sem o cabeçalho a resposta é `428`, com uma versão antiga é `412`, o evento não muda e o cliente precisa ler de novo antes de tentar outra vez.