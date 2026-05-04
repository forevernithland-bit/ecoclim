import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS ESTRITO: SOBREPOSIÇÃO PERFEITA E ALINHAMENTO ---
st.markdown("""
    <style>
    /* Empurra o layout um pouco para baixo para não cortar o título */
    .block-container { padding-top: 2rem !important; }
    
    /* Zera os espaços originais do Streamlit entre os blocos */
    div[data-testid="stVerticalBlock"] { gap: 0rem !important; }
    
    /* Centraliza o texto nas células da tabela */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
    }
    
    /* Fundos brancos sólidos obrigatórios para esconder os elementos debaixo */
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] {
        background-color: white !important;
    }

    /* 
       O EFEITO CASCATA:
       As tabelas deslizam -38px (altura exata do cabeçalho) para debaixo da tabela superior.
       Isso esconde os meses perfeitamente e une as planilhas!
    */
    
    /* 1. Tabela Editável Patrimônio (Fica no topo, mostra os meses) */
    div[data-testid="stDataEditor"]:nth-of-type(1) {
        z-index: 4 !important;
        position: relative !important;
    }
    
    /* 2. Resultados Patrimônio (Desliza sob a Tabela 1, escondendo o cabeçalho) */
    div[data-testid="stDataFrame"]:nth-of-type(1) {
        z-index: 3 !important;
        position: relative !important;
        margin-top: -38px !important; 
    }
    
    /* 3. Tabela Editável Entradas (Desliza sob a Tabela 2, escondendo o cabeçalho) */
    div[data-testid="stDataEditor"]:nth-of-type(2) {
        z-index: 2 !important;
        position: relative !important;
        margin-top: -38px !important;
    }
    
    /* 4. Resultados Entradas (Desliza sob a Tabela 3, escondendo o cabeçalho) */
    div[data-testid="stDataFrame"]:nth-of-type(2) {
        z-index: 1 !important;
        position: relative !important;
        margin-top: -38px !important;
    }

    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- JAVASCRIPT: SCROLL SINCRONIZADO DE ALTA PERFORMANCE ---
components.html("""
    <script>
    const doc = window.parent.document;
    let isSyncing = false;

    function attachScrollSync() {
        const scrollers = doc.querySelectorAll('.dvn-scroller');
        if (scrollers.length > 1) {
            scrollers.forEach(scroller => {
                scroller.addEventListener('scroll', (e) => {
                    if (!isSyncing) {
                        isSyncing = true;
                        scrollers.forEach(other => {
                            if (other !== scroller) {
                                other.scrollLeft = scroller.scrollLeft;
                            }
                        });
                        window.requestAnimationFrame(() => { isSyncing = false; });
                    }
                });
            });
            return true;
        }
        return false;
    }

    const interval = setInterval(() => {
        if (attachScrollSync()) { clearInterval(interval); }
    }, 500);
    </script>
""", height=0, width=0)

# --- MENU LATERAL ---
with st.sidebar:
    st.title("📈 Consorbens")
    menu = st.radio("Navegação", ["🏠 Dashboard Consolidado", "❄️ Ecoclim", "🏠 Airbnb", "📄 Documentos"])
    st.write("---")
    if st.button("🔄 Limpar Memória do App"):
        st.session_state.clear()
        st.rerun()

# --- CONFIGURAÇÃO DE DADOS ---
meses_base = ['dez/25', 'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
meses_view = meses_base[1:] # Tira o dez/25 da visão, mas o código ainda o usa para cálculos!

linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

# Memória Inicial
if 'df_patrimonio' not in st.session_state or 'CONTAS' not in st.session_state.df_patrimonio.columns:
    df_p = pd.DataFrame(0.0, index=range(len(linhas_patrimonio)), columns=meses_base)
    df_p.insert(0, 'CONTAS', linhas_patrimonio)
    st.session_state.df_patrimonio = df_p

if 'df_entradas' not in st.session_state or 'CONTAS' not in st.session_state.df_entradas.columns:
    df_e = pd.DataFrame(0.0, index=range(len(linhas_entradas)), columns=meses_base)
    df_e.insert(0, 'CONTAS', linhas_entradas)
    st.session_state.df_entradas = df_e

# ====================================================================
# TRAVA UNIVERSAL DE LARGURA DE COLUNAS (Garante o Alinhamento)
# ====================================================================
col_config_master = {
    "CONTAS": st.column_config.TextColumn("MESES", width=250, disabled=True)
}
for mes in meses_view:
    col_config_master[mes] = st.column_config.NumberColumn(mes, width=100)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # ------------------------------------------------------------------
    # TABELA 1: PATRIMÔNIO EDITÁVEL (A única que o cabeçalho fica visível)
    # ------------------------------------------------------------------
    df_view_patr = st.session_state.df_patrimonio[['CONTAS'] + meses_view]
    df_editado_view_patr = st.data_editor(df_view_patr, hide_index=True, column_config=col_config_master, use_container_width=True, height=283)
    
    # Salva edições na memória
    for mes in meses_view:
        st.session_state.df_patrimonio[mes] = df_editado_view_patr[mes]
    
    # Cálculos
    df_num_patr = st.session_state.df_patrimonio.set_index('CONTAS')
    patrimonio_liquido = df_num_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_num_patr.loc['IMÓVEIS'] + df_num_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    df_resultados_patr = pd.DataFrame({'CONTAS': ['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio', '% var patrimônio']})
    for mes in meses_view:
        df_resultados_patr[mes] = [patrimonio_liquido[mes], patrimonio_total[mes], var_rs[mes], var_pct[mes]]

    # Cores
    def style_patrimonio(row):
        if row['CONTAS'] == 'PATRIMONIO LÍQUIDO':
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row['CONTAS'] == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        else:
            return ['background-color: #FFF2CC; color: black; border: 1px solid #ccc;'] * len(row)

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view}, subset=pd.IndexSlice[[0, 1, 2], meses_view])\
        .format(formatter={col: '{:.2f}%' for col in meses_view}, subset=pd.IndexSlice[[3], meses_view])

    # ------------------------------------------------------------------
    # TABELA 2: RESULTADOS PATRIMÔNIO (Desliza e esconde o cabeçalho)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, hide_index=True, column_config=col_config_master, use_container_width=True, height=177)

    # ------------------------------------------------------------------
    # TABELA 3: ENTRADAS EDITÁVEL (Desliza e esconde o cabeçalho)
    # ------------------------------------------------------------------
    df_view_ent = st.session_state.df_entradas[['CONTAS'] + meses_view]
    df_editado_view_ent = st.data_editor(df_view_ent, hide_index=True, column_config=col_config_master, use_container_width=True, height=177)
    
    # Salva edições na memória
    for mes in meses_view:
        st.session_state.df_entradas[mes] = df_editado_view_ent[mes]
    
    # Cálculos
    df_num_ent = st.session_state.df_entradas.set_index('CONTAS')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'CONTAS': ['SALÁRIO MÊS:']})
    for mes in meses_view:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    # Cores
    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border: 1px solid black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view})
        
    # ------------------------------------------------------------------
    # TABELA 4: RESULTADO ENTRADAS (Desliza e esconde o cabeçalho)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, hide_index=True, column_config=col_config_master, use_container_width=True, height=75)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
