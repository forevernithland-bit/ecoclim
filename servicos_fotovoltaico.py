"""Aba "☀️ Fotovoltaico" da Gestão de Serviços (pedido do Breno, 2026-10-02).

São clientes que o Breno INDICA pra uma empresa parceira de energia solar
fotovoltaica e recebe comissão. Cada cliente vira uma linha em
`servicos_andamento` (mesma tabela dos demais serviços) marcada com
`dados_contrato["fv"]` — assim, quando o status vai pra "Em Andamento" ou
"Finalizado", ele já entra sozinho nas abas Em Andamento / Finalizados e soma
no faturamento e no lucro igual aos serviços de aquecedor, sem nenhum caminho
paralelo. A "comissão" é o ganho da Ecoclim: vira `valor_venda_total` e
`lucro_estimado` só quando o status é Em Andamento ou Finalizado.

Status (o que aparece pro usuário -> o que fica em `status_projeto`):
    Orçamento Enviado -> "Orçamento Enviado"   (fica na aba Fotovoltaico)
    Em Andamento      -> "Em Andamento"        (vai pra aba Em Andamento)
    Finalizado        -> "Concluído PIX"       (vai pra aba Finalizados)
    Cancelado         -> "Orçamento Cancelado" (fica na aba; após 6 meses vai
                                                pra "Arquivados", no fim da aba)

`dados_contrato` é uma coluna compartilhada com outros recursos — toda
gravação aqui RELÊ o valor do banco e só troca a chave "fv" (merge), nunca
sobrescreve o dicionário inteiro.

Orçamentos enviados ao cliente (várias versões) ficam no Google Drive, na
pasta compartilhada: Fotovoltaico / <nome do cliente> / V<n>_<data>_<arquivo>.
"""
import calendar
import datetime
import re
import uuid

import pandas as pd
import streamlit as st

import utils

PASTA_DRIVE = "Fotovoltaico"
MESES_PARA_ARQUIVAR = 6

STATUS_UI = ["Orçamento Enviado", "Em Andamento", "Finalizado", "Cancelado"]
UI_PARA_DB = {
    "Orçamento Enviado": "Orçamento Enviado",
    "Em Andamento": "Em Andamento",
    "Finalizado": "Concluído PIX",
    "Cancelado": "Orçamento Cancelado",
}
DB_PARA_UI = {
    "Orçamento Enviado": "Orçamento Enviado",
    "Em Andamento": "Em Andamento",
    "Concluído PIX": "Finalizado",
    "Concluído CARTÃO": "Finalizado",
    "Orçamento Cancelado": "Cancelado",
}
TIPOS_ARQUIVO = ["pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"]


# ---------------------------------------------------------------------------
# Lógica pura (sem Streamlit / sem banco) — é o que os testes exercitam
# ---------------------------------------------------------------------------
def get_fv(dados_contrato):
    """Dicionário "fv" de um `dados_contrato`, ou None se o serviço não é
    Fotovoltaico. Aceita qualquer coisa que o pandas devolva (NaN, None...)."""
    if isinstance(dados_contrato, dict) and isinstance(dados_contrato.get("fv"), dict):
        return dados_contrato["fv"]
    return None


def eh_fv(dados_contrato):
    return get_fv(dados_contrato) is not None


def _para_data(valor):
    if not valor or (not isinstance(valor, (str, datetime.date, datetime.datetime)) and pd.isna(valor)):
        return None
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    try:
        return datetime.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def somar_meses(data, meses):
    mes_idx = data.month - 1 + meses
    ano = data.year + mes_idx // 12
    mes = mes_idx % 12 + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


def esta_arquivado(status_db, fv, hoje):
    """Cancelado há 6 meses ou mais (contados da data em que foi cancelado)."""
    if status_db != "Orçamento Cancelado" or not isinstance(fv, dict):
        return False
    cancelado_em = _para_data(fv.get("cancelado_em"))
    return bool(cancelado_em and hoje >= somar_meses(cancelado_em, MESES_PARA_ARQUIVAR))


def montar_novo_registro(nome, telefone, data_envio, comissao, agora):
    """Linha nova de `servicos_andamento` para um cliente Fotovoltaico."""
    comissao = float(comissao or 0)
    return {
        # `numero_orcamento` é UNIQUE no banco: sem o sufixo, dois clientes
        # incluídos no mesmo minuto davam erro. O padrão yymmdd-HHMM no começo
        # continua casando com a ordenação por data de tela_servicos.
        "numero_orcamento": f"FV-{agora.strftime('%y%m%d-%H%M')}-{uuid.uuid4().hex[:4]}",
        "nome_cliente": str(nome).strip(),
        "telefone_cliente": str(telefone or "").strip(),
        "endereco_cliente": "",
        "produtos_adquiridos": "Energia solar fotovoltaica (indicação a empresa parceira)",
        "valor_venda_total": 0.0,
        "lucro_estimado": 0.0,
        "status_projeto": "Orçamento Enviado",
        "instalador": "",
        "data_conclusao": data_envio.isoformat(),
        "dados_contrato": {"fv": {
            "data_envio": data_envio.isoformat(), "comissao": comissao,
            "orcamentos": [], "cancelado_em": None, "finalizado_em": None,
        }},
    }


def calcular_atualizacao(status_ui, fv_atual, comissao, data_envio, data_fechamento, hoje):
    """Dado o que o usuário escolheu na tela, devolve (campos_da_tabela,
    fv_novo). `fv_atual` é o "fv" JÁ LIDO DO BANCO (preserva as versões de
    orçamento); nada aqui toca em `orcamentos`."""
    comissao = float(comissao or 0)
    fv_novo = dict(fv_atual or {})
    fv_novo["data_envio"] = data_envio.isoformat()
    fv_novo["comissao"] = comissao
    fv_novo.setdefault("orcamentos", [])

    conta_no_lucro = status_ui in ("Em Andamento", "Finalizado")
    campos = {
        "status_projeto": UI_PARA_DB[status_ui],
        "valor_venda_total": comissao if conta_no_lucro else 0.0,
        "lucro_estimado": comissao if conta_no_lucro else 0.0,
    }

    if status_ui == "Cancelado":
        fv_novo["cancelado_em"] = fv_novo.get("cancelado_em") or hoje.isoformat()
    else:
        fv_novo["cancelado_em"] = None

    if status_ui == "Finalizado":
        fv_novo["finalizado_em"] = data_fechamento.isoformat()
        campos["data_conclusao"] = data_fechamento.isoformat()
    else:
        fv_novo["finalizado_em"] = None
        if status_ui == "Orçamento Enviado":
            campos["data_conclusao"] = data_envio.isoformat()
    return campos, fv_novo


def proxima_versao(orcamentos):
    return max([int(o.get("versao") or 0) for o in (orcamentos or [])] + [0]) + 1


def nome_pasta_cliente(nome):
    # O apóstrofo também sai: get_or_create_nested_folder monta a busca no
    # Drive com name='...' sem escapar, e "D'Ávila" derrubava o upload (400).
    limpo = re.sub(r'[\\/:*?"<>|\']', "-", str(nome or "")).strip()
    return limpo or "Sem nome"


def nome_arquivo_versao(versao, data, nome_original):
    return f"V{versao}_{data.isoformat()}_{nome_original}"


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------
def _ler_dados_contrato(supabase, id_servico):
    res = supabase.table("servicos_andamento").select("dados_contrato,status_projeto").eq("id", id_servico).execute()
    if not res.data:
        return {}, ""
    dc = res.data[0].get("dados_contrato")
    return (dict(dc) if isinstance(dc, dict) else {}), str(res.data[0].get("status_projeto") or "")


def gravar_fv(supabase, id_servico, alterar_fv, campos_extra=None):
    """Relê `dados_contrato` do banco, aplica `alterar_fv(fv_atual) -> fv_novo`
    só na chave "fv" e grava junto com `campos_extra`. Devolve o fv gravado."""
    dc, _ = _ler_dados_contrato(supabase, id_servico)
    fv_novo = alterar_fv(dict(dc.get("fv") or {}))
    dc["fv"] = fv_novo
    payload = {"dados_contrato": dc}
    payload.update(campos_extra or {})
    supabase.table("servicos_andamento").update(payload).eq("id", id_servico).execute()
    return fv_novo


def enviar_versao_orcamento(supabase, id_servico, nome_cliente, arquivo, data_versao, obs=""):
    """Sobe o arquivo pro Drive (Fotovoltaico/<cliente>/) e registra como a
    próxima versão. Devolve (True, item) ou (False, mensagem de erro)."""
    dc, _ = _ler_dados_contrato(supabase, id_servico)
    fv_banco = dc.get("fv") or {}
    # `versao_max` impede reaproveitar o número de uma versão já removida.
    versao = max(proxima_versao(fv_banco.get("orcamentos")), int(fv_banco.get("versao_max") or 0) + 1)
    nome_drive = nome_arquivo_versao(versao, data_versao, arquivo.name)
    ok, res = utils.upload_to_drive(
        arquivo, nome_drive, getattr(arquivo, "type", None) or "application/octet-stream",
        [PASTA_DRIVE, nome_pasta_cliente(nome_cliente)],
    )
    if not ok:
        return False, str(res)
    item = {"versao": versao, "arquivo": arquivo.name, "drive_id": res,
            "enviado_em": data_versao.isoformat(), "obs": str(obs or "").strip()}

    def _acrescentar(fv):
        fv["orcamentos"] = list(fv.get("orcamentos") or []) + [item]
        fv["versao_max"] = max(int(fv.get("versao_max") or 0), versao)
        return fv
    gravar_fv(supabase, id_servico, _acrescentar)
    return True, item


def remover_versao_orcamento(supabase, id_servico, versao, drive_id):
    try:
        if drive_id:
            utils.delete_drive_file(drive_id)
    except Exception:
        pass

    def _tirar(fv):
        fv["orcamentos"] = [o for o in (fv.get("orcamentos") or []) if int(o.get("versao") or 0) != int(versao)]
        return fv
    gravar_fv(supabase, id_servico, _tirar)


# ---------------------------------------------------------------------------
# Telas
# ---------------------------------------------------------------------------
def _brl(v):
    return utils.to_br_currency(v)


def _fmt_data(iso):
    d = _para_data(iso)
    return d.strftime("%d/%m/%Y") if d else ""


@st.dialog("☀️ Incluir cliente (Fotovoltaico)")
def dialogo_incluir_cliente(supabase):
    st.caption("Cliente que você indica pra empresa parceira de energia solar fotovoltaica. "
               "Entra como Orçamento Enviado — o status muda depois, dentro do cliente.")
    nome = st.text_input("Nome do cliente *", key="fv_inc_nome")
    tel = st.text_input("Telefone / WhatsApp", key="fv_inc_tel", placeholder="(31) 99999-9999")
    c1, c2 = st.columns(2)
    data_envio = c1.date_input("Data de envio do orçamento", value=datetime.date.today(),
                               format="DD/MM/YYYY", key="fv_inc_data")
    comissao = c2.number_input("Comissão prevista (R$)", min_value=0.0, format="%.2f", key="fv_inc_comissao",
                               help="Opcional agora — pode preencher depois. Só entra no lucro quando o status for Em Andamento ou Finalizado.")
    arquivo = st.file_uploader("Orçamento enviado (opcional)", type=TIPOS_ARQUIVO, key="fv_inc_arquivo")

    if st.button("✅ Incluir cliente", type="primary", use_container_width=True, key="fv_inc_btn"):
        if not str(nome).strip():
            st.error("Informe o nome do cliente.")
            return
        try:
            registro = montar_novo_registro(nome, tel, data_envio, comissao, datetime.datetime.now())
            novo = supabase.table("servicos_andamento").insert(registro).execute().data[0]
        except Exception as e:
            st.error(f"Erro ao incluir: {e}")
            return
        if arquivo is not None:
            ok, res = enviar_versao_orcamento(supabase, novo["id"], registro["nome_cliente"], arquivo, data_envio)
            aviso_upload = "" if ok else f" ⚠️ Mas o orçamento NÃO subiu pro Drive ({res}) — anexe de novo dentro do cliente."
        else:
            aviso_upload = ""
        for k in ("fv_inc_nome", "fv_inc_tel", "fv_inc_data", "fv_inc_comissao", "fv_inc_arquivo"):
            st.session_state.pop(k, None)
        # st.warning aqui sumia no st.rerun() — o aviso viaja pelo toast.
        st.session_state["fv_toast"] = f"☀️ {registro['nome_cliente']} incluído em Fotovoltaico.{aviso_upload}"
        st.rerun()


def painel_cliente(supabase, row, key_prefix):
    """Painel de um cliente Fotovoltaico (abre ao clicar na linha, em qualquer
    aba onde ele esteja)."""
    id_servico = int(row["id"])
    fv = get_fv(row.get("dados_contrato")) or {}
    hoje = datetime.date.today()
    kp = f"fv_{key_prefix}"

    st.markdown("---")
    st.markdown(f"### ☀️ Fotovoltaico — {row.get('nome_cliente', '')}")

    c1, c2 = st.columns(2)
    nome = c1.text_input("Nome do cliente", value=str(row.get("nome_cliente") or ""), key=f"{kp}_nome")
    tel_banco = row.get("telefone_cliente")
    tel = c2.text_input("Telefone / WhatsApp", value="" if pd.isna(tel_banco) else str(tel_banco), key=f"{kp}_tel")

    c3, c4, c5 = st.columns(3)
    data_envio = c3.date_input("Data de envio do orçamento", value=_para_data(fv.get("data_envio")) or hoje,
                               format="DD/MM/YYYY", key=f"{kp}_envio")
    status_atual_ui = DB_PARA_UI.get(str(row.get("status_projeto")), "Orçamento Enviado")
    status_ui = c4.selectbox("Status", STATUS_UI, index=STATUS_UI.index(status_atual_ui), key=f"{kp}_status")
    comissao = c5.number_input("Comissão prevista (R$)", min_value=0.0, value=float(fv.get("comissao") or 0.0),
                               format="%.2f", key=f"{kp}_comissao")

    data_fechamento = hoje
    if status_ui == "Finalizado":
        data_fechamento = st.date_input("Data de fechamento (entra no faturamento deste mês)",
                                        value=_para_data(fv.get("finalizado_em")) or hoje,
                                        format="DD/MM/YYYY", key=f"{kp}_fechamento")
    if status_ui in ("Em Andamento", "Finalizado"):
        st.caption("A comissão entra no faturamento e no lucro, igual aos serviços de aquecedor. "
                   "O cliente aparece nas abas Em Andamento / Finalizados com ☀️ na frente do nome.")
    elif status_ui == "Cancelado":
        st.caption(f"Fica nesta aba e, depois de {MESES_PARA_ARQUIVAR} meses cancelado, vai pra Arquivados (no fim da aba).")

    # ---- Orçamentos enviados (versões) ----
    st.markdown("##### 📎 Orçamentos enviados ao cliente")
    st.caption("Cada envio atualizado vira uma nova versão, guardada no Drive em Fotovoltaico › nome do cliente.")
    versoes = sorted(fv.get("orcamentos") or [], key=lambda o: int(o.get("versao") or 0), reverse=True)
    if not versoes:
        st.info("Nenhum orçamento anexado ainda.")
    for o in versoes:
        l1, l2 = st.columns([5, 1])
        link = f"https://drive.google.com/file/d/{o.get('drive_id')}/view"
        obs = f" — {o['obs']}" if o.get("obs") else ""
        l1.markdown(f"📄 **V{o.get('versao')}** · {_fmt_data(o.get('enviado_em'))} · "
                    f"[{o.get('arquivo')}]({link}){obs}")
        if l2.button("🗑️", key=f"{kp}_del_{o.get('versao')}", help="Remover esta versão (apaga também do Drive)"):
            remover_versao_orcamento(supabase, id_servico, o.get("versao"), o.get("drive_id"))
            st.rerun()

    contador_key = f"{kp}_up_n"
    st.session_state.setdefault(contador_key, 0)
    arquivo = st.file_uploader("Anexar orçamento (nova versão)", type=TIPOS_ARQUIVO,
                               key=f"{kp}_up_{st.session_state[contador_key]}")
    obs_versao = st.text_input("Observação da versão (opcional)", key=f"{kp}_up_obs_{st.session_state[contador_key]}",
                               placeholder="Ex.: proposta com 12 painéis, valor revisado")
    if arquivo is not None and st.button("📥 Salvar como nova versão", key=f"{kp}_up_btn"):
        with st.spinner("Enviando pro Drive..."):
            ok, res = enviar_versao_orcamento(supabase, id_servico, nome or row.get("nome_cliente"),
                                              arquivo, hoje, obs_versao)
        if ok:
            st.session_state[contador_key] += 1
            st.session_state["fv_toast"] = f"📎 Versão V{res['versao']} salva no Drive."
            st.rerun()
        else:
            st.error(f"Não consegui enviar pro Drive: {res}")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 SALVAR CLIENTE", type="primary", use_container_width=True, key=f"{kp}_salvar"):
        if not str(nome).strip():
            st.error("O nome do cliente não pode ficar vazio.")
            return
        try:
            # O "fv" é relido do banco dentro de gravar_fv (preserva as versões
            # de orçamento mesmo se outra aba/sessão acabou de anexar uma).
            dc, _ = _ler_dados_contrato(supabase, id_servico)
            campos, _fv = calcular_atualizacao(status_ui, dc.get("fv") or {}, comissao, data_envio, data_fechamento, hoje)
            campos_extra = {"nome_cliente": str(nome).strip(), "telefone_cliente": str(tel).strip(), **campos}
            gravar_fv(supabase, id_servico, lambda fv_banco: calcular_atualizacao(
                status_ui, fv_banco, comissao, data_envio, data_fechamento, hoje)[1], campos_extra)
            status_antes = str(row.get("status_projeto") or "")
            if campos["status_projeto"] != status_antes:
                try:
                    import movimentacoes
                    movimentacoes.registrar(supabase, "servico", id_servico, "status",
                                            de=status_antes or None, para=campos["status_projeto"],
                                            detalhe=f"{str(nome).strip()} (Fotovoltaico)")
                except Exception:
                    pass
            destino = {"Em Andamento": " — agora está na aba Em Andamento.",
                       "Finalizado": " — agora está na aba Finalizados."}.get(status_ui, "")
            st.session_state["fv_toast"] = f"✅ {str(nome).strip()} atualizado{destino}"
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")


def renderizar_aba(supabase, df, barra_busca_fn, selecionar_fn):
    """Conteúdo da aba Fotovoltaico. `df` é o dataframe completo de serviços
    (com a coluna auxiliar `_fv`); `barra_busca_fn`/`selecionar_fn` vêm de
    tela_servicos (busca ao vivo e seleção ancorada no ID)."""
    toast = st.session_state.pop("fv_toast", None)
    if toast:
        st.toast(toast)

    c_info, c_btn = st.columns([3, 1])
    c_info.caption("Clientes indicados à empresa parceira de energia solar fotovoltaica (comissão). "
                   "Aqui ficam os que estão em fase de orçamento; ao mudar o status pra Em Andamento ou "
                   "Finalizado, o cliente vai pra aba correspondente.")
    if c_btn.button("➕ Incluir cliente", type="primary", use_container_width=True, key="fv_btn_incluir"):
        dialogo_incluir_cliente(supabase)

    hoje = datetime.date.today()
    df_fv = df[df["_fv"]].copy() if "_fv" in df.columns else df.iloc[0:0].copy()
    if not df_fv.empty:
        df_fv["_fv_dict"] = df_fv["dados_contrato"].apply(get_fv)
        df_fv["_arquivado"] = df_fv.apply(lambda r: esta_arquivado(r["status_projeto"], r["_fv_dict"], hoje), axis=1)
        df_fv = df_fv[df_fv["status_projeto"].isin(["Orçamento Enviado", "Orçamento Cancelado"])]

    def _preparar(base):
        base = base.reset_index(drop=True).copy()
        base["Cliente"] = base["nome_cliente"]
        base["Telefone"] = base["telefone_cliente"].fillna("").astype(str)
        base["Status"] = base["status_projeto"].map(lambda s: DB_PARA_UI.get(s, s))
        base["Enviado em"] = base["_fv_dict"].map(lambda f: _fmt_data((f or {}).get("data_envio")))
        base["Versões"] = base["_fv_dict"].map(lambda f: len((f or {}).get("orcamentos") or []))
        base["Comissão prevista"] = base["_fv_dict"].map(lambda f: _brl((f or {}).get("comissao") or 0))
        base["Cancelado em"] = base["_fv_dict"].map(lambda f: _fmt_data((f or {}).get("cancelado_em")))
        return base

    ativos = df_fv[~df_fv["_arquivado"]] if not df_fv.empty else df_fv
    arquivados = df_fv[df_fv["_arquivado"]] if not df_fv.empty else df_fv
    cols = ["Cliente", "Telefone", "Status", "Enviado em", "Versões", "Comissão prevista", "Cancelado em"]

    # Arquivados (cancelados há 6+ meses) ficam fora da lista normal; um
    # toggle troca a MESMA grade pra eles — uma grade só, uma seleção só.
    ver_arq = False
    if not arquivados.empty:
        ver_arq = st.toggle(f"📦 Ver arquivados — cancelados há mais de {MESES_PARA_ARQUIVAR} meses ({len(arquivados)})",
                            key="fv_ver_arquivados")
    base = arquivados if ver_arq else ativos

    serv = None
    if base.empty:
        st.info("Nenhum cliente em orçamento por aqui. Use ➕ Incluir cliente." if not ver_arq else "Nenhum arquivado.")
    else:
        prefixo = "fv_arq" if ver_arq else "fv"
        base = barra_busca_fn(_preparar(base), prefixo)
        sel = st.dataframe(base[cols], use_container_width=True, on_select="rerun",
                           selection_mode="single-row", hide_index=True, key=f"g_{prefixo}")
        n_orc = int((base["status_projeto"] == "Orçamento Enviado").sum())
        n_canc = int((base["status_projeto"] == "Orçamento Cancelado").sum())
        st.caption(f"{n_orc} em orçamento · {n_canc} cancelado(s)")
        serv = selecionar_fn(base, sel, prefixo)

    if serv is not None:
        painel_cliente(supabase, serv, f"aba_{int(serv['id'])}")
