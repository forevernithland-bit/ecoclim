import streamlit as st
import pandas as pd
import utils
from datetime import datetime

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

    # Filtro de Cancelados (50 dias)
    df_raw = df_raw[df_raw.apply(lambda r: not (r['status_projeto'] == 'Cancelado' and r['data_orcamento'] and (datetime.now().date() - pd.to_datetime(r['data_orcamento']).date()).days > 50), axis=1)]

    # Separação dos Grupos
    status_ativos = ['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO']
    status_orcamentos = ['Orçamento Enviado', 'Em Negociação', 'Cancelado']

    df_ativos = df_raw[df_raw['status_projeto'].isin(status_ativos)].copy()
    df_orcamentos = df_raw[df_raw['status_projeto'].isin(status_orcamentos)].copy()

    colunas_rapidas = ['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'valor_custo_equipamentos', 'lucro_estimado', 'instalador_responsavel']
    
    col_cfg = {
        "nome_cliente": st.column_config.TextColumn("Cliente", width="medium"),
        "produtos_adquiridos": st.column_config.TextColumn("Resumo Itens", width="medium"),
        "valor_venda_total": st.column_config.NumberColumn("Venda Total", format="R$ %,.2f"),
        "valor_custo_equipamentos": st.column_config.NumberColumn("Custo Total", format="R$ %,.2f"),
        "lucro_estimado": st.column_config.NumberColumn("Lucro Real", format="R$ %,.2f"),
        "instalador_responsavel": st.column_config.TextColumn("Instalador"),
    }

    # --- PARTE SUPERIOR: SERVIÇOS ---
    st.subheader("✅ Serviços em Andamento / Concluídos")
    if not df_ativos.empty:
        sel_ativo = st.dataframe(df_ativos[colunas_rapidas], column_config=col_cfg, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if sel_ativo.selection.rows:
            exibir_detalhes_avancados(df_ativos.iloc[sel_ativo.selection.rows[0]], supabase)
    else: st.write("_Sem serviços ativos._")

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # --- PARTE INFERIOR: ORÇAMENTOS ---
    st.subheader("📝 Orçamentos e Negociações")
    if not df_orcamentos.empty:
        sel_orc = st.dataframe(df_orcamentos[colunas_rapidas], column_config=col_cfg, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if sel_orc.selection.rows:
            exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)
    else: st.write("_Sem orçamentos pendentes._")

def exibir_detalhes_avancados(item, supabase):
    st.markdown(f"### 🔍 Gerenciar Projeto: {item['nome_cliente']}")
    
    with st.container(border=True):
        # --- CABEÇALHO DE STATUS E INSTALADOR ---
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            n_status = st.selectbox("Status Atual", 
                options=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"],
                index=(["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']) if item['status_projeto'] in ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"] else 0)
            )
        with c2:
            n_inst = st.text_input("Técnico / Instalador", value=item['instalador_responsavel'] if item['instalador_responsavel'] else "")
        with c3:
            n_v_inst = st.number_input("Valor Pago ao Instalador (R$)", value=float(item['valor_pago_instalador'] if item['valor_pago_instalador'] else 0.0), format="%.2f")

        st.markdown("---")
        st.subheader("📋 Composição de Itens e Aditivos")
        st.write("_Aqui você pode adicionar novas linhas para materiais extras ou aditivos de serviço._")

        # Preparar dados para o editor de itens
        # Se não houver detalhamento salvo, criamos a primeira linha com o resumo do orçamento
        if not item.get('detalhamento_itens') or item['detalhamento_itens'] == []:
            dados_itens = pd.DataFrame([
                {"Descrição": item['produtos_adquiridos'], "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total'])}
            ])
        else:
            dados_itens = pd.DataFrame(item['detalhamento_itens'])

        # Configuração das colunas da memória de cálculo (Imagem 2)
        col_itens_cfg = {
            "Descrição": st.column_config.TextColumn("Item / Descrição / Aditivo", width="large", required=True),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=1, default=1, width="small"),
            "Custo Un.": st.column_config.NumberColumn("Custo Un. (R$)", format="R$ %,.2f", required=True),
            "Venda Un.": st.column_config.NumberColumn("Venda Un. (R$)", format="R$ %,.2f", required=True),
        }

        # O EDITOR DE DADOS (Aqui a mágica acontece)
        df_itens_edit = st.data_editor(dados_itens, column_config=col_itens_cfg, num_rows="dynamic", use_container_width=True, key=f"editor_itens_{item['id']}")

        # Cálculos de Totais baseados nas linhas
        total_venda_calculado = (df_itens_edit['Venda Un.'] * df_itens_edit['Qtd']).sum()
        total_custo_calculado = (df_itens_edit['Custo Un.'] * df_itens_edit['Qtd']).sum()
        lucro_final = total_venda_calculado - (total_custo_calculado + n_v_inst)

        # Exibição dos resultados financeiros do serviço
        st.markdown("#### Resumo Financeiro Atualizado")
        res1, res2, res3 = st.columns(3)
        res1.metric("Faturamento Total", utils.to_br_currency(total_venda_calculado))
        res2.metric("Custo Total (Mat + Inst)", utils.to_br_currency(total_custo_calculado + n_v_inst))
        res3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_final), delta=f"{((lucro_final/total_venda_calculado)*100 if total_venda_calculado > 0 else 0):.1f}% Margem")

        if st.button("💾 SALVAR TODAS AS ALTERAÇÕES", type="primary", use_container_width=True):
            try:
                # Gerar o novo resumo de produtos para a tabela principal
                resumo_texto = ", ".join([f"{int(r['Qtd'])}x {r['Descrição']}" for _, r in df_itens_edit.iterrows()])
                
                supabase.table('servicos_andamento').update({
                    "status_projeto": n_status,
                    "instalador_responsavel": n_inst,
                    "valor_pago_instalador": n_v_inst,
                    "valor_venda_total": float(total_venda_calculado),
                    "valor_custo_equipamentos": float(total_custo_calculado),
                    "lucro_estimado": float(lucro_final),
                    "produtos_adquiridos": resumo_texto,
                    "detalhamento_itens": df_itens_edit.to_dict('records') # Salva a tabela inteira!
                }).eq('id', item['id']).execute()
                
                st.success("Projeto atualizado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
