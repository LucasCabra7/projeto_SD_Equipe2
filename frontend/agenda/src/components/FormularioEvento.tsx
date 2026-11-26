import { useEffect, useState } from "react";
import { Alert, App, Button, DatePicker, Form, Input, InputNumber, Modal, Popconfirm, Space, TimePicker } from "antd";
import { DeleteOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { api, ErroApi } from "../api/cliente";
import type { Evento, EventoEntrada, EventoParcial } from "../api/tipos";

interface ValoresFormulario {
  titulo: string;
  data: Dayjs;
  hora: Dayjs;
  duracao: number;
  descricao?: string;
}

type Problema =
  | { tipo: "versao" }
  | { tipo: "removido" }
  | { tipo: "geral"; mensagem: string; titulo: string };

interface Props {
  aberto: boolean;
  evento: Evento | null;
  dataSugerida: Dayjs;
  versaoNoServidor: number | undefined;
  onCriar: (dados: EventoEntrada) => Promise<Evento>;
  onAtualizar: (id: number, versao: number, campos: EventoParcial) => Promise<Evento>;
  onRemover: (evento: Evento) => Promise<void>;
  onFechar: () => void;
  onRessincronizar: () => void;
}

const CAMPOS = ["titulo", "data", "hora", "duracao", "descricao"] as const;

function paraFormulario(e: Evento): ValoresFormulario {
  return {
    titulo: e.titulo,
    data: dayjs(e.data),
    hora: dayjs(e.hora, "HH:mm"),
    duracao: e.duracao,
    descricao: e.descricao ?? undefined,
  };
}

function paraApi(v: ValoresFormulario): EventoEntrada {
  return {
    titulo: v.titulo.trim(),
    data: v.data.format("YYYY-MM-DD"),
    hora: v.hora.format("HH:mm"),
    duracao: v.duracao,
    descricao: v.descricao?.trim() || null,
  };
}

function diferenca(base: Evento, novo: EventoEntrada): EventoParcial {
  const campos: EventoParcial = {};
  for (const c of CAMPOS) {
    if (novo[c] !== base[c]) (campos as Record<string, unknown>)[c] = novo[c];
  }
  return campos;
}

export function FormularioEvento(props: Props) {
  const { aberto, evento, dataSugerida, versaoNoServidor } = props;
  const [form] = Form.useForm<ValoresFormulario>();
  const { message } = App.useApp();
  const [base, setBase] = useState<Evento | null>(null);
  const [problema, setProblema] = useState<Problema | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [recarregando, setRecarregando] = useState(false);
  const editando = evento !== null;

  useEffect(() => {
    if (!aberto) return;
    setProblema(null);
    setBase(evento);
    form.resetFields();
    form.setFieldsValue(
      evento ? paraFormulario(evento) : { data: dataSugerida, hora: dayjs("09:00", "HH:mm"), duracao: 60 },
    );
  }, [aberto, evento]);

  const desatualizadoNoServidor =
    editando && base !== null && problema === null && versaoNoServidor !== undefined && versaoNoServidor > base.versao;
  const sumiuDoServidor = editando && problema === null && versaoNoServidor === undefined;

  function tratarErro(e: unknown) {
    if (!(e instanceof ErroApi)) {
      setProblema({ tipo: "geral", titulo: "Erro inesperado", mensagem: String(e) });
      return;
    }
    switch (e.status) {
      case 0:
        setProblema({
          tipo: "geral",
          titulo: "Sem conexão com o servidor",
          mensagem: `${e.message} Seus dados continuam no formulário; tente salvar de novo quando o servidor voltar.`,
        });
        return;
      case 412:
        setProblema({ tipo: "versao" });
        props.onRessincronizar();
        return;
      case 404:
        setProblema({ tipo: "removido" });
        props.onRessincronizar();
        return;
      case 409:
        form.setFields([{ name: "hora", errors: ["Horário ocupado por outro evento"] }]);
        setProblema({ tipo: "geral", titulo: "Horário em conflito", mensagem: e.message });
        return;
      case 422: {
        const nosCampos = e.detalhes.filter((d) => (CAMPOS as readonly string[]).includes(d.campo));
        form.setFields(nosCampos.map((d) => ({ name: d.campo as keyof ValoresFormulario, errors: [d.mensagem] })));
        const gerais = e.detalhes.filter((d) => !(CAMPOS as readonly string[]).includes(d.campo)).map((d) => d.mensagem);
        const texto = gerais.length ? gerais.join("; ") : e.detalhes.length ? "" : e.message;
        if (texto.includes("24:00"))
          form.setFields([{ name: "duracao", errors: ["Termina depois das 24:00. Reduza a duração ou antecipe o início."] }]);
        setProblema({
          tipo: "geral",
          titulo: "O servidor recusou os dados",
          mensagem: texto || "Corrija os campos destacados.",
        });
        return;
      }
      default:
        setProblema({ tipo: "geral", titulo: `Erro ${e.status}`, mensagem: e.message });
    }
  }

  async function salvar(valores: ValoresFormulario) {
    setProblema(null);
    const dados = paraApi(valores);
    setSalvando(true);
    try {
      if (!base) {
        const criado = await props.onCriar(dados);
        message.success(`Evento "${criado.titulo}" criado.`);
      } else {
        const campos = diferenca(base, dados);
        if (Object.keys(campos).length === 0) {
          message.info("Nada foi alterado.");
          props.onFechar();
          return;
        }
        const salvo = await props.onAtualizar(base.id, base.versao, campos);
        message.success(`Alterações salvas (versão ${salvo.versao}).`);
      }
      props.onFechar();
    } catch (e) {
      tratarErro(e);
    } finally {
      setSalvando(false);
    }
  }

  async function recarregar() {
    if (!base) return;
    setRecarregando(true);
    try {
      const atual = await api.obter(base.id);
      setBase(atual);
      form.resetFields();
      form.setFieldsValue(paraFormulario(atual));
      setProblema(null);
      message.info(`Evento recarregado na versão ${atual.versao}. Refaça sua alteração se ainda fizer sentido.`);
    } catch (e) {
      tratarErro(e);
    } finally {
      setRecarregando(false);
    }
  }

  async function remover() {
    if (!base) return;
    try {
      await props.onRemover(base);
      message.success(`Evento "${base.titulo}" removido.`);
      props.onFechar();
    } catch (e) {
      tratarErro(e);
    }
  }

  const bloqueado = problema?.tipo === "removido";

  return (
    <Modal
      open={aberto}
      title={editando ? `Editar evento (versão ${base?.versao ?? evento?.versao})` : "Novo evento"}
      onCancel={props.onFechar}
      destroyOnClose
      width={520}
      footer={
        <div className="rodape-modal">
          {editando && !bloqueado ? (
            <Popconfirm
              title="Remover este evento?"
              description="Outras pessoas também deixarão de vê-lo."
              okText="Remover"
              okButtonProps={{ danger: true }}
              cancelText="Cancelar"
              onConfirm={remover}
            >
              <Button danger icon={<DeleteOutlined />}>
                Remover
              </Button>
            </Popconfirm>
          ) : (
            <span />
          )}
          <Space>
            <Button onClick={props.onFechar}>{bloqueado ? "Fechar" : "Cancelar"}</Button>
            {!bloqueado && (
              <Button type="primary" loading={salvando} onClick={() => form.submit()}>
                {editando ? "Salvar alterações" : "Criar evento"}
              </Button>
            )}
          </Space>
        </div>
      }
    >
      {problema?.tipo === "versao" && (
        <Alert
          className="aviso-modal"
          type="warning"
          showIcon
          message="Outra pessoa salvou este evento antes de você"
          description="O servidor recusou sua alteração para não apagar a dela (resposta 412). Recarregue para ver a versão atual; o que você digitou será substituído."
          action={
            <Button size="small" icon={<ReloadOutlined />} loading={recarregando} onClick={recarregar}>
              Recarregar evento
            </Button>
          }
        />
      )}
      {problema?.tipo === "removido" && (
        <Alert
          className="aviso-modal"
          type="error"
          showIcon
          message="Este evento foi removido por outra pessoa"
          description="Não há mais o que salvar. Feche o formulário; a agenda já foi atualizada."
        />
      )}
      {problema?.tipo === "geral" && (
        <Alert className="aviso-modal" type="error" showIcon message={problema.titulo} description={problema.mensagem} />
      )}
      {desatualizadoNoServidor && (
        <Alert
          className="aviso-modal"
          type="info"
          showIcon
          message={`Este evento mudou no servidor (agora está na versão ${versaoNoServidor})`}
          description="Se você salvar, o servidor vai recusar. Recarregue para editar a partir da versão atual."
          action={
            <Button size="small" loading={recarregando} onClick={recarregar}>
              Recarregar
            </Button>
          }
        />
      )}
      {sumiuDoServidor && (
        <Alert className="aviso-modal" type="info" showIcon message="Este evento parece ter sido removido por outra pessoa." />
      )}

      <Form<ValoresFormulario>
        form={form}
        layout="vertical"
        onFinish={salvar}
        disabled={bloqueado}
        requiredMark="optional"
      >
        <Form.Item
          name="titulo"
          label="Título"
          rules={[
            { required: true, whitespace: true, message: "Informe um título" },
            { max: 100, message: "Máximo de 100 caracteres" },
          ]}
        >
          <Input placeholder="Ex.: Reunião do grupo" autoFocus />
        </Form.Item>
        <div className="linha-campos">
          <Form.Item name="data" label="Data" rules={[{ required: true, message: "Escolha a data" }]}>
            <DatePicker format="DD/MM/YYYY" allowClear={false} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="hora" label="Início" rules={[{ required: true, message: "Escolha a hora" }]}>
            <TimePicker format="HH:mm" allowClear={false} style={{ width: "100%" }} needConfirm={false} />
          </Form.Item>
          <Form.Item name="duracao" label="Duração (min)" rules={[{ required: true, message: "Informe a duração" }]}>
            <InputNumber min={1} max={1440} precision={0} style={{ width: "100%" }} />
          </Form.Item>
        </div>
        <Form.Item name="descricao" label="Descrição" rules={[{ max: 500, message: "Máximo de 500 caracteres" }]}>
          <Input.TextArea rows={3} showCount maxLength={500} placeholder="Opcional" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
