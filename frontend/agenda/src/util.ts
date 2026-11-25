import dayjs from "dayjs";
import type { Evento } from "./api/tipos";

/** "14:00–15:30" a partir de hora + duração. */
export function intervalo(e: Pick<Evento, "hora" | "duracao">): string {
  const [h, m] = e.hora.split(":").map(Number);
  const fim = h * 60 + m + e.duracao;
  const hh = String(Math.floor(fim / 60)).padStart(2, "0");
  const mm = String(fim % 60).padStart(2, "0");
  return `${e.hora}–${hh}:${mm}`;
}

export function dataLonga(data: string): string {
  return dayjs(data).format("dddd, D [de] MMMM");
}

export function duracaoLegivel(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const r = min % 60;
  return r ? `${h} h ${r} min` : `${h} h`;
}
