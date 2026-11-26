# Agenda compartilhada (Equipe 02)

Projeto de Sistemas Distribuídos (CIN0143, CIn/UFPE).

Fizemos uma agenda de compromissos compartilhada: vários clientes, em máquinas diferentes, criam, editam e removem eventos na mesma agenda ao mesmo tempo. Cada evento tem título, data, hora, duração e descrição. O desafio é manter a agenda consistente: dois eventos não podem ocupar o mesmo horário, e uma edição não pode sobrescrever sem aviso a edição que outra pessoa salvou antes.

## Como as peças se ligam

```
navegador (qualquer máquina da rede)
        │  http://IP-DO-SERVIDOR:5173
        ▼
Vite (porta 5173) ── entrega a página React e repassa /api para o backend
        │  http://127.0.0.1:5050
        ▼
FastAPI (porta 5050) ── rotas, validação, lock e controle de versão
        │
        ▼
SQLite (backend/agenda.db) ── os eventos sobrevivem ao reinício
```

O servidor é uma máquina só, que roda o backend e o Vite. Os clientes só precisam de um navegador. Como a página e a API saem do mesmo endereço (o Vite repassa tudo que começa com `/api`), ninguém precisa configurar o IP da API nem liberar CORS.

## Tecnologia

- **Backend:** Python com FastAPI, rodando no Uvicorn, e Pydantic para validar os dados. Escolhemos o FastAPI porque ele resolve boa parte do trabalho de uma API REST: cada rota é declarada com o verbo HTTP, o JSON é validado antes de entrar no nosso código e a documentação sai pronta em `/docs`. As rotas são `def` e não `async def`, então cada requisição roda numa thread do pool, parecido com o "uma thread por cliente" das APS com sockets. É por isso que a agenda usa lock.
- **Persistência:** SQLite, que já vem no Python. Não precisa instalar nem subir servidor de banco.
- **Interface:** React com TypeScript, Ant Design e Vite.
- **Atualização em tempo real:** polling. A página pede a lista ao servidor a cada 3 segundos e destaca o que outra pessoa mudou.

## Estrutura

```
backend/
├── requirements.txt
├── app/
│   ├── main.py           sobe o servidor na porta 5050, formata os erros e loga cada requisição
│   ├── rotas.py          rotas HTTP
│   ├── esquemas.py       payloads e validações
│   ├── agenda.py         estado em memória, lock e conflito de horário
│   └── persistencia.py   gravação dos eventos no SQLite
└── tests/
frontend/agenda/
├── vite.config.ts        porta 5173 e o repasse de /api para o backend
└── src/
    ├── api/              chamadas à API e tipos
    ├── hooks/            estado da agenda no cliente e o polling
    └── components/       lista, calendário e formulário do evento
scripts/
└── carga.py              teste de carga e de robustez
docs/
├── contrato-api.md
└── diagrama-negocio.md
```

## Como rodar

Precisa de **Python 3.10** ou mais novo e **Node 20.19** ou mais novo (ou 22.12+).

Backend, num terminal, dentro de `backend`:

```bash
python3 -m venv .venv            # no Windows: python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main               # http://localhost:5050 (documentação em /docs)
```

Interface, em outro terminal, dentro de `frontend/agenda`:

```bash
npm install                      # só na primeira vez
npm run dev                      # http://localhost:5173
```

Abra `http://localhost:5173` no navegador. O backend precisa estar rodando antes; se ele cair, a página avisa e volta sozinha quando ele voltar.

Os eventos ficam em `backend/agenda.db`. Para começar com a agenda vazia, pare o backend e apague esse arquivo. Para usar outro arquivo, defina a variável `AGENDA_DB` antes de subir (`AGENDA_DB=/tmp/teste.db python -m app.main`; no Windows, rode esse comando no Git Bash).

## Rodando em várias máquinas

1. Escolha uma máquina para ser o servidor e suba o backend e a interface nela, como acima.
2. O Vite mostra o endereço de rede no terminal (`Network: http://172.20.5.62:5173/`, por exemplo).
3. Nas outras máquinas, abra esse endereço no navegador. Não precisa instalar nada nelas.

Cada requisição aparece no terminal do backend com o IP de quem pediu (`cliente=172.22.41.105:0`). Como as requisições passam pelo Vite, o uvicorn não recebe a porta do cliente, só o IP, e por isso ela aparece como `0`.

No laboratório do CIn, a rede cabeada não consegue abrir conexão com aparelhos no Wi-Fi, mas o contrário funciona. Então o servidor tem que ser uma máquina **cabeada**, e os notebooks no Wi-Fi entram como clientes. Se o navegador de outra máquina der timeout, confira isso e o firewall da máquina servidor; se der "conexão recusada", o backend não está rodando nela.

## Demonstrando o conflito de edição

1. Abra a agenda em duas janelas (ou em duas máquinas) e crie um evento.
2. Nas duas, clique em editar o mesmo evento.
3. Na primeira, mude o título e salve.
4. Na segunda, mude outra coisa e salve. O servidor responde 412 e a janela mostra o aviso "Outra pessoa salvou este evento antes de você", com o botão **Recarregar evento**.
5. Recarregue: o formulário passa a mostrar a versão nova, e aí dá para salvar.

Outras coisas para mostrar:

- Duas janelas criando evento no mesmo horário: a segunda recebe o aviso de horário ocupado (409) no campo de início.
- Um evento criado numa janela aparece destacado na outra em até 3 segundos.
- Parar o backend: as janelas mostram "Sem conexão com o servidor". Ao subir de novo, elas voltam sozinhas, com os eventos intactos.

## Estado e persistência

O backend guarda os eventos em memória, num objeto `Agenda`, em duas estruturas:

```python
_eventos:  dict[int, Evento]                       # id -> evento
_por_data: dict[date, list[tuple[int, int, int]]]  # data -> [(inicio, fim, id)] ordenada pelo início
```

Cada evento tem `id`, `titulo`, `data`, `hora`, `duracao` (em minutos), `descricao` e `versao`. A versão começa em 1, aumenta a cada alteração e é mandada para o cliente no cabeçalho `ETag`.

O `_por_data` serve para achar conflito de horário rápido. Como a agenda nunca aceita dois eventos sobrepostos, a lista de um dia ordenada pelo início acaba ordenada pelo fim também. Então é só fazer uma busca binária para saber onde o evento novo entraria e comparar com o evento anterior e o seguinte, sem percorrer o dia todo. Para isso dar certo, o evento tem que terminar no mesmo dia (até 24:00).

Toda criação, edição e remoção também é gravada no SQLite, dentro do mesmo lock. Quando o servidor sobe, ele lê tudo do banco e monta as duas estruturas de novo. O próximo id também fica salvo, para um id de evento removido não ser reaproveitado.

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

## Testes

Dentro de `backend`, com o ambiente ativado:

```bash
python -m pytest
```

São 44 testes: validações, conflito de horário, PATCH e DELETE com `If-Match`, persistência depois de reiniciar, 50 criações simultâneas no mesmo horário e duas edições simultâneas na mesma versão.

O teste de carga e de robustez roda contra um servidor já ligado. Ele cria muitos eventos, então vale subir o backend com um banco separado:

```bash
AGENDA_DB=/tmp/teste.db python -m app.main     # num terminal, dentro de backend
python scripts/carga.py http://localhost:5050   # em outro, na raiz do projeto
```

Para testar pelo mesmo caminho da interface, use `http://localhost:5173/api`. Ele simula:

- 50 clientes criando no mesmo horário ao mesmo tempo;
- 30 clientes editando a mesma versão de um evento;
- 10 clientes disputando os mesmos 3 eventos por 10 segundos;
- 20 clientes que caem no meio do envio e 30 que conectam e ficam travados, enquanto outros usam a agenda;
- 20 clientes fazendo 1.000 requisições.

No fim, ele confere que não sobrou nenhum evento sobreposto nem id repetido. Uma rodada pela interface (porta 5173) num notebook deu:

| Cenário | Resultado |
|---|---|
| 50 criações no mesmo horário | 1 com 201, 49 com 409 |
| 30 edições na mesma versão | 1 com 200, 29 com 412, versão final 2 |
| 10 clientes disputando 3 eventos por 10 s | 1.255 edições aceitas, 2.248 com 412, nenhuma edição perdida |
| 20 clientes caindo e 30 travados | os outros clientes continuaram respondendo em até 5 ms |
| 20 clientes, 1.000 requisições | 2,2 s (cerca de 450 por segundo), mediana de 42 ms, 95% abaixo de 64 ms, nenhuma falha |
| Agenda no fim | nenhuma sobreposição, nenhum id repetido |

## Limitações

- Existe um servidor só. O lock vale dentro de um processo; duas instâncias do backend teriam agendas diferentes.
- Não há login: qualquer cliente edita qualquer evento. Segurança ficou fora do escopo da disciplina.
