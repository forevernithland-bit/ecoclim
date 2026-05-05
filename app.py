import streamlit as st
import pandas as pd
import numpy as np
import datetime
import re
from supabase import create_client

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO
# ==========================================
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro ao conectar com Supabase: {e}")

# ==========================================
# 2. LÓGICA DE TEMPO E FORMATAÇÃO 100% BRASILEIRA
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
mes_hoje_idx = hoje.month 
mes_atual_nome = meses_pt[mes_hoje_idx - 1] 

def to_br_currency(val):
    try:
        v = int(float(val))
        if v == 0: 
            return "R$ 0"
        return f"R$ {v:,}".replace(",", ".")
    except:
        return "R$ 0"

def parse_br_currency(val):
    try:
        if isinstance(val, (int, float)): return int(val)
        clean = re.sub(r'[^\d-]', '', str(val))
        if clean == "": return 0
        return int(clean)
    except:
        return 0

# ==========================================
# 3. CSS (LARGURAS E ESTRUTURA)
# ==========================================
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }
    div.container-tabelas div[data-testid="stVerticalBlock"] { gap: 0px !important; padding: 0px !important; }
    [data-testid="stTable"] { overflow: hidden !important; }
    .dvn-scroller { overflow-y: hidden !important; }
    
    .stDataFrame table, .stDataEditor table { table-layout: fixed !important; width: 100% !important; }
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { text-align: center !important; font-size: 0.85rem !important; }
    
    /* Esconde cabeçalhos redundantes */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead { display: none !important; }
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead { display: none !important; }
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead { display: none !important; }
    section.main div[data-testid="stDataFrame"]:nth-of-type(3) thead { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. FUNÇÕES DE DADOS 
# ==========================================
def load_year_data(table_name, itens_padrao, ano_escolhido):
    try:
        res = supabase.table(table_name).select("*").eq("ano", ano_escolhido).execute()
        df_raw = pd.DataFrame(res.data)
        
        if df_raw.empty:
            df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
            df.insert(0, 'MESES', itens_padrao)
            return df
        
        df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0)
        for m in meses_pt:
            if m not in df_pivot.columns: df_pivot[m] = 0
            
        df_pivot = df_pivot[meses_pt].reset_index()
        df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
        
        for item in itens_padrao:
            if item not in df_pivot['MESES'].values:
                nova_linha = {m: 0 for m in meses_pt}
                nova_linha['MESES'] = item
                df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
        
        df_pivot.set_index('MESES', inplace=True)
        df_pivot = df_pivot.reindex(itens_padrao).reset_index()
        df_pivot[meses_pt] = df_pivot[meses_pt].astype(int)
        
        return df_pivot
    except Exception as e:
        df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao)
        return df

def save_to_supabase(table_name, df_int, ano_escolhido):
    try:
        df_melted = df_int.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
        df_melted['ano'] = ano_escolhido
        df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
        df_melted['valor'] = df_melted['valor'].astype(int)
        data = df_melted.to_dict(orient='records')
        
        supabase.table(table_name).delete().eq('ano', ano_escolhido).execute()
        supabase.table(table_name).insert(data).execute()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# ==========================================
# 5. MENU LATERAL
# ==========================================
with st.sidebar:
    st.title("📈 Consorbens Wealth")
    ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
    if st.button("🔄 Recarregar Dados"):
        st.session_state.clear()
        st.rerun()

contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state: st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
if 'df_e' not in st.session_state: st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)

col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=220, disabled=True)}
for m in meses_pt: col_cfg[m] = st.column_config.TextColumn(m, width=80) 

st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# ==========================================
# 6. TABELA 1: PATRIMÔNIO
# ==========================================
df_p_display = st.session_state.df_p.copy()
for m in meses_pt: df_p_display[m] = df_p_display[m].apply(to_br_currency)

styled_df_p = df_p_display.style.set_properties(
    subset=[mes_atual_nome], 
    **{'background-color': '#e0f0ff', 'font-weight': 'bold', 'color': '#000'}
)

df_p_edit_str = st.data_editor(styled_df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=295)

if not df_p_edit_str.equals(df_p_display):
    novo_df_p_int = df_p_edit_str.copy()
    for m in meses_pt: novo_df_p_int[m] = novo_df_p_int[m].apply(parse_br_currency)
    save_to_supabase('patrimonio', novo_df_p_int, ano_selecionado)
    st.session_state.df_p = novo_df_p_int
    st.toast("💾 Salvo com sucesso!", icon="✅")
    st.rerun()

# --- CÁLCULOS PATRIMÔNIO ---
df_n = st.session_state.df_p.set_index('MESES')
pat_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
pat_tot = pat_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
var_abs = pat_tot.diff().fillna(0)
var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

# TRAVA DO FUTURO: Zera as variações de meses que ainda não chegaram
for i, m in enumerate(meses_pt):
    if i > mes_hoje_idx - 1:
        var_abs[m] = 0
        var_pct[m] = 0

df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
for m in meses_pt: df_res_p[m] = [pat_liq[m], pat_tot[m], var_abs[m], f"{var_pct[m]:.2f}%"]

def style_res_p(row):
    styles = []
    for col in df_res_p.columns:
        bg = 'white'
        if row['MESES'] == 'PATRIMÔNIO LÍQUIDO': bg = '#FFF2CC'
        elif row['MESES'] == 'PATRIMÔNIO TOTAL': bg = '#FF9900'
        
        if col == mes_atual_nome: 
            styles.append(f'background-color: {bg}; font-weight: bold; color: black; border-left: 3px solid #4A90E2; border-right: 3px solid #4A90E2;')
        else:
            styles.append(f'background-color: {bg}; font-weight: bold; color: black; border-bottom: 1px solid #ddd;')
    return styles

styled_res_p = df_res_p.style.apply(style_res_p, axis=1).format(
    lambda x: to_br_currency(x) if isinstance(x, (int, float, np.integer, np.floating)) else x
)
st.dataframe(styled_res_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

# ==========================================
# 7. TABELA 3: ENTRADAS
# ==========================================
df_e_display = st.session_state.df_e.copy()
for m in meses_pt: df_e_display[m] = df_e_display[m].apply(to_br_currency)

styled_df_e = df_e_display.style.set_properties(
    subset=[mes_atual_nome], 
    **{'background-color': '#e0f0ff', 'font-weight': 'bold', 'color': '#000'}
)

df_e_edit_str = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

if not df_e_edit_str.equals(df_e_display):
    novo_df_e_int = df_e_edit_str.copy()
    for m in meses_pt: novo_df_e_int[m] = novo_df_e_int[m].apply(parse_br_currency)
    save_to_supabase('entradas', novo_df_e_int, ano_selecionado)
    st.session_state.df_e = novo_df_e_int
    st.toast("💾 Salvo com sucesso!", icon="✅")
    st.rerun()

tot_ent = st.session_state.df_e.set_index('MESES').sum()
df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
for m in meses_pt: df_res_e[m] = [tot_ent[m]]

def style_res_e(row):
    styles = []
    for col in df_res_e.columns:
        if col == mes_atual_nome:
            styles.append('background-color: #9BC2E6; font-weight: bold; color: black; border-left: 3px solid #4A90E2; border-right: 3px solid #4A90E2;')
        else:
            styles.append('background-color: #9BC2E6; font-weight: bold; color: black;')
    return styles

styled_res_e = df_res_e.style.apply(style_res_e, axis=1).format(
    lambda x: to_br_currency(x) if isinstance(x, (int, float, np.integer, np.floating)) else x
)
st.dataframe(styled_res_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

# ==========================================
# 8. TABELA 5: RENDIMENTO MENSAL (NOVO)
# ==========================================
st.markdown("#### 📈 Rendimento Mensal (Investimentos)")

xp_val = df_n.loc['INVESTIMENTO XP']
inter_val = df_n.loc['CONTA INTER']

# Calcula os rendimentos isolados (variação mensal)
xp_var = xp_val.diff().fillna(0)
inter_var = inter_val.diff().fillna(0)
rend_total = xp_var + inter_var

# Saldo do mês anterior para calcular o Retorno %
prev_bal = (xp_val + inter_val).shift(1).fillna(0)

df_rend = pd.DataFrame({'MESES': [
    'VARIAÇÃO INVESTIMENTO XP',
    'VARIAÇÃO CONTA INTER',
    'RENDIMENTO TOTAL',
    '% RETORNO MÊS',
    'SALÁRIO + RENDIMENTO MÊS'
]})

# Alimenta a tabela aplicando a trava de meses futuros
for i, m in enumerate(meses_pt):
    if i > mes_hoje_idx - 1:
        df_rend[m] = [0, 0, 0, "0,00%", 0]
    else:
        pb = prev_bal[m]
        rt = rend_total[m]
        pct = f"{(rt / pb) * 100:.2f}%".replace(".", ",") if pb > 0 else "0,00%"
        sal_rend = tot_ent[m] + rt
        df_rend[m] = [xp_var[m], inter_var[m], rt, pct, sal_rend]

def style_rend(row):
    styles = []
    for col in df_rend.columns:
        bg = 'white'
        if row['MESES'] == 'RENDIMENTO TOTAL': bg = '#FF9900'
        elif row['MESES'] == '% RETORNO MÊS': bg = '#FFF2CC'
        elif row['MESES'] == 'SALÁRIO + RENDIMENTO MÊS': bg = '#9BC2E6'
        
        if col == mes_atual_nome:
            styles.append(f'background-color: {bg}; font-weight: bold; color: black; border-left: 3px solid #4A90E2; border-right: 3px solid #4A90E2;')
        else:
            styles.append(f'background-color: {bg}; font-weight: bold; color: black; border-bottom: 1px solid #ddd;')
    return styles

styled_rend = df_rend.style.apply(style_rend, axis=1).format(
    lambda x: to_br_currency(x) if isinstance(x, (int, float, np.integer, np.floating)) else x
)
st.dataframe(styled_rend, hide_index=True, column_config=col_cfg, use_container_width=True, height=215)
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 9. MÉTRICAS FINAIS
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
idx_ref = mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0

m1.metric("MÉDIA RECEBIMENTOS", to_br_currency(tot_ent.mean()))
m2.metric("PATRIMÔNIO ATUAL", to_br_currency(pat_tot.iloc[idx_ref]))
m3.metric("VAR. NO ANO ($)", to_br_currency(pat_tot.iloc[idx_ref] - pat_tot.iloc[0]))
crescimento_pct = ((pat_tot.iloc[idx_ref] / pat_tot.iloc[0] - 1) * 100) if pat_tot.iloc[0] != 0 else 0
m4.metric("CRESCIMENTO NO ANO (%)", f"{crescimento_pct:,.2f}%".replace(".", ","))
