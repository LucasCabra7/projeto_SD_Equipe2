import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { App as AntApp, ConfigProvider, theme } from "antd";
import ptBR from "antd/locale/pt_BR";
import dayjs from "dayjs";
import "dayjs/locale/pt-br";
import { Agenda } from "./App";
import "./estilo.css";

dayjs.locale("pt-br");

const consultaEscuro = window.matchMedia("(prefers-color-scheme: dark)");

function Raiz() {
  const [escuro, setEscuro] = useState(consultaEscuro.matches);
  useEffect(() => {
    const aoMudar = (e: MediaQueryListEvent) => setEscuro(e.matches);
    consultaEscuro.addEventListener("change", aoMudar);
    return () => consultaEscuro.removeEventListener("change", aoMudar);
  }, []);

  return (
    <ConfigProvider
      locale={ptBR}
      theme={{
        algorithm: escuro ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: escuro ? "#6FA3C4" : "#2B5D7D",
          borderRadius: 6,
          fontFamily: '"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
        },
      }}
    >
      <AntApp>
        <Agenda />
      </AntApp>
    </ConfigProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Raiz />
  </StrictMode>,
);
