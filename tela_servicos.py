import streamlit as st
import pandas as pd
import utils
from datetime import datetime

def renderizar():
    # Título para confirmar que o código novo carregou
    st.markdown("## 🛠️ Gestão de Serviços e Orçamentos")
    
    supabase = st.session_state.supabase
    
    # 1. Carregar Dados
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df_raw = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar dados do banco: {e}")
        return

    if df_raw.empty:
        st.info("Nenhum registro encontrado no banco de dados.")
        return

    # --- Lógica de Filtro de Cancelados (50 dias) ---
    def filtrar_cancelados(row):
        if row['status_projeto'] == 'Cancelado':
            if row['data_orcamento']:
                data_orc = pd.to_datetime(row['data_orcamento']).date()
                if (datetime.now().date() - data_orc).days > 50:
                    return False
        return True

    df_raw = df_raw[df_raw.apply(filtrar_cancelados, axis=1)]

    # --- SEPARAÇÃO DOS GRUPOS (Status exatos) ---
    status_ativos = ['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO']
    status_orcamentos = ['Orçamento Enviado', 'Em Negociação', 'Cancelado']

    df_ativos = df_raw[df_raw['status_projeto'].isin(status_ativos)].copy()
    df_orcamentos = df_raw[df_raw['status_projeto'].isin(status_orcamentos)].copy()
    
    # Captura quem não se encaixou (Segurança)
    df_outros = df_raw[~df_raw['status_projeto'].isin(status_ativos + status_orcamentos)].copy()

    colunas_rapidas = [
        'nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 
        'valor_custo_equipamentos', 'lucro_estimado', 
        'instalador_responsavel', 'valor_pago_instalador'
    ]
    
    col_cfg = {
        "nome_cliente": st.column_config.TextColumn("Cliente", width="medium"),
        "produtos_adquiridos": st.column_config.TextColumn("Produto", width="medium"),
        "valor_venda_total": st.column_config.NumberColumn("Venda", format="R$ %,.2f"),
        "valor_custo_equipamentos": st.column_config.NumberColumn("Custo", format="R$ %,.2f"),
        "lucro_estimado": st.column_config.NumberColumn("Lucro Est.", format="R$ %,.2f"),
        "instalador_responsavel": st.column_config.TextColumn("Instalador"),
        "valor_pago_instalador": st.column_config.NumberColumn("Valor Inst.", format="R$ %,.2f"),
    }

    # =========================================================================
    # PARTE DE CIMA: SERVIÇOS ATIVOS / FECHADOS
    # =========================================================================
    st.subheader("✅ Serviços em Andamento / Concluídos")
    if not df_ativos.empty:
        # Correção aqui: selection_mode="single-row"
        sel_ativo = st.dataframe(df_ativos[colunas_rapidas], column_config=col_cfg, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if sel_ativo.selection.rows:
            exibir_detalhes(df_ativos.iloc[sel_ativo.selection.rows[0]], supabase)
    else:
        st.write("_Nenhum serviço ativo._")

    # =========================================================================
    # PARTE DE BAIXO: ORÇAMENTOS
    # =========================================================================
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.subheader("📝 Orçamentos e Negociações")
    if not df_orcamentos.empty:
        # Correção aqui: selection_mode="single-row"
        sel_orc = st.dataframe(df_orcamentos[colunas_rapidas], column_config=col_cfg, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if sel_orc.selection.rows:
            exibir_detalhes(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)
    else:
        st.write("_Nenhum orçamento pendente._")

    # =========================================================================
    # GAVETA DE SEGURANÇA: CASO O STATUS ESTEJA COM NOME DIFERENTE NO BANCO
    # =========================================================================
    if not df_outros.empty:
        with st.expander("❓ Itens com outros status"):
            # Correção aqui: selection_mode="single-row"
            sel_out = st.dataframe(df_outros[colunas_rapidas], column_config=col_cfg, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if sel_out.selection.rows:
                exibir_detalhes(df_outros.iloc[sel_out.selection.rows[0]], supabase)

def exibir_detalhes(item, supabase):
    st.markdown(f"### 🔍 Editando: {item['nome_cliente']}")
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            n_nome = st.text_input("Nome", value=item['nome_cliente'])
            n_status = st.selectbox("Status", 
                options=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"],
                index=(["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']) if item['status_projeto'] in ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"] else 0)
            )
        with col2:
            n_venda = st.number_input("Venda (R$)", value=float(item['valor_venda_total']), format="%.2f")
            n_custo = st.number_input("Custo Equip. (R$)", value=float(item['valor_custo_equipamentos']), format="%.2f")
        with col3:
            n_inst = st.text_input("Instalador", value=item['instalador_responsavel'] if item['instalador_responsavel'] else "")
            n_v_inst = st.number_input("Pago ao Inst. (R$)", value=float(item['valor_pago_instalador']), format="%.2f")

        n_mat = st.number_input("Materiais Extras (R$)", value=float(item['valor_custo_materiais_extras'] if item['valor_custo_materiais_extras'] else 0.0))
        n_lucro = n_venda - (n_custo + n_mat + n_v_inst)
        
        st.metric("LUCRO REAL", utils.to_br_currency(n_lucro))

        if st.button("💾 SALVAR ALTERAÇÕES", type="primary"):
            supabase.table('servicos_andamento').update({
                "nome_cliente": n_nome, "status_projeto": n_status, "valor_venda_total": n_venda,
                "valor_custo_equipamentos": n_custo, "valor_custo_materiais_extras": n_mat,
                "instalador_responsavel": n_inst, "valor_pago_instalador": n_v_inst, "lucro_estimado": n_lucro
            }).eq('id', item['id']).execute()
            st.success("Salvo!")
            st.rerun()
