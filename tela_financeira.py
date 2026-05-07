import streamlit as st
import pandas as pd
import utils
from datetime import datetime

def renderizar():
    st.markdown("## 📊 Controle Financeiro - Ecoclim")
    
    # ==========================================
    # MENU LATERAL (SIDEBAR) COM SCROLL E FILTROS
    # ==========================================
    with st.sidebar:
        st.image("logo.png", width=150)
        st.markdown("### 📅 Filtros do Período")
        ano_selecionado = st.selectbox(
            "Ano de Referência:", 
            [utils.ano_atual - 1, utils.ano_atual, utils.ano_atual + 1], 
            index=1
        )
        
        st.markdown("---")
        st.markdown("### 🚀 Ações Rápidas")
        
        # BOTÃO DE IMPORTAÇÃO AUTOMÁTICA DE LUCRO
        if st.button("📥 IMPORTAR LUCRO DE SERVIÇOS", use_container_width=True, help="Busca o lucro líquido de todos os serviços concluídos no banco de dados"):
            importar_lucro_realizado(ano_selecionado)

    # ==========================================
    # CORPO PRINCIPAL
    # ==========================================
    
    # Contas padrão da Ecoclim
    contas_padrao = [
        "Lucro de Serviços (Ecoclim)", 
        "Vendas Diretas Loja", 
        "Receitas Terceirizadas", 
        "(-) Custos Fixos (Aluguel/Luz/Tel)", 
        "(-) Marketing e Anúncios",
        "(-) Impostos e DAS",
        "(-) Pró-labore e Salários",
        "SALDO FINAL LÍQUIDO"
    ]
    
    # Carrega os dados salvos no banco
    df = utils.load_year_data('controle_financeiro', contas_padrao, ano_selecionado)
    
    # Configuração das Colunas (Meses)
    cfg = {"MESES": st.column_config.TextColumn("Categorias / Contas", width="medium", disabled=True)}
    for m in utils.meses_pt:
        cfg[m] = st.column_config.NumberColumn(m, format="R$ %,.2f")
        
    st.markdown(f"#### 📑 Planilha de Fluxo de Caixa - {ano_selecionado}")
    
    with st.container(height=500, border=True): # Container com Scroll
        df_edit = st.data_editor(
            df, 
            column_config=cfg, 
            num_rows="dynamic", 
            use_container_width=True, 
            key="tabela_financeiro_main",
            hide_index=True
        )

    # ==========================================
    # CÁLCULOS E SALVAMENTO
    # ==========================================
    c1, c2 = st.columns([3, 1])
    
    with c1:
        if st.button("💾 GRAVAR ALTERAÇÕES FINANCEIRAS", type="primary", use_container_width=True):
            # Lógica para calcular o Saldo Final antes de salvar
            for m in utils.meses_pt:
                # Soma tudo o que não é a linha de Saldo Final
                entradas = df_edit.loc[~df_edit['MESES'].str.contains("SALDO FINAL"), m].sum()
                # Como custos já estão com (-), a soma simples resolve
                df_edit.loc[df_edit['MESES'] == "SALDO FINAL LÍQUIDO", m] = entradas
            
            utils.save_to_supabase('controle_financeiro', df_edit, ano_selecionado)
            st.success(f"Dados financeiros de {ano_selecionado} sincronizados com o banco de dados!")
            st.rerun()

    with c2:
        excel_data = utils.to_excel(df_edit)
        st.download_button(
            label="📥 EXCEL", 
            data=excel_data, 
            file_name=f"Financeiro_Ecoclim_{ano_selecionado}.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ==========================================
# FUNÇÃO DE INTEGRAÇÃO: IMPORTAR LUCRO REAL
# ==========================================
def importar_lucro_realizado(ano):
    supabase = st.session_state.supabase
    try:
        # Busca todos os serviços concluídos no ano selecionado
        res = supabase.table('servicos_andamento').select('lucro_estimado, data_conclusao')\
            .filter('status_projeto', 'in', '("Concluído PIX", "Concluído CARTÃO")')\
            .execute()
        
        servicos = res.data
        if not servicos:
            st.warning("Nenhum serviço concluído encontrado para importar lucro.")
            return

        # Dicionário para somar lucro por mês
        lucro_por_mes = {m: 0.0 for m in utils.meses_pt}
        
        for s in servicos:
            if s['data_conclusao']:
                dt = datetime.strptime(s['data_conclusao'], '%Y-%m-%d')
                if dt.year == ano:
                    mes_nome = utils.meses_pt[dt.month - 1]
                    lucro_por_mes[mes_nome] += float(s['lucro_estimado'] or 0.0)

        # Atualiza a tabela no banco de dados
        # Carrega o DF atual para não perder os outros dados
        df_atual = utils.load_year_data('controle_financeiro', [], ano)
        
        # Se a linha de Lucro de Serviços não existir, ela será criada
        if "Lucro de Serviços (Ecoclim)" not in df_atual['MESES'].values:
            nova_linha = {"MESES": "Lucro de Serviços (Ecoclim)"}
            for m in utils.meses_pt: nova_linha[m] = 0.0
            df_atual = pd.concat([df_atual, pd.DataFrame([nova_linha])], ignore_index=True)
            
        # Insere os valores somados
        for mes, valor in lucro_por_mes.items():
            df_atual.loc[df_atual['MESES'] == "Lucro de Serviços (Ecoclim)", mes] = valor
            
        utils.save_to_supabase('controle_financeiro', df_atual, ano)
        st.success("🚀 Lucro de Serviços importado com sucesso! Os valores foram atualizados na conta da Ecoclim.")
        st.rerun()

    except Exception as e:
        st.error(f"Erro na integração de lucros: {e}")
