import { useCallback, useState } from "react";
import { Alert, App, Button, Segmented } from "antd";
import { CalendarOutlined, PlusOutlined, UnorderedListOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { ErroApi, URL_API } from "./api/cliente";
import type { Evento } from "./api/tipos";
import { FormularioEvento } from "./components/FormularioEvento";
import { VisaoCalendario } from "./components/VisaoCalendario";
import { VisaoLista } from "./components/VisaoLista";
import { INTERVALO_POLLING_MS, useEventos, type EstadoConexao, type MudancaRemota } from "./hooks/useEventos";

type Visao = "calendario" | "lista";

export function Agenda() {
  const { message, notification } = App.useApp();
  const [visao, setVisao] = useState<Visao>("calendario");
  const [diaSelecionado, setDiaSelecionado] = useState<Dayjs>(dayjs());
  const [modal, setModal] = useState<{ aberto: boolean; evento: Evento | null; dia: Dayjs }>({
    aberto: false,
    evento: null,
    dia: dayjs(),
  });

  const avisarMudancaRemota = useCallback(
    (m: MudancaRemota) => {
      const linhas = [
        ...m.criados.map((e) => `Criado: ${e.titulo} (${dayjs(e.data).format("DD/MM")} ${e.hora})`),
        ...m.alterados.map((e) => `Alterado: ${e.titulo} (agora na versão ${e.versao})`),
        ...m.removidos.map((e) => `Removido: ${e.titulo}`),
      ];
      notification.info({
        key: "mudanca-remota",
        message: "Outra pessoa alterou a agenda",
        description: (
          <ul className="lista-notificacao">
            {linhas.slice(0, 5).map((l) => (
              <li key={l}>{l}</li>
            ))}
            {linhas.length > 5 && <li>e mais {linhas.length - 5}</li>}
          </ul>
        ),
        placement: "bottomRight",
        duration: 5,
      });
    },
    [notification],
  );

  const agenda = useEventos(avisarMudancaRemota);

  const abrirNovo = (dia: Dayjs) => setModal({ aberto: true, evento: null, dia });
  const abrirEdicao = (evento: Evento) => setModal({ aberto: true, evento, dia: dayjs(evento.data) });
  const fechar = () => setModal((m) => ({ ...m, aberto: false }));

  async function removerDaLista(evento: Evento) {
    try {
      await agenda.remover(evento);
      message.success(`Evento "${evento.titulo}" removido.`);
    } catch (e) {
      if (!(e instanceof ErroApi)) throw e;
      if (e.status === 412) {
        message.warning("Este evento foi alterado por outra pessoa depois que você o viu. A agenda foi atualizada; confira antes de remover.");
      } else if (e.status === 404) {
        message.info("Este evento já tinha sido removido por outra pessoa.");
      } else {
        message.error(e.message);
      }
      if (!e.semConexao) agenda.sincronizar().catch(() => undefined);
    }
  }

  const versaoNoServidor = modal.evento ? agenda.eventos.find((e) => e.id === modal.evento!.id)?.versao : undefined;

  return (
    <div className="pagina">
      <header className="cabecalho">
        <div className="cabecalho-titulo">
          <h1>Agenda compartilhada</h1>
          <IndicadorConexao conexao={agenda.conexao} ultima={agenda.ultimaSincronizacao} />
        </div>
        <div className="cabecalho-acoes">
          <Segmented<Visao>
            value={visao}
            onChange={setVisao}
            options={[
              { label: "Calendário", value: "calendario", icon: <CalendarOutlined /> },
              { label: "Lista", value: "lista", icon: <UnorderedListOutlined /> },
            ]}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => abrirNovo(diaSelecionado)}>
            Novo evento
          </Button>
        </div>
      </header>

      {agenda.conexao === "offline" && (
        <Alert
          className="faixa-offline"
          type="error"
          showIcon
          message="Sem conexão com o servidor"
          description={
            <>
              Não foi possível falar com {URL_API}. Verifique se o backend está rodando.
              {agenda.ultimaSincronizacao
                ? ` A tela mostra os dados de ${dayjs(agenda.ultimaSincronizacao).format("HH:mm:ss")}.`
                : ""}{" "}
              Tentando de novo a cada {INTERVALO_POLLING_MS / 1000} s.
            </>
          }
        />
      )}

      <main>
        {visao === "calendario" ? (
          <VisaoCalendario
            eventos={agenda.eventos}
            destacados={agenda.destacados}
            diaSelecionado={diaSelecionado}
            onSelecionarDia={setDiaSelecionado}
            onAbrir={abrirEdicao}
            onNovo={abrirNovo}
          />
        ) : (
          <VisaoLista
            eventos={agenda.eventos}
            destacados={agenda.destacados}
            carregando={agenda.conexao === "conectando"}
            onAbrir={abrirEdicao}
            onRemover={removerDaLista}
          />
        )}
      </main>

      <FormularioEvento
        aberto={modal.aberto}
        evento={modal.evento}
        dataSugerida={modal.dia}
        versaoNoServidor={versaoNoServidor}
        onCriar={agenda.criar}
        onAtualizar={agenda.atualizar}
        onRemover={agenda.remover}
        onFechar={fechar}
        onRessincronizar={() => agenda.sincronizar().catch(() => undefined)}
      />
    </div>
  );
}

function IndicadorConexao({ conexao, ultima }: { conexao: EstadoConexao; ultima: Date | null }) {
  const texto =
    conexao === "online"
      ? `Sincronizado às ${dayjs(ultima).format("HH:mm:ss")}`
      : conexao === "offline"
        ? "Sem conexão"
        : "Conectando ao servidor…";
  return (
    <span className={`indicador indicador-${conexao}`} role="status" aria-live="polite">
      <span className="indicador-ponto" aria-hidden />
      {texto}
    </span>
  );
}
