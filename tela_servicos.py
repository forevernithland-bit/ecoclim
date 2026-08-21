import streamlit as st
import pandas as pd
import datetime
import re
import unicodedata
import utils
import servicos_painel
import cronograma

def deve_ir_para_finalizados(status, data_conc_str):
    if status in ["Concluído PIX", "Concluído CARTÃO"]:
        return True
    return False


def _norm_txt(s):
    """minúsculas, sem acento — para agrupar/buscar de forma robusta."""
    t = str(s or "").lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')


def _ts_registro(row):
    """Timestamp para ordenar por data: usa o numero_orcamento (yymmdd-HHMM) se
    casar, senão cai para data_conclusao."""
    m = re.search(r'(\d{6})-(\d{4})', str(row.get('numero_orcamento') or ''))
    if m:
        try:
            return pd.to_datetime(m.group(1) + m.group(2), format='%y%m%d%H%M')
        except Exception:
            pass
    try:
        return pd.to_datetime(row.get('data_conclusao'))
    except Exception:
        return pd.NaT


def barra_busca_servicos(df, key_prefix):
    """Campo único de busca ao vivo (filtra a cada letra digitada, por nome,
    telefone OU código) + ordenação por Data/Nome. Retorna o df filtrado."""
    if df is None or df.empty:
        return df

    c1, c2 = st.columns([3, 1.4])
    termo = c1.text_input("🔍 Buscar por nome, telefone ou código", key=f"busca_termo_{key_prefix}",
                          placeholder="Digite para filtrar...")
    ordenar = c2.selectbox("Ordenar por", ["Data (recente)", "Data (antiga)", "Nome (A-Z)", "Nome (Z-A)"],
                           key=f"busca_ord_{key_prefix}")

    out = df.copy()
    termo = str(termo or "").strip()
    if termo:
        alvo = _norm_txt(termo)
        cols_busca = [c for c in ['nome_cliente', 'telefone_cliente', 'numero_orcamento'] if c in out.columns]
        mask = pd.Series(False, index=out.index)
        for c in cols_busca:
            mask = mask | out[c].fillna("").astype(str).map(_norm_txt).str.contains(alvo, regex=False)
        out = out[mask]

    out = out.copy()
    out['_ts'] = out.apply(_ts_registro, axis=1)
    out['_nome'] = out['nome_cliente'].fillna("").astype(str).map(_norm_txt) if 'nome_cliente' in out.columns else ""
    if ordenar == "Data (recente)":
        out = out.sort_values('_ts', ascending=False, na_position='last')
    elif ordenar == "Data (antiga)":
        out = out.sort_values('_ts', ascending=True, na_position='last')
    elif ordenar == "Nome (A-Z)":
        out = out.sort_values('_nome', ascending=True)
    else:
        out = out.sort_values('_nome', ascending=False)

    return out.drop(columns=['_ts', '_nome']).reset_index(drop=True)


@st.dialog("➕ Cadastrar Venda (Em Andamento)")
def _modal_cadastrar_venda(supabase, lista_instaladores):
    st.caption("Cria um serviço já em andamento (sem passar por orçamento). Você pode detalhar depois clicando no cliente na lista.")
    nome = st.text_input("Cliente *", key="cv_nome")
    tel = st.text_input("WhatsApp", key="cv_tel", placeholder="(31) 99999-9999")
    end = st.text_input("Endereço (opcional)", key="cv_end", placeholder="Rua, número, bairro, cidade - UF")
    c1, c2 = st.columns(2)
    valor = c1.number_input("Valor Total da venda (R$)", min_value=0.0, format="%.2f", key="cv_valor")
    lucro = c2.number_input("Lucro Líquido estimado (R$)", min_value=0.0, format="%.2f", key="cv_lucro")
    c3, c4 = st.columns(2)
    inst = c3.selectbox("Instalador", [""] + list(lista_instaladores), key="cv_inst")
    data_prev = c4.date_input("Data prevista de término", value=datetime.date.today(), format="DD/MM/YYYY", key="cv_data")
    prod = st.text_input("Produtos / Serviços (resumo, opcional)", key="cv_prod")

    if st.button("✅ Cadastrar venda", type="primary", use_container_width=True):
        if not str(nome).strip():
            st.error("Informe o nome do cliente.")
            return
        payload = {
            "numero_orcamento": f"VENDA-{datetime.datetime.now().strftime('%y%m%d-%H%M')}",
            "nome_cliente": str(nome).strip(),
            "telefone_cliente": str(tel).strip(),
            "endereco_cliente": str(end).strip(),
            "produtos_adquiridos": str(prod).strip(),
            "valor_venda_total": float(valor),
            "lucro_estimado": float(lucro),
            "status_projeto": "Em Andamento",
            "instalador": inst,
            "data_conclusao": data_prev.strftime('%Y-%m-%d'),
            "dados_contrato": {},
        }
        try:
            supabase.table('servicos_andamento').insert(payload).execute()
            st.success("✅ Venda cadastrada em andamento!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao cadastrar: {e}")

def renderizar_pagamento_instaladores(df_subset, supabase, key_suffix, titulo):
    """Tabela compacta de pagamento aos instaladores — marca vários de uma vez,
    sem precisar abrir o painel de detalhe de cada cliente. df_subset já deve
    vir filtrado pra quem faz sentido pagar agora (ex.: finalizados do mês,
    ou concluídos pelo instalador mas ainda aguardando pagamento do cliente)."""
    df_pag_base = df_subset[['id', 'nome_cliente', 'instalador', 'custo_terceirizados', 'pago_instalador']].copy()
    df_pag_base['custo_terceirizados'] = pd.to_numeric(df_pag_base['custo_terceirizados'], errors='coerce').fillna(0)
    df_pag_base = df_pag_base[df_pag_base['custo_terceirizados'] > 0].reset_index(drop=True)
    df_pag_base['pago_instalador'] = df_pag_base['pago_instalador'].fillna(False).astype(bool)
    if df_pag_base.empty:
        return

    # Pagos sobem pro topo (só depois de salvar — durante a edição a linha
    # não pula de lugar, senão fica confuso clicar em vários seguidos),
    # pendentes ficam embaixo, mais fáceis de achar.
    df_pag_base = df_pag_base.sort_values(['pago_instalador', 'nome_cliente'], ascending=[False, True]).reset_index(drop=True)

    n_pendentes = int((~df_pag_base['pago_instalador']).sum())
    valor_total_pendente = df_pag_base.loc[~df_pag_base['pago_instalador'], 'custo_terceirizados'].sum()

    # Adiantamentos ainda não compensados dos instaladores que aparecem
    # nesta lista — descontados do total pendente (pedido do Breno).
    instaladores_aqui = [i for i in df_pag_base['instalador'].dropna().unique().tolist() if str(i).strip()]
    total_adiantado = 0.0
    try:
        if instaladores_aqui:
            res_ad = supabase.table('adiantamentos_instalador').select('valor').in_('instalador', instaladores_aqui).eq('pago', False).execute()
            total_adiantado = sum(float(a.get('valor') or 0) for a in (res_ad.data or []))
    except Exception:
        pass
    valor_liquido = valor_total_pendente - total_adiantado

    with st.expander(f"💰 {titulo} — {utils.to_br_currency(valor_liquido)} líquido pendente ({n_pendentes})", expanded=False):
        df_pag_view = df_pag_base.rename(columns={
            'nome_cliente': 'Cliente', 'instalador': 'Instalador',
            'custo_terceirizados': 'Valor Instalação', 'pago_instalador': 'Pago?',
        })
        cfg_pag = {
            "id": None,
            "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
            "Instalador": st.column_config.TextColumn("Instalador", disabled=True),
            "Valor Instalação": st.column_config.NumberColumn("Valor Instalação", format="R$ %.2f", disabled=True),
            "Pago?": st.column_config.CheckboxColumn("💰 Pago?"),
        }
        df_pag_ed = st.data_editor(df_pag_view, column_config=cfg_pag, hide_index=True,
                                   use_container_width=True, key=f"pag_editor_{key_suffix}")

        total_pendente_pag = df_pag_ed.loc[~df_pag_ed['Pago?'].astype(bool), 'Valor Instalação'].sum()
        total_pago_pag = df_pag_ed.loc[df_pag_ed['Pago?'].astype(bool), 'Valor Instalação'].sum()
        mp1, mp2, mp3, mp4 = st.columns(4)
        mp1.metric("💰 Pendente", utils.to_br_currency(total_pendente_pag))
        mp2.metric("✅ Já Pago", utils.to_br_currency(total_pago_pag))
        mp3.metric("💵 Adiantamento", utils.to_br_currency(total_adiantado))
        mp4.metric("🧮 Líquido a Pagar", utils.to_br_currency(total_pendente_pag - total_adiantado))
        if total_adiantado > 0:
            st.caption("Líquido a Pagar = Pendente − Adiantamento (ainda não marcado como compensado). Marque um adiantamento como pago/compensado no popup 💵 Adiantamento.")

        if st.button("💾 Salvar Pagamentos", key=f"btn_salvar_pag_{key_suffix}"):
            hoje_str = datetime.date.today().strftime('%Y-%m-%d')
            alterados = 0
            for _, row in df_pag_ed.iterrows():
                original = df_pag_base[df_pag_base['id'] == row['id']].iloc[0]
                if bool(row['Pago?']) != bool(original['pago_instalador']):
                    payload = {"pago_instalador": bool(row['Pago?'])}
                    payload["data_pagamento_instalador"] = hoje_str if bool(row['Pago?']) else None
                    supabase.table('servicos_andamento').update(payload).eq('id', int(row['id'])).execute()
                    alterados += 1
            if alterados:
                st.success(f"✅ {alterados} pagamento(s) atualizado(s)!")
                st.rerun()
            else:
                st.info("Nenhuma alteração pra salvar.")


@st.dialog("💵 Adiantamento ao Instalador")
def _modal_adiantamento_instalador(supabase, lista_instaladores):
    st.caption("Registra um adiantamento dado ao instalador (fora do valor normal da instalação). Não altera nenhum serviço — só fica no histórico dele.")
    # Valdimar é o instalador principal — já vem pré-selecionado.
    _idx_padrao = lista_instaladores.index("Valdimar") if "Valdimar" in lista_instaladores else 0
    instalador_sel = st.selectbox("Instalador", lista_instaladores, index=_idx_padrao, key="ad_instalador")

    try:
        res_receber = supabase.table('servicos_andamento').select('custo_terceirizados').eq('instalador', instalador_sel).eq('pago_instalador', False).execute()
        total_a_receber = sum(float(r.get('custo_terceirizados') or 0) for r in (res_receber.data or []))
    except Exception:
        total_a_receber = 0.0

    try:
        res_adiant = supabase.table('adiantamentos_instalador').select('*').eq('instalador', instalador_sel).order('data', desc=True).execute()
        adiantamentos = res_adiant.data or []
    except Exception:
        adiantamentos = []
    # Só adiantamentos ainda NÃO marcados como pagos/compensados descontam
    # do saldo — um que já foi compensado não deve continuar puxando o
    # saldo pra baixo pra sempre.
    total_adiantado_aberto = sum(float(a.get('valor') or 0) for a in adiantamentos if not a.get('pago', False))
    saldo_pendente = total_a_receber - total_adiantado_aberto

    c1, c2 = st.columns(2)
    c1.metric("A Receber (instalações não pagas)", utils.to_br_currency(total_a_receber))
    c2.metric("Saldo Pendente (após adiantamentos)", utils.to_br_currency(saldo_pendente))

    st.markdown("##### ➕ Novo Adiantamento")
    valor_adiant = st.number_input("Valor do Adiantamento (R$)", min_value=0.0, format="%.2f", key="ad_valor")
    motivo_adiant = st.text_area("Descrição / Motivo", key="ad_motivo", placeholder="Ex: adiantamento pedido pelo instalador pra despesa da obra")
    data_adiant = st.date_input("Data", value=datetime.date.today(), format="DD/MM/YYYY", key="ad_data")

    if valor_adiant > 0:
        st.caption(f"Saldo pendente depois deste adiantamento: **{utils.to_br_currency(saldo_pendente - valor_adiant)}**")

    if st.button("💾 Registrar Adiantamento", type="primary", use_container_width=True):
        if valor_adiant <= 0:
            st.warning("Informe um valor maior que zero.")
        else:
            try:
                supabase.table('adiantamentos_instalador').insert({
                    "instalador": instalador_sel,
                    "valor": valor_adiant,
                    "motivo": motivo_adiant.strip(),
                    "data": data_adiant.strftime('%Y-%m-%d'),
                    "pago": False,
                }).execute()
                st.success("✅ Adiantamento registrado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao registrar. Confirme se a tabela 'adiantamentos_instalador' e sua coluna 'pago' existem no Supabase (rode o SQL pendente). Detalhe: {e}")

    if adiantamentos:
        st.markdown("##### 🕓 Histórico de Adiantamentos")
        st.caption("Marque como Pago quando esse adiantamento já tiver sido descontado/compensado — ele deixa de reduzir o saldo pendente.")
        for a in adiantamentos:
            try:
                data_fmt = pd.to_datetime(a.get('data')).strftime('%d/%m/%Y')
            except Exception:
                data_fmt = str(a.get('data') or '')
            _ca1, _ca2 = st.columns([4, 1])
            _ca1.markdown(f"**{data_fmt}** — {utils.to_br_currency(a.get('valor'))} — {a.get('motivo') or 'sem motivo informado'}")
            _pago_novo = _ca2.checkbox("Pago", value=bool(a.get('pago', False)), key=f"ad_pago_{a['id']}")
            if _pago_novo != bool(a.get('pago', False)):
                try:
                    supabase.table('adiantamentos_instalador').update({"pago": _pago_novo}).eq('id', a['id']).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")


@st.dialog("📅 Agendar Tarefa/Visita para o Instalador")
def _modal_agendar_tarefa_instalador(supabase, lista_instaladores):
    st.caption("Cria uma tarefa que aparece direto no app do instalador (com aviso de notificação). Ex.: ligar pra um cliente e agendar uma manutenção.")
    instalador_sel = st.selectbox("Instalador", lista_instaladores, key="at_instalador")
    c1, c2 = st.columns(2)
    tipo_sel = c1.selectbox("Tipo", ["Manutenção", "Orçamento", "Tarefa"], key="at_tipo")
    cliente_nome = c2.text_input("Cliente", key="at_cliente")
    c3, c4 = st.columns(2)
    telefone = c3.text_input("Telefone", key="at_telefone")
    endereco = c4.text_input("Endereço (opcional)", key="at_endereco")
    c5, c6 = st.columns(2)
    data_visita = c5.date_input("Data prevista", value=datetime.date.today(), format="DD/MM/YYYY", key="at_data")
    hora_visita = c6.time_input("Hora", value=datetime.time(9, 0), key="at_hora")
    observacoes = st.text_area("O que ele precisa fazer", key="at_obs", placeholder="Ex: ligar pro cliente Fulano e agendar uma manutenção do sistema")

    if st.button("📅 Agendar para o Instalador", type="primary", use_container_width=True):
        if not cliente_nome.strip():
            st.warning("Informe pelo menos o nome do cliente.")
        else:
            try:
                data_hora_iso = datetime.datetime.combine(data_visita, hora_visita).isoformat()
                supabase.table('agenda_visitas').insert({
                    "instalador": instalador_sel,
                    "tipo": tipo_sel,
                    "cliente_nome": cliente_nome.strip(),
                    "telefone": telefone.strip(),
                    "endereco": endereco.strip(),
                    "data_hora": data_hora_iso,
                    "status": "Agendada",
                    "observacoes": observacoes.strip(),
                    "visto_pelo_instalador": False,
                    "criado_por": "admin",
                }).execute()
                st.success(f"✅ Tarefa agendada para {instalador_sel}! Vai aparecer no app dele com aviso de notificação.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao agendar. Certifique-se de que as colunas 'visto_pelo_instalador' e 'criado_por' existem na tabela 'agenda_visitas'. Detalhe: {e}")


def renderizar():
    st.markdown("""
        <style>
        div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] { display: none !important; }
        input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none !important; margin: 0 !important; }
        input[type=number] { -moz-appearance: textfield !important; }
        @media screen and (max-width: 768px) {
            div[data-testid="stDataFrame"] { overflow-x: auto !important; }
            div[data-testid="column"] { width: 100% !important; min-width: 100% !important; display: block !important; margin-bottom: 0.8rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    col_tit, col_btn = st.columns([1.6, 2.2])
    with col_tit:
        st.markdown("## 📋 Gestão de Serviços")
        
    supabase = st.session_state.supabase

    # ---------------------------------------------------------------
    # Notificação: instalador deixou comentário/valor sugerido numa
    # tarefa de agenda (respondendo o que o Breno pediu pelo app dele).
    # ---------------------------------------------------------------
    try:
        res_notif = supabase.table('agenda_visitas').select('*').eq('visto_pelo_admin', False).not_.is_('comentario_instalador', 'null').execute()
        notificacoes_instalador = [n for n in (res_notif.data or []) if str(n.get('comentario_instalador') or '').strip()]
    except Exception:
        notificacoes_instalador = []

    if notificacoes_instalador:
        with st.container(border=True):
            st.markdown(f"##### 🔔 {len(notificacoes_instalador)} resposta(s) do(s) instalador(es) na Agenda")
            for n in notificacoes_instalador:
                _partes = [f"**{n.get('instalador', '')}** sobre **{n.get('cliente_nome', '')}**:"]
                _partes.append(f"> {n.get('comentario_instalador')}")
                if n.get('valor_sugerido'):
                    _partes.append(f"💰 Valor sugerido: {utils.to_br_currency(n.get('valor_sugerido'))}")
                st.markdown("\n\n".join(_partes))
                if st.button("✅ Marcar como visto", key=f"notif_visto_{n['id']}"):
                    try:
                        supabase.table('agenda_visitas').update({"visto_pelo_admin": True}).eq('id', n['id']).execute()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                st.markdown("---")

    try:
        res = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df = pd.DataFrame(res.data)
    except: 
        st.error("Erro de conexão com o banco de dados.")
        return
        
    if df.empty: 
        st.info("Nenhum serviço ou orçamento encontrado.")
        return

    try:
        res_inst = supabase.table('config_instaladores').select('nome').order('nome').execute()
        lista_instaladores = [r['nome'] for r in res_inst.data if str(r.get('nome', '')).strip() != ""]
    except:
        lista_instaladores = []

    with col_btn:
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        cb1, cb2, cb3 = st.columns(3)
        if cb1.button("📅 Cronograma", use_container_width=True, type="secondary"):
            cronograma.modal_cronograma(df, lista_instaladores)
        if cb2.button("💵 Adiantamento", use_container_width=True, type="secondary"):
            _modal_adiantamento_instalador(supabase, lista_instaladores)
        if cb3.button("📅+ Agendar Tarefa", use_container_width=True, type="secondary"):
            _modal_agendar_tarefa_instalador(supabase, lista_instaladores)

    if 'instalador' not in df.columns:
        df['instalador'] = ""

    df_taxas = utils.load_taxas()
    df_produtos = utils.load_catalog('catalogo_produtos')
    
    df['data_conclusao'] = pd.to_datetime(df['data_conclusao'], errors='coerce')
    df['ir_finalizados'] = df.apply(lambda x: deve_ir_para_finalizados(x['status_projeto'], x['data_conclusao']), axis=1)

    df['Cliente'] = df['nome_cliente']
    df['Status'] = df['status_projeto']
    df['Valor Total'] = df['valor_venda_total'].apply(lambda x: utils.to_br_currency(x))
    df['Lucro Líquido'] = df['lucro_estimado'].apply(lambda x: utils.to_br_currency(x))
    df['Instalador'] = df['instalador']

    def descobrir_data_termino(row):
        status = str(row['status_projeto'])
        alvos = ["Aguardando Pagamento", "Concluído PIX", "Concluído CARTÃO", "Aguardando Peças", "Em Andamento"]
        if status in alvos and pd.notna(row['data_conclusao']) and str(row['data_conclusao']).lower() not in ['nat', 'none', 'nan']:
            try: return pd.to_datetime(row['data_conclusao']).strftime('%d/%m/%Y')
            except: pass
        return ""
    
    df['Data de término'] = df.apply(descobrir_data_termino, axis=1)

    def descobrir_venc_fornecedor(row):
        if bool(row.get('pago_avista_fornecedor', False)):
            return "✅ PAGO À VISTA"
        venc = row.get('vencimento_boleto')
        if pd.notna(venc) and str(venc).strip().lower() not in ['none', 'nan', 'nat', '']:
            try: return pd.to_datetime(venc).strftime('%d/%m/%Y')
            except: return str(venc)
        return ""
    
    df['($) Fornecedor'] = df.apply(descobrir_venc_fornecedor, axis=1)

    def descobrir_report_instalador(row):
        if bool(row.get('instalacao_concluida_instalador', False)):
            return "📲✅ Concluiu"
        if str(row.get('observacao_instalador', '') or '').strip().lower() not in ('', 'nan', 'none'):
            return "📲 Comentou"
        return ""

    df['Instalador Reportou'] = df.apply(descobrir_report_instalador, axis=1)

    # "pendente recebimento" NÃO aparece mais na grade principal — esse aviso
    # agora vive só no total do bloco "💰 Pagamento aos Instaladores" dentro
    # de Finalizados (renderizar_pagamento_instaladores), pra não duplicar a
    # informação em dois lugares.
    ativos_status = ["Em Andamento", "Aguardando Pagamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]

    df_orc = df[(~df['status_projeto'].isin(ativos_status)) & (df['status_projeto'] != 'Rascunho') & (df['status_projeto'] != 'Rascunho Rápido')].reset_index(drop=True)
    df_fin = df[df['ir_finalizados'] == True].reset_index(drop=True)
    df_atv = df[(df['status_projeto'].isin(ativos_status)) & (df['ir_finalizados'] == False)].reset_index(drop=True)

    aba1, aba2, aba3 = st.tabs(["🚀 Em Andamento", "📝 Orçamentos", "✅ Finalizados"])

    colunas_visiveis = ['Cliente', 'Status', 'Valor Total', 'Lucro Líquido', 'Data de término', 'Instalador', '($) Fornecedor', 'Instalador Reportou']

    config_colunas = {
        "Cliente": "Cliente", "Status": "Status",
        "Valor Total": st.column_config.TextColumn("Valor Total"),
        "Lucro Líquido": st.column_config.TextColumn("Lucro Líquido"),
        "Data de término": st.column_config.TextColumn("Data de término"),
        "Instalador": "Instalador",
        "($) Fornecedor": st.column_config.TextColumn("($) Fornecedor"),
        "Instalador Reportou": st.column_config.TextColumn("App Instalador"),
    }
    
    with aba1:
        cad_c1, cad_c2 = st.columns([1, 4])
        if cad_c1.button("➕ Cadastrar Venda", type="primary", use_container_width=True, key="btn_cad_venda"):
            _modal_cadastrar_venda(supabase, lista_instaladores)
        df_atv = barra_busca_servicos(df_atv, "atv")
        sel = st.dataframe(df_atv[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key="g_atv")
        total_bruto_atv = pd.to_numeric(df_atv['valor_venda_total'], errors='coerce').fillna(0).sum()
        total_lucro_atv = pd.to_numeric(df_atv['lucro_estimado'], errors='coerce').fillna(0).sum()
        st.markdown(f"<div style='text-align: right; font-size: 18px; font-weight: bold; margin-bottom: 20px;'><span style='color: #555; margin-right: 20px;'>Faturamento Bruto: {utils.to_br_currency(total_bruto_atv)}</span> <span style='color: #004488;'>Lucro Líquido Estimado: {utils.to_br_currency(total_lucro_atv)}</span></div>", unsafe_allow_html=True)

        if sel.selection.rows and len(df_atv) > sel.selection.rows[0]:
            servicos_painel.exibir_painel_detalhado(df_atv.iloc[sel.selection.rows[0]], supabase, df_taxas, df_produtos, f"atv_{df_atv.iloc[sel.selection.rows[0]]['id']}", lista_instaladores)
    
    with aba2:
        df_orc = barra_busca_servicos(df_orc, "orc")
        sel = st.dataframe(df_orc[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key="g_orc")
        total_bruto_orc = pd.to_numeric(df_orc['valor_venda_total'], errors='coerce').fillna(0).sum()
        total_lucro_orc = pd.to_numeric(df_orc['lucro_estimado'], errors='coerce').fillna(0).sum()
        st.markdown(f"<div style='text-align: right; font-size: 18px; font-weight: bold; margin-bottom: 20px;'><span style='color: #555; margin-right: 20px;'>Faturamento Bruto: {utils.to_br_currency(total_bruto_orc)}</span> <span style='color: #004488;'>Lucro Líquido Estimado: {utils.to_br_currency(total_lucro_orc)}</span></div>", unsafe_allow_html=True)
        
        if sel.selection.rows and len(df_orc) > sel.selection.rows[0]: 
            servicos_painel.exibir_painel_detalhado(df_orc.iloc[sel.selection.rows[0]], supabase, df_taxas, df_produtos, f"orc_{df_orc.iloc[sel.selection.rows[0]]['id']}", lista_instaladores)

    with aba3:
        st.caption("Histórico de serviços concluídos e faturados.")
        hoje = datetime.date.today()
        ano_atual = hoje.year
        mes_atual_idx = hoje.month

        df_fin['Ano'] = df_fin['data_conclusao'].dt.year.fillna(ano_atual).astype(int)
        df_fin['Mes_idx'] = df_fin['data_conclusao'].dt.month.fillna(mes_atual_idx).astype(int)

        # Serviço que o instalador já confirmou como pronto pelo app, mas
        # que o Breno ainda não fechou como Concluído PIX/CARTÃO (cliente
        # ainda não pagou). Continua aparecendo lá em cima em "Em Andamento"
        # normalmente — aqui ele só entra na parte de Pagamento aos
        # Instaladores do mês (nunca na grade principal de Finalizados),
        # agrupado pela data em que o INSTALADOR marcou como concluída
        # (já que ainda não existe uma data de fechamento do admin).
        df_pronto_nao_pago = df[
            df['instalacao_concluida_instalador'].fillna(False).astype(bool)
            & (~df['status_projeto'].isin(['Concluído PIX', 'Concluído CARTÃO']))
        ].copy()
        _data_conc_inst = pd.to_datetime(df_pronto_nao_pago['data_conclusao_instalador'], errors='coerce')
        df_pronto_nao_pago['Ano'] = _data_conc_inst.dt.year.fillna(ano_atual).astype(int)
        df_pronto_nao_pago['Mes_idx'] = _data_conc_inst.dt.month.fillna(mes_atual_idx).astype(int)

        anos_disponiveis = sorted(list(set(df_fin['Ano'].unique()) | set(df_pronto_nao_pago['Ano'].unique()) | {ano_atual}), reverse=True)

        c_ano, c_mes, c_vazio = st.columns([1.5, 1.5, 7])
        with c_ano:
            ano_sel = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(ano_atual), key="filtro_ano_fin")
        with c_mes:
            mes_sel = st.selectbox("Mês", utils.meses_pt, index=mes_atual_idx - 1, key="filtro_mes_fin")
            mes_sel_idx = utils.meses_pt.index(mes_sel) + 1

        df_fin_mes = df_fin[(df_fin['Ano'] == ano_sel) & (df_fin['Mes_idx'] == mes_sel_idx)].reset_index(drop=True)
        df_pronto_mes = df_pronto_nao_pago[(df_pronto_nao_pago['Ano'] == ano_sel) & (df_pronto_nao_pago['Mes_idx'] == mes_sel_idx)].reset_index(drop=True)

        if df_fin_mes.empty and df_pronto_mes.empty:
            st.info(f"Nenhum serviço finalizado registrado em {mes_sel} de {ano_sel}.")
        else:
            if not df_fin_mes.empty:
                sel_fin = st.dataframe(df_fin_mes[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key=f"g_fin_{ano_sel}_{mes_sel_idx}")
                total_bruto_fin_mes = pd.to_numeric(df_fin_mes['valor_venda_total'], errors='coerce').fillna(0).sum()
                total_lucro_fin_mes = pd.to_numeric(df_fin_mes['lucro_estimado'], errors='coerce').fillna(0).sum()
                st.markdown(f"<div style='text-align: right; font-size: 18px; font-weight: bold; margin-bottom: 20px;'><span style='color: #555; margin-right: 20px;'>Faturamento Bruto ({mes_sel}): {utils.to_br_currency(total_bruto_fin_mes)}</span> <span style='color: #004488;'>Lucro Líquido Realizado: {utils.to_br_currency(total_lucro_fin_mes)}</span></div>", unsafe_allow_html=True)
            else:
                sel_fin = None
                st.info(f"Nenhum serviço fechado com o cliente ainda em {mes_sel} de {ano_sel} — só pagamento de instalador pendente abaixo.")

            df_pagamento_mes = pd.concat([df_fin_mes, df_pronto_mes], ignore_index=True) if not df_pronto_mes.empty else df_fin_mes
            renderizar_pagamento_instaladores(df_pagamento_mes, supabase, f"{ano_sel}_{mes_sel_idx}", f"Pagamento aos Instaladores — {mes_sel}")

            if sel_fin is not None and sel_fin.selection.rows and len(df_fin_mes) > sel_fin.selection.rows[0]:
                servicos_painel.exibir_painel_detalhado(df_fin_mes.iloc[sel_fin.selection.rows[0]], supabase, df_taxas, df_produtos, f"fin_{df_fin_mes.iloc[sel_fin.selection.rows[0]]['id']}", lista_instaladores)
