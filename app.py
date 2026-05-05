import streamlit as st
import pandas as pd
import numpy as np
import datetime
from supabase import create_client, Client

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# 2. CONEXÃO SUPABASE
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro na conexão: {e}")

# 3. LÓGICA DE TEMPO
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_fiscal = hoje.year
mes_hoje_idx = hoje.month 

coluna_css_idx = mes_hoje_idx + 1 

# 4. FUNÇÃO DE FORMATAÇÃO BRASILEIRA (R$ 1.000.000,00)
def formata_br(valor):
    try:
        # Formata com separador de milhar americano (,) e decimal (.)
        # Depois troca para o padrão brasileiro
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

# 5. CSS NO CAPRICHO
st.markdown(f"""
    <style>
    .block-container {{ padding-top: 2rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }}
    div.container-tabelas div[data-testid="stVerticalBlock"] {{ gap: 0px !important; padding: 0px !important; }}
    .stDataFrame table, .stDataEditor table {{ table-layout: fixed !important; width: 100% !important; }}
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th {{ text-align: center !important; font-size: 0.88rem !important; }}

    /* ELIMINA SCROLL VERTICAL */
    [data-testid="stTable"] {{ overflow: hidden !important; }}
    .dvn-scroller {{ overflow-y: hidden !important; }}

    /* OCULTAR CABEÇALHOS DAS TABELAS DE BAIXO */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead {{ display: none !important; }}
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead {{ display: none !important; }}
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead {{ display: none !important; }}

    /* DESTAQUE DO MÊS ATUAL */
    section.main div[data-testid="stDataEditor"] td:nth-child({coluna_css_idx}), 
    section.main div[data-testid="stDataEditor"] th:nth-child({coluna_css_idx}),
    section.main div[data-testid="stDataFrame"] td:nth-child({coluna_css_idx}) {{
        background-color: #E8F0FE !important;
        font-weight: bold !important;
        color: #000 !important;
    }}
    </style>
""", unsafe_allow_html=True)

# 6. FUNÇÕES DE BANCO DE DADOS
def load_year_data(table_name, itens_padrao, ano_escolhido):
    res = supabase.table(table_name).select("*").eq("ano", ano_escolhido).execute()
    df_raw = pd.DataFrame(res.data)
    if df_raw.empty:
        df = pd.DataFrame(0.0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao)
        return df
    df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0)
    for m in meses_pt:
        if m not in df_pivot.columns: df_pivot[m] = 0.0
    df_pivot = df_pivot[meses_pt].reset_index()
    df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
    return df_pivot

def save_to_supabase(table_name, df, ano_escolhido):
    df_melted = df.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
    df_melted['ano'] = ano_escolhido
    df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
    data = df_melted.to_dict(orient='records')
    supabase.table(table_name).upsert(data).execute()

# 7. MENU LATERAL
with st.sidebar:
    st.title("📈 Consorbens Wealth")
    ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
    if st.button("🔄 Recarregar Dados"):
        st.session_state.clear()
        st.rerun()

# 8. INICIALIZAÇÃO DE DADOS
contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state:
    st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
if 'df_e' not in st.session_state:
    st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)

# 9. CONFIGURAÇÃO DE COLUNAS (FORMATO PARA EDIÇÃO)
col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=210, disabled=True)}
for m in meses_pt: 
    # O format % , .2f tenta induzir o separador de milhar na edição
    col_cfg[m] = st.column_config.NumberColumn(m, width=72, format="R$ % ,.2f")

# 10. DASHBOARD
st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# --- TABELA 1: PATRIMÔNIO (AUTO-SAVE AO DAR ENTER) ---
df_p_editado = st.data_editor(st.session_state.df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=290)

if not df_p_editado.equals(st.session_state.df_p):
    st.session_state.df_p = df_p_editado
    save_to_supabase('patrimonio', df_p_editado, ano_selecionado)
    st.toast("✅ Patrimônio salvo!")
    st.rerun()

# Cálculos
df_n = st.session_state.df_p.set_index('MESES')
patr_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
patr_total = patr_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
var_abs = patr_total.diff().fillna(0)
var_pct = (patr_total.pct_change().fillna(0) * 100).round(2)

df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
for m in meses_pt: df_res_p[m] = [patr_liq[m], patr_total[m], var_abs[m], var_pct[m]]

# --- TABELA 2: RESULTADOS PATRIMÔNIO (COM FORMATAÇÃO BRASILEIRA FORÇADA) ---
st.dataframe(df_res_p.style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; color: black; border-bottom: 1px solid #ddd;'] * len(row), axis=1)
             .format(lambda x: formata_br(x) if isinstance(x, (int, float)) else x),
             hide_index=True, column_config=col_cfg, use_container_width=True, height=155)

# --- TABELA 3: ENTRADAS (AUTO-SAVE AO DAR ENTER) ---
df_e_editado = st.data_editor(st.session_state.df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=185)

if not df_e_editado.equals(st.session_state.df_e):
    st.session_state.df_e = df_e_editado
    save_to_supabase('entradas', df_e_editado, ano_selecionado)
    st.toast("✅ Entradas salvas!")
    st.rerun()

salario_total = st.session_state.df_e.set_index('MESES').sum()
df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
for m in meses_pt: df_res_e[m] = [salario_total[m]]

# --- TABELA 4: RESULTADO ENTRADAS ---
st.dataframe(df_res_e.style.apply(lambda x: ['background-color: #9BC2E6; font-weight: bold; color: black;'] * len(x), axis=1)
             .format(lambda x: formata_br(x) if isinstance(x, (int, float)) else x), 
             hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

st.markdown('</div>', unsafe_allow_html=True)

# 11. MÉTRICAS
st.markdown("<br>", unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
idx_ref = mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0
m1.metric("MÉDIA RECEBIMENTOS", formata_br(salario_total.mean()))
m2.metric("PATRIMÔNIO ATUAL", formata_br(patr_total.iloc[idx_ref]))
m3.metric("VAR. NO ANO ($)", formata_br(patr_total.iloc[idx_ref] - patr_total.iloc[0]))
m4.metric("CRESCIMENTO NO ANO (%)", f"{((patr_total.iloc[idx_ref] / patr_total.iloc[0] - 1)*100 if patr_total.iloc[0] != 0 else 0):,.2f}%")
