import streamlit as st
import pandas as pd
import numpy as np
import datetime
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
# 2. LÓGICA DE TEMPO E FORMATAÇÃO (SEM CENTAVOS)
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
mes_hoje_idx = hoje.month 
mes_atual_nome = meses_pt[mes_hoje_idx - 1] 

def formata_br(valor):
    # Formata com separador de milhar brasileiro (ponto) nas tabelas de resultado
    if pd.isna(valor): 
        return "R$ 0"
    try:
        v = float(valor)
        if v == 0: 
            return "R$ 0"
        return f"R$ {v:,.0f}".replace(",", ".")
    except: 
        return valor

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
    
    /* Esconde os cabeçalhos das tabelas de baixo para colar tudo */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead { display: none !important; }
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead { display: none !important; }
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. FUNÇÕES DE DADOS (BLINDADAS CONTRA ERROS)
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

def save_to_supabase(table_name, df, ano_escolhido):
    try:
        df_melted = df.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
        df_melted['ano'] = ano_escolhido
        df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
        
        # Garante que vai salvar como número inteiro perfeitamente formatado
        df_melted['valor'] = df_melted['valor'].apply(lambda x: int(float(x)))
        data = df_melted.to_dict(orient='records')
        
        # TÉCNICA DE BLINDAGEM: Apaga os registros do ano selecionado e insere de novo
        # Isso resolve 100% o APIError de upsert por falta de Primary Key
        supabase.table(table_name).delete().eq('ano', ano_escolhido).execute()
        supabase.table(table_name).insert(data).execute()
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")

# ==========================================
# 5. MENU LATERAL E INICIALIZAÇÃO
# ==========================================
with st.sidebar:
    st.title("📈 Consorbens Wealth")
    ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
    if st.button("🔄 Recarregar Dados da Nuvem"):
        st.session_state.clear()
        st.rerun()

contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state:
    st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
if 'df_e' not in st.session_state:
    st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)

# Formatação visual para edição. Usa vírgula por limitação do Streamlit, mas fica mais bonito que o número puro.
col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=220, disabled=True)}
for m in meses_pt: 
    col_cfg[m] = st.column_config.NumberColumn(m, width=80, format="%,d", step=1)

st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# ==========================================
# 7. TABELA 1: PATRIMÔNIO (EDITÁVEL)
# ==========================================
# APLICA A COR NO MÊS ATUAL NA EDIÇÃO
styled_df_p = st.session_state.df_p.style.set_properties(
    subset=[mes_atual_nome], 
    **{'background-color': '#e0f0ff', 'font-weight': 'bold', 'color': '#000'}
)

df_p_edit = st.data_editor(styled_df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=295)

if not df_p_edit.equals(st.session_state.df_p):
    save_to_supabase('patrimonio', df_p_edit, ano_selecionado)
    st.session_state.df_p = df_p_edit
    st.toast("💾 Patrimônio salvo no Supabase!", icon="✅")
    st.rerun()

# --- CÁLCULOS PATRIMÔNIO ---
df_n = st.session_state.df_p.set_index('MESES')
pat_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
pat_tot = pat_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
var_abs = pat_tot.diff().fillna(0)
var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
for m in meses_pt: 
    df_res_p[m] = [pat_liq[m], pat_tot[m], var_abs[m], f"{var_pct[m]:.2f}%"]

# --- TABELA 2: RESULTADOS PATRIMÔNIO ---
def style_res_p(row):
    styles = []
    for col in df_res_p.columns:
        bg = 'white'
        if row['MESES'] == 'PATRIMÔNIO LÍQUIDO': bg = '#FFF2CC'
        elif row['MESES'] == 'PATRIMÔNIO TOTAL': bg = '#FF9900'
        
        # Borda azul e fundo se for a coluna do mês atual
        if col == mes_atual_nome:
            styles.append(f'background-color: {bg}; font-weight: bold; color: black; border-left: 3px solid #4A90E2; border-right: 3px solid #4A90E2;')
        else:
            styles.append(f'background-color: {bg}; font-weight: bold; color: black; border-bottom: 1px solid #ddd;')
    return styles

# APLICA AS CORES E O FORMATO "R$ 1.000" PERFEITAMENTE
styled_res_p = df_res_p.style.apply(style_res_p, axis=1).format(
    lambda x: formata_br(x) if isinstance(x, (int, float, np.integer, np.floating)) else x
)

st.dataframe(styled_res_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

# ==========================================
# 8. TABELA 3: ENTRADAS
# ==========================================
styled_df_e = st.session_state.df_e.style.set_properties(
    subset=[mes_atual_nome], 
    **{'background-color': '#e0f0ff', 'font-weight': 'bold', 'color': '#000'}
)

df_e_edit = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

if not df_e_edit.equals(st.session_state.df_e):
    save_to_supabase('entradas', df_e_edit, ano_selecionado)
    st.session_state.df_e = df_e_edit
    st.toast("💾 Entradas salvas no Supabase!", icon="✅")
    st.rerun()

# --- CÁLCULOS ENTRADAS ---
tot_ent = st.session_state.df_e.set_index('MESES').sum()
df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
for m in meses_pt: df_res_e[m] = [tot_ent[m]]

# --- TABELA 4: RESULTADO ENTRADAS ---
def style_res_e(row):
    styles = []
    for col in df_res_e.columns:
        if col == mes_atual_nome:
            styles.append('background-color: #9BC2E6; font-weight: bold; color: black; border-left: 3px solid #4A90E2; border-right: 3px solid #4A90E2;')
        else:
            styles.append('background-color: #9BC2E6; font-weight: bold; color: black;')
    return styles

styled_res_e = df_res_e.style.apply(style_res_e, axis=1).format(
    lambda x: formata_br(x) if isinstance(x, (int, float, np.integer, np.floating)) else x
)

st.dataframe(styled_res_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 9. MÉTRICAS FINAIS
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
idx_ref = mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0

m1.metric("MÉDIA RECEBIMENTOS", formata_br(tot_ent.mean()))
m2.metric("PATRIMÔNIO ATUAL", formata_br(pat_tot.iloc[idx_ref]))
m3.metric("VAR. NO ANO ($)", formata_br(pat_tot.iloc[idx_ref] - pat_tot.iloc[0]))
crescimento_pct = ((pat_tot.iloc[idx_ref] / pat_tot.iloc[0] - 1) * 100) if pat_tot.iloc[0] != 0 else 0
m4.metric("CRESCIMENTO NO ANO (%)", f"{crescimento_pct:,.2f}%")
