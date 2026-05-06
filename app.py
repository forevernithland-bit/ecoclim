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
# 2. LÓGICA DE TEMPO E FORMATAÇÃO
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_atual = hoje.year
mes_hoje_idx = hoje.month 
mes_atual_nome = meses_pt[mes_hoje_idx - 1] 

def to_br_currency(val):
    try:
        v = int(float(val))
        if v == 0: return "R$ 0"
        return f"R$ {v:,}".replace(",", ".")
    except: return "R$ 0"

def parse_br_currency(val):
    try:
        if isinstance(val, (int, float)): return int(val)
        clean = re.sub(r'[^\d-]', '', str(val))
        if clean == "": return 0
        return int(clean)
    except: return 0

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
    
    /* Esconde cabeçalhos das tabelas de resultado */
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
                nova_linha = {m: 0 for m in meses_pt}; nova_linha['MESES'] = item
                df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
        df_pivot.set_index('MESES', inplace=True); df_pivot = df_pivot.reindex(itens_padrao).reset_index()
        df_pivot[meses_pt] = df_pivot[meses_pt].astype(int)
        return df_pivot
    except:
        df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao); return df

def save_to_supabase(table_name, df_int, ano_escolhido):
    df_melted = df_int.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
    df_melted['ano'] = ano_escolhido; df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
    df_melted['valor'] = df_melted['valor'].astype(int)
    data = df_melted.to_dict(orient='records')
    supabase.table(table_name).delete().eq('ano', ano_escolhido).execute()
    supabase.table(table_name).insert(data).execute()

# ==========================================
# 5. MENU LATERAL E VISIBILIDADE
# ==========================================
with st.sidebar:
    st.title("📈 Consorbens Wealth")
    ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
    
    st.write("---")
    st.markdown("### 👁️ Colunas Visíveis")
    
    # Se for um ano passado (ex: 2025), mostra tudo por padrão. Se for o ano atual, mostra até o mês atual.
    meses_default = meses_pt if ano_selecionado < ano_atual else meses_pt[:mes_hoje_idx]
    
    meses_selecionados = st.multiselect(
        "Selecione os meses que deseja ver nas tabelas:", 
        options=meses_pt, 
        default=meses_default
    )
    
    # Previne que o app quebre se o usuário remover todos os meses
    if not meses_selecionados:
        meses_selecionados = [meses_pt[0]]

    colunas_visiveis = ["MESES"] + meses_selecionados

    if st.button("🔄 Recarregar Dados"):
        st.session_state.clear(); st.rerun()

# ==========================================
# 6. INICIALIZAÇÃO
# ==========================================
contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state: st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
if 'df_e' not in st.session_state: st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)

col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=220, disabled=True)}
for m in meses_pt: col_cfg[m] = st.column_config.TextColumn(m, width=80) 

st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# --- TABELA 1: PATRIMÔNIO ---
df_p_display = st.session_state.df_p[colunas_visiveis].copy()
for m in [c for c in colunas_visiveis if c != "MESES"]: 
    df_p_display[m] = df_p_display[m].apply(to_br_currency)

styled_df_p = df_p_display.style.set_properties(subset=[mes_atual_nome], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
df_p_edit_str = st.data_editor(styled_df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=295)

if not df_p_edit_str.equals(df_p_display):
    for m in [c for c in colunas_visiveis if c != "MESES"]:
        st.session_state.df_p.loc[:, m] = df_p_edit_str[m].apply(parse_br_currency)
    save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado)
    st.toast("💾 Salvo!", icon="✅"); st.rerun()

# Cálculos Patrimônio
df_n = st.session_state.df_p.set_index('MESES')
pat_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
pat_tot = pat_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
var_abs = pat_tot.diff().fillna(0)
var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

# TRAVA DO FUTURO INTELIGENTE (Só bloqueia se for no ano atual ou futuro)
for i, m in enumerate(meses_pt):
    is_future = False
    if ano_selecionado > ano_atual:
        is_future = True
    elif ano_selecionado == ano_atual and i > mes_hoje_idx - 1:
        is_future = True
        
    if is_future:
        var_abs[m] = 0
        var_pct[m] = 0

df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
for m in meses_pt: df_res_p[m] = [pat_liq[m], pat_tot[m], var_abs[m], f"{var_pct[m]:.2f}%"]

styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
st.dataframe(styled_res_p.format(lambda x: to_br_currency(x) if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

# --- TABELA 3: ENTRADAS ---
df_e_display = st.session_state.df_e[colunas_visiveis].copy()
for m in [c for c in colunas_visiveis if c != "MESES"]: 
    df_e_display[m] = df_e_display[m].apply(to_br_currency)

styled_df_e = df_e_display.style.set_properties(subset=[mes_atual_nome], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
df_e_edit_str = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

if not df_e_edit_str.equals(df_e_display):
    for m in [c for c in colunas_visiveis if c != "MESES"]:
        st.session_state.df_e.loc[:, m] = df_e_edit_str[m].apply(parse_br_currency)
    save_to_supabase('entradas', st.session_state.df_e, ano_selecionado)
    st.toast("💾 Salvo!", icon="✅"); st.rerun()

df_e_n = st.session_state.df_e.set_index('MESES')
tot_ent = df_e_n.sum()

df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
for m in meses_pt: df_res_e[m] = [tot_ent[m]]

styled_res_e = df_res_e[colunas_visiveis].style.apply(lambda row: [f'background-color: #9BC2E6; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
st.dataframe(styled_res_e.format(lambda x: to_br_currency(x) if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

# --- TABELA 5: RENDIMENTOS ---
st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
xp_val = df_n.loc['INVESTIMENTO XP']
inter_val = df_n.loc['CONTA INTER']
xp_var = xp_val.diff().fillna(0)
inter_var = inter_val.diff().fillna(0)
rend_total = xp_var + inter_var
prev_bal = (xp_val + inter_val).shift(1).fillna(0)

df_rend = pd.DataFrame({'MESES': ['VARIAÇÃO INVESTIMENTO XP', 'VARIAÇÃO CONTA INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
for i, m in enumerate(meses_pt):
    # Mesma lógica do futuro
    is_future = False
    if ano_selecionado > ano_atual:
        is_future = True
    elif ano_selecionado == ano_atual and i > mes_hoje_idx - 1:
        is_future = True

    if is_future: 
        df_rend[m] = [0, 0, 0, "0,00%", 0]
    else:
        rt = rend_total[m]; pb = prev_bal[m]
        pct_val = (rt / pb * 100) if pb > 0 else 0
        df_rend[m] = [xp_var[m], inter_var[m], rt, f"{pct_val:.2f}%".replace(".", ","), tot_ent[m] + rt]

styled_rend = df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
st.dataframe(styled_rend.format(lambda x: to_br_currency(x) if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=215)
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 9. MÉTRICAS E GRÁFICOS (ANO COMPLETO)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

# Define meses de cálculo para as médias (Para não distorcer a média dividindo por 12 se estivermos em Maio)
meses_calculo = meses_pt if ano_selecionado < ano_atual else meses_pt[:mes_hoje_idx]

media_entradas = tot_ent[meses_calculo].mean()
media_rend_r = rend_total[meses_calculo].mean()
media_rend_p = (rend_total[meses_calculo] / prev_bal[meses_calculo].replace(0, np.nan)).mean() * 100

# Se for ano passado, pega o valor de Dezembro, senão pega o do mês atual
idx_ref = 11 if ano_selecionado < ano_atual else (mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0)

c1.metric("💰 MÉDIA ENTRADAS FIXAS", to_br_currency(media_entradas))
c2.metric("🎯 LIMITE DE GASTO (MÉDIA REND.)", to_br_currency(media_rend_r), help="Média de rendimento da XP e Inter. Use como teto de gastos.")
c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
c4.metric("🏛️ PATRIMÔNIO ATUAL", to_br_currency(pat_tot.iloc[idx_ref]))

st.write("---")
# Gráficos Anuais Fixos (Mostram todos os 12 meses do ano selecionado)
g1, g2 = st.columns(2)
with g1:
    st.subheader("Aumento de Patrimônio Total")
    st.line_chart(pat_tot[meses_pt])
    
    st.subheader("Rendimento Mensal (R$)")
    st.bar_chart(rend_total[meses_pt])

with g2:
    st.subheader("Salário + Rendimento Mensal")
    sal_rend_data = tot_ent[meses_pt] + rend_total[meses_pt]
    st.area_chart(sal_rend_data)

    st.subheader("Faturamento Ecoclim")
    # Agora puxando do dataframe de entradas corretamente!
    ecoclim_data = df_e_n.loc['ECOCLIM'][meses_pt]
    st.line_chart(ecoclim_data)
