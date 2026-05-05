import streamlit as st
import pandas as pd
import numpy as np
import datetime
from supabase import create_client, Client

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# 2. CONEXÃO DIRETA COM SUPABASE (SEGURA E LIMPA)
@st.cache_resource
def init_connection():
    # Suas chaves exatas, com limpeza automática de espaços invisíveis
    url = "https://ldoxfmdajhamdfrksyby.supabase.co".strip()
    key = "sb_publishable_dWLIIeBa7Yj68FP4W4uq2A_ljsHb6W2".strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro na conexão com o banco de dados: {e}")

# 3. LÓGICA DE TEMPO
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_hoje = hoje.year
mes_hoje_idx = hoje.month # Janeiro = 1, Maio = 5

# Coluna CSS: 1 (MESES), 2 (JAN), 3 (FEV)... 6 (MAIO)
coluna_css_idx = mes_hoje_idx + 1 

# 4. ESTILIZAÇÃO CSS (COR DO MÊS, LARGURA E GAVETA)
st.markdown(f"""
    <style>
    .block-container {{ padding-top: 2rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }}
    div.container-tabelas div[data-testid="stVerticalBlock"] {{ gap: 0px !important; padding: 0px !important; }}
    
    /* Trava de largura para caber o ano todo na tela */
    .stDataFrame table, .stDataEditor table {{ table-layout: fixed !important; width: 100% !important; }}
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th {{ text-align: center !important; font-size: 0.85rem !important; }}

    /* OCULTAR CABEÇALHOS DAS TABELAS DE BAIXO */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead {{ display: none !important; }}
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead {{ display: none !important; }}
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead {{ display: none !important; }}

    /* COR DO MÊS ATUAL EM TODAS AS TABELAS (EDITÁVEIS OU NÃO) */
    /* Seleciona a coluna baseada no mês atual */
    section.main div[data-testid="stDataEditor"] td:nth-child({coluna_css_idx}), 
    section.main div[data-testid="stDataEditor"] th:nth-child({coluna_css_idx}),
    section.main div[data-testid="stDataFrame"] td:nth-child({coluna_css_idx}) {{
        background-color: #E2E8F0 !important; /* Cinza destaque */
        font-weight: bold !important;
    }}

    /* Estilo dos Indicadores */
    div[data-testid="stMetricValue"] {{ font-size: 1.1rem !important; }}
    div[data-testid="stMetricLabel"] {{ font-size: 0.75rem !important; font-weight: bold !important; }}
    div[data-testid="stMetric"] {{
        background-color: #ffffff; padding: 5px 10px !important; border-radius: 5px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;
    }}
    </style>
""", unsafe_allow_html=True)

# 5. FUNÇÕES DE BANCO DE DADOS (CARREGAR E SALVAR)
def load_year_data(table_name, itens_padrao, ano_escolhido):
    try:
        res = supabase.table(table_name).select("*").eq("ano", ano_escolhido).execute()
        df_raw = pd.DataFrame(res.data)
        
        if df_raw.empty:
            df = pd.DataFrame(0.0, index=range(len(itens_padrao)), columns=meses_pt)
            df.insert(0, 'MESES', itens_padrao)
            return df
        
        # Transforma linhas em colunas
        df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0)
        for m in meses_pt:
            if m not in df_pivot.columns: df_pivot[m] = 0.0
        
        df_pivot = df_pivot[meses_pt].reset_index()
        df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
        
        # Garante que todas as contas padrão apareçam
        for item in itens_padrao:
            if item not in df_pivot['MESES'].values:
                nova_linha = {m: 0.0 for m in meses_pt}
                nova_linha['MESES'] = item
                df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
        
        return df_pivot
    except:
        df = pd.DataFrame(0.0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao)
        return df

def save_to_supabase(table_name, df, ano_escolhido):
    df_melted = df.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
    df_melted['ano'] = ano_escolhido
    df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
    data = df_melted.to_dict(orient='records')
    supabase.table(table_name).upsert(data).execute()

# 6. INTERFACE LATERAL
with st.sidebar:
    st.title("📈 Consorbens Wealth")
    ano_selecionado = st.selectbox("Escolha o Ano", options=[2025, 2026, 2027, 2028], index=1)
    
    st.write("---")
    if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
        with st.spinner("Salvando no Supabase..."):
            save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado)
            save_to_supabase('entradas', st.session_state.df_e, ano_selecionado)
        st.success(f"Dados de {ano_selecionado} salvos!")

    if st.button("🔄 Recarregar Dados"):
        st.session_state.clear()
        st.rerun()

# 7. CARREGAMENTO DOS DADOS
contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state:
    st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
if 'df_e' not in st.session_state:
    st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)

# 8. CONFIGURAÇÃO DE COLUNAS (LARGURA FIXA)
col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=200, disabled=True)}
for m in meses_pt:
    col_cfg[m] = st.column_config.NumberColumn(m, width=70, format="%.2f")

# 9. RENDERIZAÇÃO DO DASHBOARD
st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# --- TABELA 1: PATRIMÔNIO EDITÁVEL ---
st.session_state.df_p = st.data_editor(st.session_state.df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=275)

# Cálculos de Patrimônio
df_n = st.session_state.df_p.set_index('MESES')
patr_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
patr_total = patr_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
var_abs = patr_total.diff().fillna(0)
var_pct = (patr_total.pct_change().fillna(0) * 100).round(2)

df_res_p = pd.DataFrame({'MESES': ['PATR. LÍQUIDO', 'PATR. TOTAL', 'VAR. MENSAL ($)', 'VAR. MENSAL (%)']})
for m in meses_pt:
    df_res_p[m] = [patr_liq[m], patr_total[m], var_abs[m], var_pct[m]]

# --- TABELA 2: RESULTADOS PATRIMÔNIO (CORES ESTÁTICAS) ---
def style_p(row):
    color = 'white'
    if row['MESES'] == 'PATR. LÍQUIDO': color = '#FFF2CC'
    if row['MESES'] == 'PATR. TOTAL': color = '#FF9900'
    return [f'background-color: {color}; font-weight: bold; color: black; border-bottom: 1px solid #ddd;'] * len(row)

st.dataframe(df_res_p.style.apply(style_p, axis=1), hide_index=True, column_config=col_cfg, use_container_width=True, height=145)

# --- TABELA 3: ENTRADAS EDITÁVEL ---
st.session_state.df_e = st.data_editor(st.session_state.df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=170)

# Cálculos de Entradas
salario_total = st.session_state.df_e.set_index('MESES').sum()
df_res_e = pd.DataFrame({'MESES': ['TOTAL ENTRADAS:']})
for m in meses_pt: df_res_e[m] = [salario_total[m]]

# --- TABELA 4: RESULTADO ENTRADAS ---
st.dataframe(df_res_e.style.apply(lambda x: ['background-color: #9BC2E6; font-weight: bold; color: black;'] * len(x), axis=1), 
             hide_index=True, column_config=col_cfg, use_container_width=True, height=45)

st.markdown('</div>', unsafe_allow_html=True)

# 10. INDICADORES FINAIS
st.markdown("<br>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("MÉDIA ENTRADAS", f"R$ {salario_total.mean():,.2f}")
c2.metric("PATRIMÔNIO ATUAL", f"R$ {patr_total.iloc[mes_hoje_idx-1]:,.2f}")
c3.metric("VAR. NO ANO ($)", f"R$ {patr_total.iloc[mes_hoje_idx-1] - patr_total.iloc[0]:,.2f}")
c4.metric("VAR. NO ANO (%)", f"{((patr_total.iloc[mes_hoje_idx-1] / patr_total.iloc[0] - 1)*100):,.2f}%")
