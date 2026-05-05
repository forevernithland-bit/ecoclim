import streamlit as st
import pandas as pd
import numpy as np
import datetime
from supabase import create_client, Client

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- LÓGICA DE DATAS ---
hoje = datetime.datetime.now()
ano_atual = hoje.year
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
mes_atual_str = meses_pt[hoje.month - 1]
colunas_exibicao = ['MESES'] + meses_pt

# --- CONFIGURAÇÃO VISUAL (CSS) ---
st.markdown(f"""
    <style>
    .block-container {{ padding-top: 2rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }}
    div.container-tabelas div.st-emotion-cache-1wivap2 {{ gap: 0rem !important; }}
    div.container-tabelas div[data-testid="stVerticalBlock"] {{ gap: 0px !important; padding: 0px !important; }}
    .stDataFrame table, .stDataEditor table {{ table-layout: fixed !important; width: 100% !important; }}
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th {{ text-align: center !important; }}
    
    /* Gaveta para esconder cabeçalhos */
    section.main div[data-testid="stDataEditor"]:nth-of-type(1) {{ z-index: 10 !important; position: relative !important; }}
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) {{ z-index: 9 !important; position: relative !important; margin-top: -42px !important; }}
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) {{ z-index: 8 !important; position: relative !important; margin-top: -42px !important; }}
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) {{ z-index: 7 !important; position: relative !important; margin-top: -42px !important; }}

    /* Cor do Mês Atual via CSS (Garante funcionamento em tudo) */
    section.main [data-testid="stTable"] td:nth-child({hoje.month + 1}), 
    section.main [data-testid="stTable"] th:nth-child({hoje.month + 1}) {{
        background-color: #E2E8F0 !important;
    }}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE BANCO DE DADOS ---

def load_data(table_name, linhas_padrao):
    # Procura dados do ano atual
    res = supabase.table(table_name).select("*").eq("ano", ano_atual).execute()
    df_raw = pd.DataFrame(res.data)
    
    # Se o banco estiver vazio para este ano, cria estrutura inicial
    if df_raw.empty:
        df = pd.DataFrame(0.0, index=range(len(linhas_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', linhas_padrao)
        return df
    
    # "Pivot" - Transforma as linhas do banco em colunas para a nossa tabela
    df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0)
    
    # Garante que todos os meses existam como colunas
    for m in meses_pt:
        if m not in df_pivot.columns:
            df_pivot[m] = 0.0
            
    # Reorganiza para o nosso formato
    df_pivot = df_pivot[meses_pt].reset_index()
    df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
    
    # Garante que todas as linhas padrão existam (caso tenha adicionado contas novas no código)
    for linha in linhas_padrao:
        if linha not in df_pivot['MESES'].values:
            nova_linha = {m: 0.0 for m in meses_pt}
            nova_linha['MESES'] = linha
            df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
            
    return df_pivot

def save_data(table_name, df):
    # Transforma a tabela larga de volta em linhas (Melt)
    df_melted = df.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
    df_melted['ano'] = ano_atual
    df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
    
    # Envia para o Supabase (Upsert resolve: se existe atualiza, se não cria)
    data = df_melted.to_dict(orient='records')
    supabase.table(table_name).upsert(data).execute()

# --- INICIALIZAÇÃO ---
linhas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state:
    st.session_state.df_p = load_data('patrimonio', linhas_p)
if 'df_e' not in st.session_state:
    st.session_state.df_e = load_data('entradas', linhas_e)

# --- INTERFACE ---

with st.sidebar:
    st.title("📈 Consorbens")
    st.write(f"**Ano Fiscal: {ano_atual}**")
    if st.button("💾 SALVAR NO SUPABASE", type="primary", use_container_width=True):
        save_data('patrimonio', st.session_state.df_p)
        save_data('entradas', st.session_state.df_e)
        st.success("Dados guardados na nuvem!")
    
    if st.button("🔄 Atualizar Dados"):
        st.session_state.clear()
        st.rerun()

# --- RENDERIZAÇÃO DAS TABELAS ---

st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# Configuração de Colunas
col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=210, disabled=True)}
for m in meses_pt: col_cfg[m] = st.column_config.NumberColumn(m, width=70, format="R$ %.2f")

# Tabela 1: Edição Património
def style_row(row):
    return ['background-color: #E2E8F0; font-weight: bold;' if col == mes_atual_str else '' for col in row.index]

st.session_state.df_p = st.data_editor(st.session_state.df_p.style.apply(style_row, axis=1), 
                                      hide_index=True, column_config=col_cfg, use_container_width=True, height=280)

# Cálculos (Aqui você pode manter a lógica de cálculo que já tínhamos)
# ... [Lógica de somas e variações simplificada para o exemplo] ...
df_res_p = pd.DataFrame({'MESES': ['PATRIMONIO TOTAL']})
for m in meses_pt: df_res_p[m] = st.session_state.df_p[m].sum()

st.dataframe(df_res_p.style.apply(lambda x: ['background-color: #FF9900; font-weight: bold']*len(x), axis=1),
             hide_index=True, column_config=col_cfg, use_container_width=True, height=45)

# Tabela 2: Edição Entradas
st.session_state.df_e = st.data_editor(st.session_state.df_e.style.apply(style_row, axis=1), 
                                      hide_index=True, column_config=col_cfg, use_container_width=True, height=180)

st.markdown('</div>', unsafe_allow_html=True)
