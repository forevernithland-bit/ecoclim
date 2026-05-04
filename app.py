import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- 1. CSS PARA SOBREPOSIÇÃO (Esconde cabeçalhos perfeitamente) ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    div.st-emotion-cache-1wivap2 { gap: 0rem !important; }
    
    /* Centraliza os textos */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
    }
    
    /* 
       MÁGICA DA SOBREPOSIÇÃO:
       Cada tabela desliza para baixo da tabela anterior para esconder os meses.
       Z-index maior = Fica por cima.
    */
    /* 1. Tabela Patrimônio Editável (Topo) */
    div[data-testid="stDataEditor"]:nth-of-type(1) { z-index: 10; position: relative; }
    
    /* 2. Tabela Patrimônio Resultado (Esconde cabeçalho debaixo da tabela 1) */
    div[data-testid="stDataFrame"]:nth-of-type(1) { z-index: 9; position: relative; margin-top: -36px !important; margin-bottom: 30px !important; }
    
    /* 3. Tabela Entradas Editável (Esconde cabeçalho debaixo da tabela 2) */
    div[data-testid="stDataEditor"]:nth-of-type(2) { z-index: 8; position: relative; }
    
    /* 4. Tabela Entradas Resultado (Esconde cabeçalho debaixo da tabela 3) */
    div[data-testid="stDataFrame"]:nth-of-type(2) { z-index: 7; position: relative; margin-top: -36px !important; }
    
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. JAVASCRIPT PARA SINCRONIZAR O SCROLL HORIZONTAL ---
components.html("""
    <script>
    const doc = window.parent.document;
    let isSyncing = false;

    function attachScrollSync() {
        // Encontra as barras de rolagem das tabelas do Streamlit
        const scrollers = doc.querySelectorAll('.dvn-scroller');
        if (scrollers.length > 1) {
            scrollers.forEach(scroller => {
                scroller.addEventListener('scroll', (e) => {
                    if (!isSyncing) {
                        isSyncing = true;
                        // Aplica a rolagem atual em todas as outras tabelas
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

    // Tenta aplicar a sincronização até as tabelas carregarem na tela
    const interval = setInterval(() => {
        if (attachScrollSync()) {
            clearInterval(interval);
        }
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

# --- LÓGICA DE MESES ---
meses_base = ['dez/25', 'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
meses_view = meses_base[1:] # Tira o dez/25 da visão do usuário, deixando só de Janeiro a Dezembro

linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

# Inicializando Banco de Memória
if 'df_patrimonio' not in st.session_state or 'CONTAS' not in st.session_state.df_patrimonio.columns:
    df_p = pd.DataFrame(0.0, index=range(len(linhas_patrimonio)), columns=meses_base)
    df_p.insert(0, 'CONTAS', linhas_patrimonio)
    st.session_state.df_patrimonio = df_p

if 'df_entradas' not in st.session_state or 'CONTAS' not in st.session_state.df_entradas.columns:
    df_e = pd.DataFrame(0.0, index=range(len(linhas_entradas)), columns=meses_base)
    df_e.insert(0, 'CONTAS', linhas_entradas)
    st.session_state.df_entradas = df_e

# Travando largura idêntica para as colunas
col_config = {"CONTAS": st.column_config.TextColumn("CONTAS", width=250, disabled=True)}
for mes in meses_view:
    col_config[mes] = st.column_config.NumberColumn(mes, width=100)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # ------------------------------------------------------------------
    # BLOCO 1: PATRIMÔNIO (Mostra meses_view, oculta dez/25)
    # ------------------------------------------------------------------
    df_view_patr = st.session_state.df_patrimonio[['CONTAS'] + meses_view]
    df_editado_view_patr = st.data_editor(df_view_patr, hide_index=True, column_config=col_config, use_container_width=True, height=283)
    
    # Salva edições na memória (mantendo dez/25 intacto lá no fundo)
    for mes in meses_view:
        st.session_state.df_patrimonio[mes] = df_editado_view_patr[mes]
    
    # Cálculos usando toda a base (incluindo dez/25 para gerar JANEIRO)
    df_num_patr = st.session_state.df_patrimonio.set_index('CONTAS')
    patrimonio_liquido = df_num_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_num_patr.loc['IMÓVEIS'] + df_num_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    # Cria tabela de resultados APENAS com os meses visíveis
    df_resultados_patr = pd.DataFrame({'CONTAS': ['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio', '% var patrimônio']})
    for mes in meses_view:
        df_resultados_patr[mes] = [patrimonio_liquido[mes], patrimonio_total[mes], var_rs[mes], var_pct[mes]]

    def style_patrimonio(row):
        if row['CONTAS'] == 'PATRIMONIO LÍQUIDO':
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row['CONTAS'] == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row['CONTAS'] == 'Var $ patrimonio':
            return ['background-color: #FFF2CC; color: black;'] * len(row)
        else:
            return ['background-color: #FFFFFF; color: black;'] * len(row)

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view}, subset=pd.IndexSlice[[0, 1, 2], meses_view])\
        .format(formatter={col: '{:.2f}%' for col in meses_view}, subset=pd.IndexSlice[[3], meses_view])

    # Tabela Resultados Patrimônio (Esconde cabeçalho debaixo da tabela de cima)
    st.dataframe(styled_df_patr, hide_index=True, column_config=col_config, use_container_width=True, height=176)

    # ------------------------------------------------------------------
    # BLOCO 2: ENTRADAS
    # ------------------------------------------------------------------
    df_view_ent = st.session_state.df_entradas[['CONTAS'] + meses_view]
    df_editado_view_ent = st.data_editor(df_view_ent, hide_index=True, column_config=col_config, use_container_width=True, height=176)
    
    for mes in meses_view:
        st.session_state.df_entradas[mes] = df_editado_view_ent[mes]
    
    df_num_ent = st.session_state.df_entradas.set_index('CONTAS')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'CONTAS': ['SALÁRIO MÊS:']})
    for mes in meses_view:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border: 1px solid black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses_view})
        
    # Tabela Resultado Entradas
    st.dataframe(styled_df_ent, hide_index=True, column_config=col_config, use_container_width=True, height=75)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
