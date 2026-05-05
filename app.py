import streamlit as st
import pandas as pd
import numpy as np
import datetime
from supabase import create_client, Client

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

@st.cache_resource
def init_connection():
    url = "https://ldoxfmdajhamdfrksyby.supabase.co".strip()
    key = "sb_publishable_dWLIIeBa7Yj68FP4W4uq2A_ljsHb6W2".strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro na conexão com Supabase: {e}")

# ==========================================
# 2. LÓGICA DE TEMPO E FORMATAÇÃO
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_fiscal = hoje.year
mes_hoje_idx = hoje.month # Ex: 5 para Maio

# Ajuste do CSS para pintar a coluna correta (MESES = 1, JAN = 2... MAIO = 6)
coluna_css_idx = mes_hoje_idx + 1 

# Função para forçar o formato R$ 1.000.000,00 nos resultados finais
def formata_br(valor):
    if pd.isna(valor):
        return "R$ 0,00"
    try:
        # Formata no padrão americano e depois inverte ponto e vírgula
        formatado = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return formatado
    except:
        return valor

# ==========================================
# 3. CSS (VISUAL LIMPO E SEM SCROLL VERTICAL)
# ==========================================
st.markdown(f"""
    <style>
    /* Aproveitamento máximo da tela */
    .block-container {{ padding-top: 2rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }}
    
    /* Remove os espaços de separação entre as tabelas */
    div.container-tabelas div[data-testid="stVerticalBlock"] {{ gap: 0px !important; padding: 0px !important; }}
    
    /* Trava largura e centraliza conteúdo */
    .stDataFrame table, .stDataEditor table {{ table-layout: fixed !important; width: 100% !important; }}
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th {{ text-align: center !important; font-size: 0.88rem !important; }}

    /* MATA O SCROLL VERTICAL DAS TABELAS */
    [data-testid="stTable"] {{ overflow: hidden !important; }}
    .dvn-scroller {{ overflow-y: hidden !important; }}

    /* ESCONDE OS CABEÇALHOS DAS TABELAS DE RESULTADO PARA PARECER UMA SÓ */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead {{ display: none !important; }}
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead {{ display: none !important; }}
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead {{ display: none !important; }}

    /* PINTA A COLUNA DO MÊS ATUAL */
    section.main div[data-testid="stDataEditor"] td:nth-child({coluna_css_idx}), 
    section.main div[data-testid="stDataEditor"] th:nth-child({coluna_css_idx}),
    section.main div[data-testid="stDataFrame"] td:nth-child({coluna_css_idx}) {{
        background-color: #E8F0FE !important; /* Azul clarinho elegante */
        font-weight: bold !important;
        color: #000 !important;
    }}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. FUNÇÕES DE DADOS (SUPABASE)
# ==========================================
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
    for item in itens_padrao:
        if item not in df_pivot['MESES'].values:
            nova_linha = {m: 0.0 for m in meses_pt}; nova_linha['MESES'] = item
            df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
    return df_pivot

def save_to_supabase(table_name, df, ano_escolhido):
    df_melted = df.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
    df_melted['ano'] = ano_escolhido
    df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
    data = df_melted.to_dict(orient='records')
    supabase.table(table_name).upsert(data).execute()

# ==========================================
# 5. MENU LATERAL E INICIALIZAÇÃO
# ==========================================
with st.sidebar:
    st.title("📈 Consorbens Wealth")
    ano_selecionado = st.selectbox("Selecione o Ano", options=[2025, 2026, 2027, 2028], index=1)
    
    if st.button("🔄 Atualizar e Limpar Memória"):
        st.session_state.clear()
        st.rerun()

contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_p' not in st.session_state:
    st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
if 'df_e' not in st.session_state:
    st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)

# ==========================================
# 6. CONFIGURAÇÃO DAS COLUNAS DAS TABELAS
# ==========================================
col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=210, disabled=True)}
for m in meses_pt: 
    # Essa configuração permite digitar "1000" e ele mostra "R$ 1,000.00" na hora de editar
    col_cfg[m] = st.column_config.NumberColumn(m, width=72, format="R$ % ,.2f", step=0.01)

# ==========================================
# 7. RENDERIZAÇÃO DO DASHBOARD
# ==========================================
st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)

# --- TABELA 1: PATRIMÔNIO (EDITÁVEL COM AUTO-SAVE) ---
df_p_editado = st.data_editor(st.session_state.df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=290)

# Inteligência do Auto-Save:
if not df_p_editado.equals(st.session_state.df_p):
    st.session_state.df_p = df_p_editado
    save_to_supabase('patrimonio', df_p_editado, ano_selecionado)
    st.toast("✅ Patrimônio atualizado no banco de dados!", icon="💾")
    st.rerun()

# --- CÁLCULOS DO PATRIMÔNIO ---
df_n = st.session_state.df_p.set_index('MESES')
patr_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
patr_total = patr_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
var_abs = patr_total.diff().fillna(0)
var_pct = (patr_total.pct_change().fillna(0) * 100).round(2)

df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
for m in meses_pt: df_res_p[m] = [patr_liq[m], patr_total[m], var_abs[m], f"{var_pct[m]:.2f}%"]

# --- TABELA 2: RESULTADOS DO PATRIMÔNIO ---
st.dataframe(df_res_p.style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; color: black; border-bottom: 1px solid #ddd;'] * len(row), axis=1)
             .format(lambda x: formata_br(x) if isinstance(x, (int, float, np.float64)) else x),
             hide_index=True, column_config=col_cfg, use_container_width=True, height=155)


# --- TABELA 3: ENTRADAS (EDITÁVEL COM AUTO-SAVE) ---
df_e_editado = st.data_editor(st.session_state.df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=185)

# Inteligência do Auto-Save:
if not df_e_editado.equals(st.session_state.df_e):
    st.session_state.df_e = df_e_editado
    save_to_supabase('entradas', df_e_editado, ano_selecionado)
    st.toast("✅ Entradas atualizadas no banco de dados!", icon="💾")
    st.rerun()

# --- CÁLCULOS DAS ENTRADAS ---
salario_total = st.session_state.df_e.set_index('MESES').sum()
df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
for m in meses_pt: df_res_e[m] = [salario_total[m]]

# --- TABELA 4: RESULTADO DAS ENTRADAS ---
st.dataframe(df_res_e.style.apply(lambda x: ['background-color: #9BC2E6; font-weight: bold; color: black;'] * len(x), axis=1)
             .format(lambda x: formata_br(x) if isinstance(x, (int, float, np.float64)) else x), 
             hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

st.markdown('</div>', unsafe_allow_html=True)


# ==========================================
# 8. INDICADORES DE RESUMO (MÉTRICAS)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("#### 📊 Resumo de Performance Anual")
m1, m2, m3, m4 = st.columns(4)

# Lógica para pegar o mês atual ou o último preenchido
idx_ref = mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0

m1.metric("MÉDIA DE RECEBIMENTOS", formata_br(salario_total.mean()))
m2.metric("PATRIMÔNIO ATUAL", formata_br(patr_total.iloc[idx_ref]))
m3.metric("CRESCIMENTO ABSOLUTO ($)", formata_br(patr_total.iloc[idx_ref] - patr_total.iloc[0]))
m4.metric("CRESCIMENTO NO ANO (%)", f"{((patr_total.iloc[idx_ref] / patr_total.iloc[0] - 1)*100 if patr_total.iloc[0] != 0 else 0):,.2f}%")
