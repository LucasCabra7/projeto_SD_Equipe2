import { Button, Empty, Popconfirm, Space, Table, Tag, Tooltip } from "antd";
import { DeleteOutlined, EditOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { Evento } from "../api/tipos";
import { duracaoLegivel, intervalo } from "../util";

interface Props {
  eventos: Evento[];
  destacados: Set<number>;
  carregando: boolean;
  onAbrir: (evento: Evento) => void;
  onRemover: (evento: Evento) => void;
}

export function VisaoLista({ eventos, destacados, carregando, onAbrir, onRemover }: Props) {
  return (
    <Table<Evento>
      rowKey="id"
      dataSource={eventos}
      loading={carregando}
      pagination={{ pageSize: 10, hideOnSinglePage: true }}
      scroll={{ x: 720 }}
      rowClassName={(e) => (destacados.has(e.id) ? "linha destacado" : "linha")}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="A agenda está vazia" /> }}
      columns={[
        {
          title: "Data",
          dataIndex: "data",
          width: 150,
          render: (d: string) => dayjs(d).format("ddd, DD/MM/YYYY"),
        },
        { title: "Horário", key: "horario", width: 120, render: (_, e) => intervalo(e) },
        { title: "Título", dataIndex: "titulo", ellipsis: true },
        {
          title: "Duração",
          dataIndex: "duracao",
          width: 110,
          render: (m: number) => duracaoLegivel(m),
        },
        {
          title: "Descrição",
          dataIndex: "descricao",
          ellipsis: true,
          render: (d: string | null) => d ?? <span className="texto-apagado">sem descrição</span>,
        },
        {
          title: (
            <Tooltip title="Sobe a cada alteração. É o valor enviado no If-Match.">
              <span>Versão</span>
            </Tooltip>
          ),
          dataIndex: "versao",
          width: 90,
          render: (v: number) => <Tag bordered={false}>v{v}</Tag>,
        },
        {
          title: "",
          key: "acoes",
          width: 110,
          fixed: "right",
          render: (_, e) => (
            <Space size={4}>
              <Tooltip title="Editar">
                <Button type="text" icon={<EditOutlined />} aria-label={`Editar ${e.titulo}`} onClick={() => onAbrir(e)} />
              </Tooltip>
              <Popconfirm
                title="Remover este evento?"
                okText="Remover"
                okButtonProps={{ danger: true }}
                cancelText="Cancelar"
                onConfirm={() => onRemover(e)}
              >
                <Button type="text" danger icon={<DeleteOutlined />} aria-label={`Remover ${e.titulo}`} />
              </Popconfirm>
            </Space>
          ),
        },
      ]}
    />
  );
}
