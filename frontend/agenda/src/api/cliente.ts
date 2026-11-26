import type { DetalheErro, Evento, EventoEntrada, EventoParcial } from "./tipos";

export const URL_API: string = import.meta.env.VITE_API_URL ?? "/api";
const TEMPO_LIMITE_MS = 8000;

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
    throw new ErroApi(0, `Não foi possível conectar ao servidor em ${URL_API}.`);
  } finally {
    clearTimeout(timer);
  }

  if (resposta.status === 502) {
    throw new ErroApi(0, `Não foi possível conectar ao servidor em ${URL_API}.`);
  }

  if (!resposta.ok) {
    const corpo: { erro?: string; detalhes?: DetalheErro[] } = await resposta.json().catch(() => ({}));
    throw new ErroApi(resposta.status, corpo.erro ?? `Erro ${resposta.status}`, corpo.detalhes ?? []);
  }

  return resposta.status === 204 ? (undefined as T) : ((await resposta.json()) as T);
}

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
