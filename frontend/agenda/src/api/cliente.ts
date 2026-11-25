import type { DetalheErro, Evento, EventoEntrada, EventoParcial } from "./tipos";

export const URL_API: string = import.meta.env.VITE_API_URL ?? "http://localhost:5050";
const TEMPO_LIMITE_MS = 8000;

/**
 * Erro único para tudo que pode dar errado numa chamada.
 * status 0 significa que nem chegou resposta (servidor fora do ar, rede, timeout).
 */
export class ErroApi extends Error {
  status: number;
  detalhes: DetalheErro[];

  constructor(status: number, mensagem: string, detalhes: DetalheErro[] = []) {
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
    this.detalhes = detalhes;
  }

  get semConexao() {
    return this.status === 0;
  }
}

async function requisicao<T>(caminho: string, init: RequestInit = {}): Promise<T> {
  // AbortController cancela a requisição se o servidor demorar demais,
  // para a tela não ficar "carregando" para sempre.
  const controle = new AbortController();
  const timer = setTimeout(() => controle.abort(), TEMPO_LIMITE_MS);
  let resposta: Response;
  try {
    resposta = await fetch(`${URL_API}${caminho}`, {
      ...init,
      signal: controle.signal,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    // fetch só lança exceção quando não há resposta HTTP nenhuma
    // (servidor desligado, CORS bloqueado, timeout).
    throw new ErroApi(0, `Não foi possível conectar ao servidor em ${URL_API}.`);
  } finally {
    clearTimeout(timer);
  }

  if (!resposta.ok) {
    // A API sempre devolve {"erro": "...", "detalhes"?: [...]} nos erros.
    let corpo: { erro?: string; detalhes?: DetalheErro[] } = {};
    try {
      corpo = await resposta.json();
    } catch {
      /* corpo vazio ou não JSON */
    }
    throw new ErroApi(resposta.status, corpo.erro ?? `Erro ${resposta.status}`, corpo.detalhes ?? []);
  }

  return resposta.status === 204 ? (undefined as T) : ((await resposta.json()) as T);
}

/**
 * A versão também vem no ETag ("3", com aspas), mas como o corpo já traz
 * `versao`, usamos o corpo. O If-Match precisa ir no formato do ETag.
 */
const ifMatch = (versao: number) => ({ "If-Match": `"${versao}"` });

export const api = {
  listar: () => requisicao<Evento[]>("/eventos"),

  obter: (id: number) => requisicao<Evento>(`/eventos/${id}`),

  criar: (evento: EventoEntrada) =>
    requisicao<Evento>("/eventos", { method: "POST", body: JSON.stringify(evento) }),

  atualizar: (id: number, versao: number, campos: EventoParcial) =>
    requisicao<Evento>(`/eventos/${id}`, {
      method: "PATCH",
      headers: ifMatch(versao),
      body: JSON.stringify(campos),
    }),

  remover: (id: number, versao: number) =>
    requisicao<void>(`/eventos/${id}`, { method: "DELETE", headers: ifMatch(versao) }),
};
