// Espelha o contrato da API (docs/contrato-api.md).

export interface Evento {
  id: number;
  titulo: string;
  data: string; // AAAA-MM-DD
  hora: string; // HH:MM
  duracao: number; // minutos
  descricao: string | null;
  versao: number;
}

/** Corpo do POST /eventos (id e versao são gerados pelo servidor). */
export type EventoEntrada = Omit<Evento, "id" | "versao">;

/** Corpo do PATCH /eventos/{id}: só os campos que mudaram. */
export type EventoParcial = Partial<EventoEntrada>;

export interface DetalheErro {
  campo: string;
  mensagem: string;
}
