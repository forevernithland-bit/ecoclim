import streamlit as st
import pandas as pd
import numpy as np
import datetime
from supabase import create_client, Client

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO (VIA SECRETS)
# ==========================================
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

@st.cache_resource
def init_connection():
    # Puxa as configurações que você inseriu na aba "Segredos" do Streamlit
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro na conexão: Verifique se as chaves em 'Segredos' estão corretas.")

# ==========================================
# 2. LÓGICA DE TEMPO E FORMATAÇÃO BR
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
mes_hoje_idx = hoje.month 
coluna_css_idx = mes_hoje_idx + 1 

def formata_br(valor):
    if pd.isna(valor) or valor == 0: return "R$ 0,00"
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return valor

# ==========================================
# 3. CSS COMPLETO (CORES E SEM SCROLL)
# ==========================================
st.markdown(f"""
    <style>
    .block-container {{ padding-top: 1.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }}
    div.container-tabelas div[data-testid="stVerticalBlock"] {{ gap: 0px !important; padding: 0px !important; }}
    
    /* REMOVE O SCROLL VERTICAL E AJUSTA LARGURA */
    [data-testid="stTable"] {{ overflow: hidden !important; }}
    .dvn-scroller {{ overflow-y: hidden !important; }}
    .stDataFrame table, .stDataEditor table {{ table-layout: fixed !important; width: 100% !important; }}
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th {{ text-align: center !important; font-size: 0.85rem !important; }}

    /* ESCONDE CABEÇALHOS REPETIDOS */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead {{ display: none !important; }}
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead {{ display: none !important; }}
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead {{ display: none !important; }}

    /* DESTAQUE DA COLUNA DO MÊS ATUAL */
    section.main div[data-testid="stDataEditor"] td:nth-child({coluna_css_idx}), 
    section.main div[data-testid="stDataFrame"] td:nth-child({coluna_css_idx}) {{
        background-color: #f0f7ff !important;
        font-weight: bold !important;
    }}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. FUNÇÕES DE DADOS (PUXANDO DO BANCO)
# ==========================================
def load_year_data(table_name, itens_padrao, ano_escolhido):
    try:
        res = supabase.table(table_name).select("*").eq("ano", ano_escolhido).execute()
        df_raw = pd.DataFrame(res.data)
        if df_raw.empty:
            df = pd.DataFrame(0.0, index=range(len(itens_padrao)), columns=meses_pt)
            df.insert(0, 'MESES', itens_padrao)
            return df
        
        df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0)
        # Garante que todos os meses existam
        for m in meses_pt:
            if m not in df_pivot.columns: df_pivot[m] = 0.0
        
        df_pivot = df_pivot[meses_pt].reset_index()
        df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
        
        # Garante que todas as contas padrão existam na ordem correta
        for item in itens_padrao:
            if item not in df_pivot['MESES'].values:
                nova_linha = {m: 0.0 for m in meses_pt}; nova_linha['MESES'] = item
                df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
        
        # Ordena conforme a lista 'itens_padrao'
        df_pivot.set_index('MESES', inplace=True)
        df_pivot = df_pivot.reindex(itens_padrao).reset_index()
        return df_pivot
    except Exception as e:
        st.error(f"Erro ao carregar {table_name}: {e}")
        df = pd.DataFrame(0.0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao); return df

def save_to_supabase(table_name, df, ano_escolhido):
    try:
        df_melted = df.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
        df_melted['ano'] = ano_escolhido
        df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
        data = df_melted.to_dict(orient='records')
        supabase.table(table_name).upsert(data).execute()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# ==========================================
# 5. DASHBOARD PRINCIPAL
# ==========================================
with st.sidebar:
    st.title("📈 Consorbens Wealth")
    ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
    if st.button("🔄 Forçar Recarregamento"):
        st.session_state.clear()
        st.rerun()

# Listas de contas (conforme suas imagens)
contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state:
    st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
if 'df_e' not in st.session_state:
    st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)

# Configuração visual das colunas
col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=200, disabled=True)}
for m in meses_pt: 
    col_cfg[m] = st.column_config.NumberColumn(m, width=80, format="R$ % ,.2f")

st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# --- TABELA 1: PATRIMÔNIO (EDITÁVEL) ---
df_p_edit = st.data_editor(st.session_state.df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=282)

if not df_p_edit.equals(st.session_state.df_p):
    st.session_state.df_p = df_p_edit
    save_to_supabase('patrimonio', df_p_edit, ano_selecionado)
    st.toast("💾 Salvo automaticamente!", icon="✅")
    st.rerun()

# --- CÁLCULOS PATRIMÔNIO ---
df_n = st.session_state.df_p.set_index('MESES')
pat_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
pat_tot = pat_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
var_abs = pat_tot.diff().fillna(0)
var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
for m in meses_pt: df_res_p[m] = [pat_liq[m], pat_tot[m], var_abs[m], f"{var_pct[m]:.2f}%"]

# --- TABELA 2: RESULTADOS (CORES FIXAS) ---
def style_res_p(row):
    color = 'white'
    if row['MESES'] == 'PATRIMÔNIO LÍQUIDO': color = '#FFF2CC'
    if row['MESES'] == 'PATRIMÔNIO TOTAL': color = '#FF9900'
    return [f'background-color: {color}; font-weight: bold; color: black; border-bottom: 1px solid #ddd;'] * len(row)

st.dataframe(df_res_p.style.apply(style_res_p, axis=1).format(lambda x: formata_br(x) if isinstance(x, (float, int)) else x),
             hide_index=True, column_config=col_cfg, use_container_width=True, height=155)

# --- TABELA 3: ENTRADAS (EDITÁVEL) ---
df_e_edit = st.data_editor(st.session_state.df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=180)

if not df_e_edit.equals(st.session_state.df_e):
    st.session_state.df_e = df_e_edit
    save_to_supabase('entradas', df_e_edit, ano_selecionado)
    st.toast("💾 Salvo automaticamente!", icon="✅")
    st.rerun()

# --- CÁLCULOS ENTRADAS ---
tot_ent = st.session_state.df_e.set_index('MESES').sum()
df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
for m in meses_pt: df_res_e[m] = [tot_ent[m]]

# --- TABELA 4: RESULTADO ENTRADAS ---
st.dataframe(df_res_e.style.apply(lambda x: ['background-color: #9BC2E6; font-weight: bold; color: black;'] * len(x), axis=1).format(lambda x: formata_br(x) if isinstance(x, (float, int)) else x),
             hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

st.markdown('</div>', unsafe_allow_html=True)

# MÉTRICAS FINAIS
st.markdown("<br>", unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
idx_ref = mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0
m1.metric("MÉDIA RECEBIMENTOS", formata_br(tot_ent.mean()))
m2.metric("PATRIMÔNIO ATUAL", formata_br(pat_tot.iloc[idx_ref]))
m3.metric("VAR. NO ANO ($)", formata_br(pat_tot.iloc[idx_ref] - pat_tot.iloc[0]))
m4.metric("CRESCIMENTO NO ANO (%)", f"{((pat_tot.iloc[idx_ref] / pat_tot.iloc[0] - 1)*100 if pat_tot.iloc[0] != 0 else 0):,.2f}%")
