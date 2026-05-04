import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS CIRÚRGICO: ALINHAMENTO SEM QUEBRAR DADOS ---
st.markdown("""
    <style>
    /* Dá um respiro no topo para os meses aparecerem bem */
    .block-container { padding-top: 3rem !important; }
    
    /* Remove todos os buracos em branco entre os elementos da página principal */
    section.main div.st-emotion-cache-1wivap2 { gap: 0rem !important; }
    section.main div[data-testid="stVerticalBlock"] { gap: 0px !important; }
    
    /* Centraliza os textos */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
    }
    
    /* Fundos brancos sólidos para a sobreposição funcionar */
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] {
        background-color: white !important;
    }

    /* 
       A MÁGICA SEGURA: 
       Usa a altura exata do cabeçalho (-39px) para esconder APENAS o cabeçalho, 
       sem comer a primeira linha de dados!
    */
    
    /* 1. Patrimônio Editável (Fica no topo, MOSTRA os meses) */
    section.main div[data-testid="stDataEditor"]:nth-of-type(1) { 
        z-index: 10 !important; position: relative !important; 
    }
    
    /* 2. Patrimônio Resultado (ESCONDE cabeçalho debaixo da tabela 1) */
    section.main div[data-testid="stDataFrame"]:nth-of-type(1) { 
        z-index: 9 !important; position: relative !important; 
        margin-top: -39px !important; 
    }
    
    /* 3. Entradas Editável (ESCONDE cabeçalho debaixo da tabela 2) */
    section.main div[data-testid="stDataEditor"]:nth-of-type(2) { 
        z-index: 8 !important; position: relative !important; 
        margin-top: -39px !important; 
    }
    
    /* 4. Entradas Resultado (ESCONDE cabeçalho debaixo da tabela 3) */
    section.main div[data-testid="stDataFrame"]:nth-of-type(2) { 
        z-index: 7 !important; position: relative !important; 
        margin-top: -39px !important; 
    }

    /* Tira o arredondamento para parecer uma planilha só */
    section.main div[data-testid="stDataEditor"] > div > div { border-radius: 0px !important; }
    section.main div[data-testid="stDataFrame"] > div > div { border-radius: 0px !important; border-top: none !important; }

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
meses_view = meses_base[1:] # Tira dez/25 da visão

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
# Configuração para a Tabela 1 (Exibe os nomes)
col_config_top = {"MESES": st.column_config.TextColumn("MESES", width=250, disabled=True)}
for mes in meses_view:
    col_config_top[mes] = st.column_config.NumberColumn(mes, width=100)

# Configuração para Tabelas 2, 3 e 4 (Títulos invisíveis para esconder melhor)
col_config_bot = {"MESES": st.column_config.TextColumn(" ", width=250, disabled=True)}
for mes in meses_view:
    col_config_bot[mes] = st.column_config.NumberColumn(" ", width=100)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # ------------------------------------------------------------------
    # TABELA 1: PATRIMÔNIO (Mostra Meses no topo)
    # ------------------------------------------------------------------
    df_view_patr = st.session_state.df_patrimonio[['MESES'] + meses_view]
    df_editado_view_patr = st.data_editor(df_view_patr, hide_index=True, column_config=col_config_top, use_container_width=True, height=285)
    
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
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border-bottom: 1px solid #ccc;'] * len(row)
        elif row['MESES'] == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border-bottom: 1px solid #ccc;'] * len(row)
        else:
            return ['background-color: #FFF2CC; color: black; border-bottom: 1px solid #ccc;'] * len(row)

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view}, subset=pd.IndexSlice[[0, 1, 2], meses_view])\
        .format(formatter={col: '{:.2f}%' for col in meses_view}, subset=pd.IndexSlice[[3], meses_view])

    # ------------------------------------------------------------------
    # TABELA 2: RESULTADOS PATRIMÔNIO (Cabeçalho oculto)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, hide_index=True, column_config=col_config_bot, use_container_width=True, height=180)

    # ------------------------------------------------------------------
    # TABELA 3: ENTRADAS EDITÁVEL (Cabeçalho oculto)
    # ------------------------------------------------------------------
    df_view_ent = st.session_state.df_entradas[['MESES'] + meses_view]
    df_editado_view_ent = st.data_editor(df_view_ent, hide_index=True, column_config=col_config_bot, use_container_width=True, height=180)
    
    for mes in meses_view:
        st.session_state.df_entradas[mes] = df_editado_view_ent[mes]
    
    df_num_ent = st.session_state.df_entradas.set_index('MESES')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'MESES': ['SALÁRIO MÊS:']})
    for mes in meses_view:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view})
        
    # ------------------------------------------------------------------
    # TABELA 4: RESULTADO ENTRADAS (Cabeçalho oculto)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, hide_index=True, column_config=col_config_bot, use_container_width=True, height=75)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
