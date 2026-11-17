# Diagramas de negócio da agenda compartilhada (Equipe 02)

Estes diagramas mostram as regras de negócio da agenda: como um evento é criado e como fica a edição e a remoção que vão entrar na Entrega 2. Em todos eles, do momento em que o lock é adquirido até a resposta, nenhuma outra requisição mexe na agenda. Qualquer saída depois desse ponto (sucesso ou erro) libera o lock.

## Criar evento (`POST /eventos`)

Antes de qualquer coisa o Pydantic valida o formato. Só depois o servidor pega o lock e procura conflito de horário naquele dia. Assim, se duas pessoas tentam o mesmo horário ao mesmo tempo, a segunda já encontra o evento da primeira gravado e recebe 409.

```mermaid
flowchart TD
    inicio(["POST /eventos"]) --> validar{"Formato válido?"}
    validar -- não --> r422["422 dados invalidos"]
    validar -- sim --> lock["Adquire o lock"]
    lock --> conflito{"Conflito de horário no dia?"}
    conflito -- sim --> r409["409 conflito de horario"]
    conflito -- não --> grava["Gera o id e grava com versão 1"]
    grava --> r201(["201 com Location e ETag 1"])
```

## Editar ou remover evento (Entrega 2)

O `If-Match` é conferido antes do lock porque não depende do estado da agenda. No `PATCH`, o intervalo antigo do evento sai do índice antes da busca por conflito. Se não fosse assim, o evento conflitaria com ele mesmo ao mudar só um pouco de horário. Se der conflito, o intervalo antigo volta para o índice e nada muda.

```mermaid
flowchart TD
    inicio(["PATCH ou DELETE /eventos/id"]) --> ifmatch{"Tem If-Match?"}
    ifmatch -- não --> r428["428 If-Match obrigatorio"]
    ifmatch -- sim --> lock["Adquire o lock"]
    lock --> existe{"Evento existe?"}
    existe -- não --> r404["404 nao encontrado"]
    existe -- sim --> versao{"Versão bate?"}
    versao -- não --> r412["412 versao mudou"]
    versao -- "sim, DELETE" --> r204(["Remove o evento e o intervalo, responde 204"])
    versao -- "sim, PATCH" --> conflito{"Sem o intervalo antigo, o novo horário conflita?"}
    conflito -- sim --> r409["Devolve o intervalo antigo e responde 409"]
    conflito -- não --> r200(["Aplica, soma 1 na versão e responde 200 com novo ETag"])
```

## Exemplo: Ana e Bruno editando o mesmo evento

É o caso que o lock sozinho não resolve, porque entre ler e salvar passa tempo e cada passo é uma requisição separada. Os dois leem a versão 1. Ana salva primeiro, e o evento passa para a versão 2. Quando Bruno tenta salvar em cima da versão 1, recebe 412 em vez de apagar a alteração da Ana sem saber. Ele relê o evento e tenta de novo.

```mermaid
sequenceDiagram
    participant Ana
    participant Bruno
    participant API as Servidor
    Ana->>API: GET /eventos/1
    API-->>Ana: 200, ETag "1"
    Bruno->>API: GET /eventos/1
    API-->>Bruno: 200, ETag "1"
    Ana->>API: PATCH /eventos/1 com If-Match "1"
    API-->>Ana: 200, versao 2, ETag "2"
    Bruno->>API: PATCH /eventos/1 com If-Match "1"
    API-->>Bruno: 412, a versao mudou
    Bruno->>API: GET /eventos/1
    API-->>Bruno: 200, ETag "2" (já com a mudança da Ana)
    Bruno->>API: PATCH /eventos/1 com If-Match "2"
    API-->>Bruno: 200, versao 3, ETag "3"
```