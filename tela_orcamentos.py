import streamlit as st
import pandas as pd
import utils
import math

# Importando nossos novos módulos de abas
import orcamento_personalizado
import orcamento_lote
import orcamento_rapido

@st.dialog("💡 Calculadoras de Dimensionamento e Lembretes")
def abrir_lembretes():
    t_banho, t_tubo, t_col = st.tabs(["🚿 Banhos por Litro", "🧪 Tubos (Vácuo)", "☀️ Coletores (Planos)"])
    
    with t_banho:
        st.caption("Calcule quantos banhos o boiler suporta.")
        c1, c2 = st.columns(2)
        v_b = c1.number_input("Volume do Boiler (Litros)", min_value=0, step=10, key="calc_vol_banho")
        l_b = c2.number_input("Litros por Banho", min_value=1, value=45, step=1, key="calc_litro_banho")
        if v_b > 0:
            qtd_banhos = int(v_b / l_b)
            st.success(f"**Resultado:** {qtd_banhos} Banhos\n\n*(1 banho está configurado para {l_b} litros)*")
            
    with t_tubo:
        st.caption("Calcule a quantidade de tubos a vácuo necessários.")
        v_t = st.number_input("Volume do Boiler (Litros)", min_value=0, step=10, key="calc_vol_tubo")
        if v_t > 0:
            c1, c2 = st.columns(2)
            c1.info(f"**BOM (20L por tubo):**\n### {math.ceil(v_t / 20)} tubos")
            c2.success(f"**ÓTIMO (15L por tubo):**\n### {math.ceil(v_t / 15)} tubos")
            
    with t_col:
        st.caption("Calcule a quantidade de coletores (1 placa para cada 200L).")
        v_c = st.number_input("Volume do Boiler (Litros)", min_value=0, step=10, key="calc_vol_col")
        if v_c > 0:
            exato = v_c / 200
            arredondado = math.ceil(exato)
            if arredondado > exato:
                st.success(f"**Resultado:** ### {arredondado} coletores\n\n⚠️ *O sistema colocou 1 coletor a mais para o sistema ficar mais eficiente.*")
            else:
                st.success(f"**Resultado:** ### {arredondado} coletores\n\n✅ *Cálculo exato de 1 coletor para cada 200L.*")

def limpar_tela_orcamento():
    chaves = [
        'rascunho_id', 'input_nome_cliente', 'input_whatsapp', 
        'txt_servico', 'val_servico', 'txt_outros', 'val_outros', 
        'input_obs_pdf', 'df_orc', 'df_orc_prev', 'editor_orc_base', 
        'pdf_gerado', 'nome_cliente_previa', 'servico_selecionado_anterior', 
        'outros_selecionado_anterior',
        'rapido_rascunho_id', 'rapido_input_nome_cliente', 'rapido_df_orc', 'editor_rapido',
        'rapido_custo_servico', 'rapido_venda_servico', 'rapido_custo_outros', 'rapido_venda_outros',
        'rapido_nf', 'rapido_taxa_cartao', 'rapido_comissao'
    ]
    for k in chaves:
        if k in st.session_state: 
            del st.session_state[k]

def renderizar():
    deve_rerun = False
    
    # -------------------------------------------------------------------------
    # TRANSFERÊNCIA SEGURA DO ORÇAMENTO RÁPIDO PARA O PERSONALIZADO
    # -------------------------------------------------------------------------
    if st.session_state.get('transferir_agora'):
        novo_df = []
        df_r = st.session_state.get('rapido_df_orc', pd.DataFrame())
        cat_p = utils.load_catalog('catalogo_produtos')
        
        if not df_r.empty:
            for _, r in df_r.iterrows():
                p_nome = str(r.get("Produto da Base", "")).strip()
                p_manual = str(r.get("Produto Manual", "")).strip()
                q = float(r.get("Quantidade", 0))
                c = float(r.get("Custo (R$)", 0.0))
                v = float(r.get("Venda (R$)", 0.0))
                
                desc = ""
                if p_nome and p_nome != "OUTRO" and not cat_p.empty:
                    match = cat_p[cat_p['Item'].astype(str).str.strip().str.upper() == p_nome.upper()]
                    if not match.empty:
                        desc = str(match.iloc[0].get('Descrição', ''))
                        if desc.lower() == 'nan': desc = ""
                        
                novo_df.append({
                    "Produto da Base": p_nome,
                    "Produto Manual": p_manual,
                    "Descrição": desc,
                    "Quantidade": q,
                    "Custo (R$)": c,
                    "Venda (R$)": v,
                    "Custo Total": q * c,
                    "Venda Total": q * v
                })
        
        while len(novo_df) < 5:
            novo_df.append({"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0})
        
        st.session_state.df_orc = pd.DataFrame(novo_df)
        st.session_state.df_orc_prev = st.session_state.df_orc.copy()
        
        st.session_state.input_nome_cliente = st.session_state.get("rapido_input_nome_cliente", "")
        st.session_state.val_servico = st.session_state.get("rapido_venda_servico", 0.0)
        st.session_state.val_outros = st.session_state.get("rapido_venda_outros", 0.0)
        
        if "editor_orc_base" in st.session_state:
            del st.session_state["editor_orc_base"]
            
        st.session_state.transferir_agora = False
        st.session_state.show_transfer_success = True

    # -------------------------------------------------------------------------
    # BLINDAGEM DE ESTADO INICIAL
    # -------------------------------------------------------------------------
    if "input_nome_cliente" not in st.session_state: st.session_state.input_nome_cliente = ""
    if "input_whatsapp" not in st.session_state: st.session_state.input_whatsapp = ""
    if "txt_servico" not in st.session_state: st.session_state.txt_servico = ""
    if "val_servico" not in st.session_state: st.session_state.val_servico = 0.0
    if "txt_outros" not in st.session_state: st.session_state.txt_outros = ""
    if "val_outros" not in st.session_state: st.session_state.val_outros = 0.0
    if "servico_selecionado_anterior" not in st.session_state: st.session_state.servico_selecionado_anterior = ""
    if "outros_selecionado_anterior" not in st.session_state: st.session_state.outros_selecionado_anterior = ""
    
    if "rapido_input_nome_cliente" not in st.session_state: st.session_state.rapido_input_nome_cliente = ""
    if "rapido_custo_servico" not in st.session_state: st.session_state.rapido_custo_servico = 0.0
    if "rapido_venda_servico" not in st.session_state: st.session_state.rapido_venda_servico = 0.0
    if "rapido_custo_outros" not in st.session_state: st.session_state.rapido_custo_outros = 0.0
    if "rapido_venda_outros" not in st.session_state: st.session_state.rapido_venda_outros = 0.0
    if "rapido_nf" not in st.session_state: st.session_state.rapido_nf = "Não"
    if "rapido_taxa_cartao" not in st.session_state: st.session_state.rapido_taxa_cartao = "Nenhum / Dinheiro / PIX"
    if "rapido_comissao" not in st.session_state: st.session_state.rapido_comissao = 0.0

    # =============================================================================
    # TÍTULO E BOTÕES LATERAIS DIREITOS
    # =============================================================================
    col_tit, col_btn = st.columns([2, 1])
    
    with col_tit:
        st.markdown("<h4 style='color:#004488; margin:0; font-weight:600;'>📝 Gestão de Orçamentos</h4>", unsafe_allow_html=True)
        
    with col_btn:
        if st.button("🔄 ATUALIZAR DADOS DO BANCO / LIMPAR", use_container_width=True):
            limpar_tela_orcamento()
            for chave in ['db_produtos', 'db_servicos', 'db_outros', 'db_taxas', 'pdf_gerados_lote']:
                if chave in st.session_state: 
                    del st.session_state[chave]
            st.rerun()
            
        if st.button("💡 Lembretes e Cálculos Rápidos", use_container_width=True):
            abrir_lembretes()

    if 'db_produtos' not in st.session_state: st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
    if 'db_servicos' not in st.session_state: st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
    if 'db_outros' not in st.session_state: st.session_state.db_outros = utils.load_catalog('catalogo_outros')
    if 'db_taxas' not in st.session_state: st.session_state.db_taxas = utils.load_taxas()

    cat_produtos = st.session_state.db_produtos
    lista_nomes_produtos = cat_produtos['Item'].dropna().tolist() if not cat_produtos.empty else []
    
    aba_personalizado, aba_lote, aba_rapido = st.tabs(["📝 Orçamento Personalizado", "📦 Gerador em Lote (Tabelas)", "⚡ Orçamento Rápido"])

    # Roteador chamando as abas separadas em arquivos
    with aba_personalizado:
        if orcamento_personalizado.renderizar(lista_nomes_produtos, limpar_tela_orcamento):
            deve_rerun = True

    with aba_lote:
        if orcamento_lote.renderizar():
            deve_rerun = True

    with aba_rapido:
        if orcamento_rapido.renderizar(lista_nomes_produtos, limpar_tela_orcamento):
            deve_rerun = True

    if deve_rerun:
        st.rerun()
