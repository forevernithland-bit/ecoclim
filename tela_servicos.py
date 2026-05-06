import streamlit as st
import pandas as pd
import utils
from datetime import datetime, timedelta

def renderizar():
    st.markdown("## 🛠️ Gestão de Serviços e Orçamentos")
    
    supabase = st.session_state.supabase
    
    # 1. Carregar Dados
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df_raw = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    if df_raw.empty:
        st.info("Nenhum registro encontrado.")
        return

    # --- Lógica de Filtro de Cancelados (50 dias) ---
    def filtrar_cancelados(row):
        if row['status_projeto'] == 'Cancelado':
            data_orc = pd.to_datetime(row['data_orcamento']).date()
            if (datetime.now().date() - data_orc).days > 50:
                return False
        return True

    df_raw = df_raw[df_raw.apply(filtrar_cancelados, axis=1)]

    # --- SEPARAÇÃO DOS GRUPOS ---
    status_ativos = ['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO']
    status_orcamentos = ['Orçamento Enviado', 'Em Negociação', 'Cancelado']

    df_ativos = df_raw[df_raw['status_projeto'].isin(status_ativos)].copy()
    df_orcamentos = df_raw[df_raw['status_projeto'].isin(status_orcamentos)].copy()

    # Colunas de exibição rápida solicitadas
    colunas_rapidas = [
        'nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 
        'valor_custo_equipamentos', 'lucro_estimado', 
        'instalador_responsavel', 'valor_pago_instalador'
    ]
    
    col_cfg = {
        "nome_cliente": st.column_config.TextColumn("Cliente", width="medium"),
        "produtos_adquiridos": st.column_config.TextColumn("Produto", width="large"),
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
        # Mostra a tabela e captura a seleção
        selecionado_ativo = st.dataframe(
            df_ativos[colunas_rapidas],
            column_config=col_cfg,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single"
        )
        
        # Se clicar em um cliente, abre os detalhes
        if selecionado_ativo.selection.rows:
            idx = selecionado_ativo.selection.rows[0]
            item_completo = df_ativos.iloc[idx]
            exibir_detalhes(item_completo, supabase)
    else:
        st.write("_Nenhum serviço em andamento no momento._")

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # =========================================================================
    # PARTE DE BAIXO: ORÇAMENTOS
    # =========================================================================
    st.subheader("📝 Orçamentos e Negociações")
    if not df_orcamentos.empty:
        selecionado_orc = st.dataframe(
            df_orcamentos[colunas_rapidas],
            column_config=col_cfg,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single"
        )
        
        if selecionado_orc.selection.rows:
            idx_orc = selecionado_orc.selection.rows[0]
            item_orc_completo = df_orcamentos.iloc[idx_orc]
            exibir_detalhes(item_orc_completo, supabase)
    else:
        st.write("_Nenhum orçamento pendente._")

# Função auxiliar para mostrar o "Pop-up" (Formulário de Detalhes)
def exibir_detalhes(item, supabase):
    with st.expander(f"🔍 DETALHES COMPLETOS: {item['nome_cliente']}", expanded=True):
        st.warning("⚠️ Altere os dados abaixo e clique em 'Salvar Alterações' para atualizar o cliente.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            novo_nome = st.text_input("Nome do Cliente", value=item['nome_cliente'])
            novo_status = st.selectbox("Status do Projeto", 
                options=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"],
                index=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto'])
            )
        with col2:
            novo_venda = st.number_input("Valor de Venda (R$)", value=float(item['valor_venda_total']), format="%.2f")
            novo_custo_eq = st.number_input("Custo Equipamentos (R$)", value=float(item['valor_custo_equipamentos']), format="%.2f")
        with col3:
            novo_instalador = st.text_input("Instalador Responsável", value=item['instalador_responsavel'] if item['instalador_responsavel'] else "")
            novo_valor_inst = st.number_input("Valor da Instalação (R$)", value=float(item['valor_pago_instalador']), format="%.2f")

        st.info(f"**Produtos:** {item['produtos_adquiridos']}")
        
        # Memória de Cálculo em Tempo Real
        novo_mat_extra = st.number_input("Materiais Extras / Outros Custos (R$)", value=float(item['valor_custo_materiais_extras'] if item['valor_custo_materiais_extras'] else 0.0))
        
        novo_lucro = novo_venda - (novo_custo_eq + novo_mat_extra + novo_valor_inst)
        
        c_l1, c_l2 = st.columns(2)
        c_l1.metric("LUCRO ESTIMADO ATUALIZADO", utils.to_br_currency(novo_lucro))
        
        if st.button(f"💾 Salvar Alterações de {item['nome_cliente']}", type="primary"):
            try:
                supabase.table('servicos_andamento').update({
                    "nome_cliente": novo_nome,
                    "status_projeto": novo_status,
                    "valor_venda_total": novo_venda,
                    "valor_custo_equipamentos": novo_custo_eq,
                    "valor_custo_materiais_extras": novo_mat_extra,
                    "instalador_responsavel": novo_instalador,
                    "valor_pago_instalador": novo_valor_inst,
                    "lucro_estimado": novo_lucro
                }).eq('id', item['id']).execute()
                st.success("Dados atualizados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
