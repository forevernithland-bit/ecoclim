import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS: COLAGEM EXTREMA E SOBREPOSIÇÃO ---
st.markdown("""
    <style>
    /* Desce o topo para os meses não sumirem */
    .block-container { padding-top: 4rem !important; }
    
    /* Remove todos os espaços nativos entre as tabelas */
    div.st-emotion-cache-1wivap2 { gap: 0rem !important; }
    div[data-testid="stVerticalBlock"] > div { padding: 0px !important; margin: 0px !important; }
    
    /* Centraliza o texto */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
    }
    
    /* 
       COLAGEM EXTREMA (-43px):
       Esse valor foi ajustado para engolir todo o cabeçalho e colar as bordas!
    */
    
    /* Tabela 1: Patrimônio Editável (Topo) */
    div[data-testid="stDataEditor"]:nth-of-type(1) {
        z-index: 10 !important;
        position: relative !important;
    }
    
    /* Tabela 2: Resultados Patrimônio (Cola na T1) */
    div[data-testid="stDataFrame"]:nth-of-type(1) {
        z-index: 9 !important;
        position: relative !important;
        margin-top: -43px !important; 
        margin-bottom: 40px !important; /* Espaço antes das Entradas */
    }
    
    /* Tabela 3: Entradas Editáveis (Cabeçalho oculto sob si mesma, mas com margem ajustada) */
    div[data-testid="stDataEditor"]:nth-of-type(2) {
        z-index: 8 !important;
        position: relative !important;
    }
    
    /* Tabela 4: Resultados Entradas (Cola na T3) */
    div[data-testid="stDataFrame"]:nth-of-type(2) {
        z-index: 7 !important;
        position: relative !important;
        margin-top: -43px !important;
    }

    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- JAVASCRIPT: SCROLL SINCRONIZADO ---
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
meses_view = meses_base[1:]

linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

if 'df_patrimonio' not in st.session_state or 'MESES' not in st.session_state.df_patrimonio.columns:
    df_p = pd.DataFrame(0.0, index=range(len(linhas_patrimonio)), columns=meses_base)
    df_p.insert(0, 'MESES', linhas_patrimonio)
    st.session_state.df_patrimonio = df_p

if 'df_entradas' not in st.session_state or 'MESES' not in st.session_state.df_entradas.columns:
    df_e = pd.DataFrame(0.0, index=range(len(linhas_entradas)), columns=meses_base)
    df_e.insert(0, 'MESES', linhas_entradas)
    st.session_state.df_entradas = df_e

# TRAVA UNIVERSAL DE COLUNAS
col_config_top = {"MESES": st.column_config.TextColumn("MESES", width=250, disabled=True)}
col_config_bot = {"MESES": st.column_config.TextColumn(" ", width=250, disabled=True)} # Título invisível para não conflitar com a sobreposição

for mes in meses_view:
    col_config_top[mes] = st.column_config.NumberColumn(mes, width=100)
    col_config_bot[mes] = st.column_config.NumberColumn(" ", width=100)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # ------------------------------------------------------------------
    # TABELA 1: PATRIMÔNIO (Mostra Meses)
    # ------------------------------------------------------------------
    df_view_patr = st.session_state.df_patrimonio[['MESES'] + meses_view]
    df_editado_view_patr = st.data_editor(df_view_patr, hide_index=True, column_config=col_config_top, use_container_width=True, height=282)
    
    for mes in meses_view:
        st.session_state.df_patrimonio[mes] = df_editado_view_patr[mes]
    
    df_num_patr = st.session_state.df_patrimonio.set_index('MESES')
    patrimonio_liquido = df_num_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_num_patr.loc['IMÓVEIS'] + df_num_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    df_resultados_patr = pd.DataFrame({'MESES': ['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio', '% var patrimônio']})
    for mes in meses_view:
        df_resultados_patr[mes] = [patrimonio_liquido[mes], patrimonio_total[mes], var_rs[mes], var_pct[mes]]

    def style_patrimonio(row):
        if row['MESES'] == 'PATRIMONIO LÍQUIDO':
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row['MESES'] == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        else:
            return ['background-color: #FFF2CC; color: black; border: 1px solid #e0e0e0;'] * len(row)

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view}, subset=pd.IndexSlice[[0, 1, 2], meses_view])\
        .format(formatter={col: '{:.2f}%' for col in meses_view}, subset=pd.IndexSlice[[3], meses_view])

    # ------------------------------------------------------------------
    # TABELA 2: RESULTADOS PATRIMÔNIO (Cabeçalho engolido pela T1)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, hide_index=True, column_config=col_config_bot, use_container_width=True, height=183)

    # ------------------------------------------------------------------
    # TABELA 3: ENTRADAS EDITÁVEL (Desce um pouco e exibe seus próprios meses se quiser, ou usa o CSS top)
    # Aqui vamos usar o col_config_top para ela ter seu próprio cabeçalho "MESES"
    # ------------------------------------------------------------------
    df_view_ent = st.session_state.df_entradas[['MESES'] + meses_view]
    df_editado_view_ent = st.data_editor(df_view_ent, hide_index=True, column_config=col_config_top, use_container_width=True, height=177)
    
    for mes in meses_view:
        st.session_state.df_entradas[mes] = df_editado_view_ent[mes]
    
    df_num_ent = st.session_state.df_entradas.set_index('MESES')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'MESES': ['SALÁRIO MÊS:']})
    for mes in meses_view:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border: 1px solid black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view})
        
    # ------------------------------------------------------------------
    # TABELA 4: RESULTADO ENTRADAS (Cabeçalho engolido pela T3)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, hide_index=True, column_config=col_config_bot, use_container_width=True, height=78)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
