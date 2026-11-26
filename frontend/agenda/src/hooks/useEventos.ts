import { useCallback, useEffect, useRef, useState } from "react";
import { api, ErroApi } from "../api/cliente";
import type { Evento, EventoEntrada, EventoParcial } from "../api/tipos";

export const INTERVALO_POLLING_MS = 3000;
const DESTAQUE_MS = 4000;

export interface MudancaRemota {
  criados: Evento[];
  alterados: Evento[];
  removidos: Evento[];
}

export type EstadoConexao = "conectando" | "online" | "offline";

export function useEventos(aoMudarRemotamente: (m: MudancaRemota) => void) {
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [conexao, setConexao] = useState<EstadoConexao>("conectando");
  const [ultimaSincronizacao, setUltimaSincronizacao] = useState<Date | null>(null);
  const [destacados, setDestacados] = useState<Set<number>>(new Set());

  const conhecidosRef = useRef<Map<number, Evento> | null>(null);
  const geracaoRef = useRef(0);
  const callbackRef = useRef(aoMudarRemotamente);
  callbackRef.current = aoMudarRemotamente;

  const definir = useCallback((lista: Evento[]) => {
    conhecidosRef.current = new Map(lista.map((e) => [e.id, e]));
    setEventos(lista);
  }, []);

  const destacar = useCallback((ids: number[]) => {
    if (ids.length === 0) return;
    setDestacados((atual) => new Set([...atual, ...ids]));
    setTimeout(() => {
      setDestacados((atual) => {
        const novo = new Set(atual);
        ids.forEach((id) => novo.delete(id));
        return novo;
      });
    }, DESTAQUE_MS);
  }, []);

  const sincronizar = useCallback(async () => {
    const geracao = geracaoRef.current;
    try {
      const lista = await api.listar();
      if (geracao !== geracaoRef.current) return;
      const anteriores = conhecidosRef.current;
      if (anteriores) {
        const mudanca = comparar(anteriores, lista);
        const total = mudanca.criados.length + mudanca.alterados.length + mudanca.removidos.length;
        if (total > 0) {
          callbackRef.current(mudanca);
          destacar([...mudanca.criados, ...mudanca.alterados].map((e) => e.id));
        }
      }
      definir(lista);
      setConexao("online");
      setUltimaSincronizacao(new Date());
    } catch (e) {
      if (e instanceof ErroApi && e.semConexao) setConexao("offline");
      else throw e;
    }
  }, [definir, destacar]);

  useEffect(() => {
    let ativo = true;
    let timer: ReturnType<typeof setTimeout>;
    const ciclo = async () => {
      await sincronizar().catch(() => undefined);
      if (ativo) timer = setTimeout(ciclo, INTERVALO_POLLING_MS);
    };
    ciclo();
    const aoFocar = () => document.visibilityState === "visible" && sincronizar().catch(() => undefined);
    document.addEventListener("visibilitychange", aoFocar);
    return () => {
      ativo = false;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", aoFocar);
    };
  }, [sincronizar]);

  const aplicarLocal = useCallback(
    (transformar: (lista: Evento[]) => Evento[]) => {
      geracaoRef.current += 1;
      definir(ordenar(transformar([...(conhecidosRef.current?.values() ?? [])])));
    },
    [definir],
  );

  const criar = useCallback(
    async (dados: EventoEntrada) => {
      const evento = await api.criar(dados);
      aplicarLocal((lista) => [...lista, evento]);
      return evento;
    },
    [aplicarLocal],
  );

  const atualizar = useCallback(
    async (id: number, versao: number, campos: EventoParcial) => {
      const evento = await api.atualizar(id, versao, campos);
      aplicarLocal((lista) => lista.map((e) => (e.id === id ? evento : e)));
      return evento;
    },
    [aplicarLocal],
  );

  const remover = useCallback(
    async (evento: Evento) => {
      await api.remover(evento.id, evento.versao);
      aplicarLocal((lista) => lista.filter((e) => e.id !== evento.id));
    },
    [aplicarLocal],
  );

  return { eventos, conexao, ultimaSincronizacao, destacados, sincronizar, criar, atualizar, remover };
}

function comparar(anteriores: Map<number, Evento>, atuais: Evento[]): MudancaRemota {
  const mudanca: MudancaRemota = { criados: [], alterados: [], removidos: [] };
  const idsAtuais = new Set<number>();
  for (const e of atuais) {
    idsAtuais.add(e.id);
    const antes = anteriores.get(e.id);
    if (!antes) mudanca.criados.push(e);
    else if (antes.versao !== e.versao) mudanca.alterados.push(e);
  }
  for (const [id, e] of anteriores) if (!idsAtuais.has(id)) mudanca.removidos.push(e);
  return mudanca;
}

function ordenar(lista: Evento[]) {
  return lista.sort((a, b) => (a.data + a.hora).localeCompare(b.data + b.hora));
}
