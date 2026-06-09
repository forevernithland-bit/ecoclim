import streamlit as st
import pandas as pd
import datetime
import utils
import servicos_painel

def deve_ir_para_finalizados(status, data_conc_str):
    if status in ["Concluído PIX", "Concluído CARTÃO"]:
        return True
    return False

def renderizar():
    # =========================================================================
    # CSS RESPONSIVO PARA CELULAR + CSS GLOBAL
    # =========================================================================
    st.markdown("""
        <style>
        /* CSS Nativo: Ocultar setinhas de number_inputs */
        div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] { 
            display: none !important; 
        }
        input[type=number]::-webkit-inner-spin-button, 
        input[type=number]::-webkit-outer-spin-button { 
            -webkit-appearance: none !important; 
            margin: 0 !important; 
        }
        input[type=number] { 
            -moz-appearance: textfield !important; 
        }

        /* Responsividade Mobile */
        @media screen and (max-width: 768px) {
            /* Permite scroll horizontal nas Dataframes para não espremer colunas */
            div[data-testid="stDataFrame"] {
                overflow-x: auto !important;
            }
            /* Empilha colunas no painel de detalhes do cliente */
            div[data-testid="column"] {
                width: 100% !important;
                min-width: 100% !important;
                display: block !important;
                margin-bottom: 0.8rem !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("## 📋 Gestão de Serviços")
    supabase = st.session_state.supabase
    
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
        alvos = ["Aguardando Pagamento", "Concluído PIX", "Concluído CARTÃO", "Aguardando Peças"]
        if status in alvos and pd.notna(row['data_conclusao']) and str(row['data_conclusao']).lower() not in ['nat', 'none', 'nan']:
            try:
                return pd.to_datetime(row['data_conclusao']).strftime('%d/%m/%Y')
            except:
                pass
        return ""
    df['Data de término'] = df.apply(descobrir_data_termino, axis=1)

    def descobrir_venc_fornecedor(row):
        venc = row.get('vencimento_boleto')
        if pd.notna(venc) and str(venc).strip().lower() not in ['none', 'nan', 'nat', '']:
            try: 
                return pd.to_datetime(venc).strftime('%d/%m/%Y')
            except: 
                return str(venc)
        return ""
    df['($) Fornecedor'] = df.apply(descobrir_venc_fornecedor, axis=1)

    ativos_status = ["Em Andamento", "Aguardando Pagamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]
    
    df_orc = df[(~df['status_projeto'].isin(ativos_status)) & (df['status_projeto'] != 'Rascunho') & (df['status_projeto'] != 'Rascunho Rápido')].reset_index(drop=True)
    df_fin = df[df['ir_finalizados'] == True].reset_index(drop=True)
    df_atv = df[(df['status_projeto'].isin(ativos_status)) & (df['ir_finalizados'] == False)].reset_index(drop=True)

    aba1, aba2, aba3 = st.tabs(["🚀 Em Andamento", "📝 Orçamentos", "✅ Finalizados"])
    
    colunas_visiveis = ['Cliente', 'Status', 'Valor Total', 'Lucro Líquido', 'Data de término', 'Instalador', '($) Fornecedor']
    
    config_colunas = {
        "Cliente": "Cliente",
        "Status": "Status",
        "Valor Total": st.column_config.TextColumn("Valor Total"),
        "Lucro Líquido": st.column_config.TextColumn("Lucro Líquido"),
        "Data de término": st.column_config.TextColumn("Data de término"),
        "Instalador": "Instalador",
        "($) Fornecedor": st.column_config.TextColumn("($) Fornecedor")
    }
    
    with aba1:
        sel = st.dataframe(df_atv[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key="g_atv")
        total_lucro_atv = pd.to_numeric(df_atv['lucro_estimado'], errors='coerce').fillna(0).sum()
        st.markdown(f"<div style='text-align: right; color: #004488; font-size: 18px; font-weight: bold; margin-bottom: 20px;'>Total Lucro Líquido Estimado: {utils.to_br_currency(total_lucro_atv)}</div>", unsafe_allow_html=True)
        if sel.selection.rows and len(df_atv) > sel.selection.rows[0]: 
            servicos_painel.exibir_painel_detalhado(df_atv.iloc[sel.selection.rows[0]], supabase, df_taxas, df_produtos, f"atv_{df_atv.iloc[sel.selection.rows[0]]['id']}", lista_instaladores)
    
    with aba2:
        sel = st.dataframe(df_orc[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key="g_orc")
        total_lucro_orc = pd.to_numeric(df_orc['lucro_estimado'], errors='coerce').fillna(0).sum()
        st.markdown(f"<div style='text-align: right; color: #004488; font-size: 18px; font-weight: bold; margin-bottom: 20px;'>Total Lucro Líquido Estimado: {utils.to_br_currency(total_lucro_orc)}</div>", unsafe_allow_html=True)
        if sel.selection.rows and len(df_orc) > sel.selection.rows[0]: 
            servicos_painel.exibir_painel_detalhado(df_orc.iloc[sel.selection.rows[0]], supabase, df_taxas, df_produtos, f"orc_{df_orc.iloc[sel.selection.rows[0]]['id']}", lista_instaladores)

    with aba3:
        st.caption("Histórico de serviços concluídos e faturados.")
        
        hoje = datetime.date.today()
        ano_atual = hoje.year
        mes_atual_idx = hoje.month

        df_fin['Ano'] = df_fin['data_conclusao'].dt.year.fillna(ano_atual).astype(int)
        df_fin['Mes_idx'] = df_fin['data_conclusao'].dt.month.fillna(mes_atual_idx).astype(int)

        anos_disponiveis = sorted(list(set(df_fin['Ano'].unique()) | {ano_atual}), reverse=True)

        c_ano, c_mes, c_vazio = st.columns([1.5, 1.5, 7])
        with c_ano:
            ano_sel = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(ano_atual), key="filtro_ano_fin")
        with c_mes:
            mes_sel = st.selectbox("Mês", utils.meses_pt, index=mes_atual_idx - 1, key="filtro_mes_fin")
            mes_sel_idx = utils.meses_pt.index(mes_sel) + 1

        df_fin_mes = df_fin[(df_fin['Ano'] == ano_sel) & (df_fin['Mes_idx'] == mes_sel_idx)].reset_index(drop=True)

        if df_fin_mes.empty:
            st.info(f"Nenhum serviço finalizado registrado em {mes_sel} de {ano_sel}.")
        else:
            sel_fin = st.dataframe(df_fin_mes[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key=f"g_fin_{ano_sel}_{mes_sel_idx}")
            
            total_lucro_fin_mes = pd.to_numeric(df_fin_mes['lucro_estimado'], errors='coerce').fillna(0).sum()
            st.markdown(f"<div style='text-align: right; color: #004488; font-size: 18px; font-weight: bold; margin-bottom: 20px;'>Total Lucro Líquido Realizado ({mes_sel}): {utils.to_br_currency(total_lucro_fin_mes)}</div>", unsafe_allow_html=True)
            
            if sel_fin.selection.rows and len(df_fin_mes) > sel_fin.selection.rows[0]: 
                servicos_painel.exibir_painel_detalhado(df_fin_mes.iloc[sel_fin.selection.rows[0]], supabase, df_taxas, df_produtos, f"fin_{df_fin_mes.iloc[sel_fin.selection.rows[0]]['id']}", lista_instaladores)
