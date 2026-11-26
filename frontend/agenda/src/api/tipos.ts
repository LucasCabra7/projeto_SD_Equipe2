
export interface Evento {
  id: number;
  titulo: string;
  data: string;
  hora: string;
  duracao: number;
  descricao: string | null;
  versao: number;
}

export type EventoEntrada = Omit<Evento, "id" | "versao">;

export type EventoParcial = Partial<EventoEntrada>;

export interface DetalheErro {
  campo: string;
  mensagem: string;
}
