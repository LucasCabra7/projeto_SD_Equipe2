import { useMemo } from "react";
import { Button, Calendar, Empty, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { Dayjs } from "dayjs";
import type { Evento } from "../api/tipos";
import { dataLonga, duracaoLegivel, intervalo } from "../util";

interface Props {
  eventos: Evento[];
  destacados: Set<number>;
  diaSelecionado: Dayjs;
  onSelecionarDia: (dia: Dayjs) => void;
  onAbrir: (evento: Evento) => void;
  onNovo: (dia: Dayjs) => void;
}

export function VisaoCalendario({
  eventos,
  destacados,
  diaSelecionado,
  onSelecionarDia,
  onAbrir,
  onNovo,
}: Props) {
  const porDia = useMemo(() => {
    const mapa = new Map<string, Evento[]>();
    for (const e of eventos) mapa.set(e.data, [...(mapa.get(e.data) ?? []), e]);
    return mapa;
  }, [eventos]);

  const chaveDia = diaSelecionado.format("YYYY-MM-DD");
  const doDia = porDia.get(chaveDia) ?? [];

  return (
    <div className="calendario-layout">
      <Calendar
        className="calendario"
        value={diaSelecionado}
        onSelect={(dia) => onSelecionarDia(dia)}
        cellRender={(dia, info) => {
          if (info.type !== "date") return info.originNode;
          const lista = porDia.get(dia.format("YYYY-MM-DD")) ?? [];
          if (lista.length === 0) return null;
          return (
            <ul className="celula-eventos">
              {lista.slice(0, 3).map((e) => (
                <li
                  key={e.id}
                  className={
                    destacados.has(e.id)
                      ? "celula-evento destacado"
                      : "celula-evento"
                  }
                >
                  <span className="celula-hora">{e.hora}</span> {e.titulo}
                </li>
              ))}
              {lista.length > 3 && (
                <li className="celula-mais">+{lista.length - 3}</li>
              )}
            </ul>
          );
        }}
      />

      <aside className="painel-dia" aria-label="Eventos do dia selecionado">
        <header className="painel-dia-cabecalho">
          <h2>{dataLonga(chaveDia)}</h2>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => onNovo(diaSelecionado)}
          >
            Novo evento
          </Button>
        </header>
        {doDia.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="Nenhum evento neste dia"
          />
        ) : (
          <ol className="lista-dia">
            {doDia.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  className={
                    destacados.has(e.id) ? "item-dia destacado" : "item-dia"
                  }
                  onClick={() => onAbrir(e)}
                >
                  <span className="item-dia-hora">{intervalo(e)}</span>
                  <span className="item-dia-titulo">{e.titulo}</span>
                  <span className="item-dia-meta">
                    {duracaoLegivel(e.duracao)}
                    <Tag bordered={false}>v{e.versao}</Tag>
                  </span>
                  {e.descricao && (
                    <span className="item-dia-descricao">{e.descricao}</span>
                  )}
                </button>
              </li>
            ))}
          </ol>
        )}
      </aside>
    </div>
  );
}
