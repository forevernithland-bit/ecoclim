import streamlit as st
import pandas as pd
import numpy as np
import datetime
import re
import os
import io
from supabase import create_client
from fpdf import FPDF

# =============================================================================
# MÓDULO 1: CONFIGURAÇÃO E CONEXÃO
# =============================================================================
st.set_page_config(page_title="Ecoclim ERP", layout="wide", page_icon="🌤️")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro na conexão Supabase: {e}")

# =============================================================================
# MÓDULO 2: UTILITÁRIOS E FORMATAÇÃO
# =============================================================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_atual = hoje.year
mes_hoje_idx = hoje.month 
mes_atual_nome = meses_pt[mes_hoje_idx - 1] 

def to_br_currency(val, show_cents=True):
    try:
        v = float(val)
        if show_cents:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return f"R$ {int(v):,}".replace(",", ".")
    except: return "R$ 0,00"

def parse_br_currency(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        clean = re.sub(r'[^\d,-]', '', str(val)).replace(",", ".")
        return float(clean) if clean else 0.0
    except: return 0.0

# =============================================================================
# MÓDULO 3: BANCO DE DADOS (FUNÇÕES GERAIS)
# =============================================================================
# --- CATÁLOGOS (CONFIGURAÇÕES) ---
def load_catalog(table_name):
    try:
        res = supabase.table(table_name).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame(columns=["Item", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)", "Descrição"])
        
        df = df.rename(columns={"item": "Item", "custo": "Custo (R$)", "margem": "Margem (%)", "descricao": "Descrição"})
        df['Venda (R$)'] = (df['Custo (R$)'] * (1 + df['Margem (%)'] / 100)).round().astype(int)
        df['Lucro (R$)'] = df['Venda (R$)'] - df['Custo (R$)']
        return df[["Item", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)", "Descrição"]]
    except:
        return pd.DataFrame(columns=["Item", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)", "Descrição"])

def save_catalog(table_name, df):
    try:
        data = []
        for _, row in df.iterrows():
            if row['Item'] and str(row['Item']).strip() != "":
                data.append({
                    "item": row['Item'],
                    "custo": float(row['Custo (R$)']),
                    "margem": float(row['Margem (%)']),
                    "descricao": str(row['Descrição']) if row['Descrição'] else ""
                })
        supabase.table(table_name).delete().neq("item", "___vazio___").execute()
        if data: supabase.table(table_name).insert(data).execute()
    except Exception as e: st.error(f"Erro ao sincronizar catálogo: {e}")

# --- FINANCEIRO ---
def load_year_data(table_name, itens_padrao, ano_escolhido):
    try:
        res = supabase.table(table_name).select("*").eq("ano", ano_escolhido).execute()
        df_raw = pd.DataFrame(res.data)
        if df_raw.empty:
            df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
            df.insert(0, 'MESES', itens_padrao); return df
        
        df_pivot = df_raw.pivot(index='conta', columns='mes', values='valor').fillna(0)
        for m in meses_pt:
            if m not in df_pivot.columns: df_pivot[m] = 0
        df_pivot = df_pivot[meses_pt].reset_index()
        df_pivot.rename(columns={'conta': 'MESES'}, inplace=True)
        
        for item in itens_padrao:
            if item not in df_pivot['MESES'].values:
                nova_linha = {m: 0 for m in meses_pt}; nova_linha['MESES'] = item
                df_pivot = pd.concat([df_pivot, pd.DataFrame([nova_linha])], ignore_index=True)
        
        df_pivot.set_index('MESES', inplace=True); df_pivot = df_pivot.reindex(itens_padrao).reset_index()
        df_pivot[meses_pt] = df_pivot[meses_pt].astype(float)
        return df_pivot
    except:
        df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao); return df

def save_to_supabase(table_name, df_int, ano_escolhido):
    try:
        df_melted = df_int.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
        df_melted['ano'] = ano_escolhido; df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
        data = df_melted.to_dict(orient='records')
        supabase.table(table_name).delete().eq('ano', ano_escolhido).execute()
        supabase.table(table_name).insert(data).execute()
    except Exception as e: st.error(f"Erro ao salvar financeiro: {e}")

# --- PREFERÊNCIAS DO USUÁRIO ---
def load_user_settings():
    try:
        res = supabase.table('configuracoes').select("*").eq('user_id', 'breno.lima').execute()
        if res.data: return res.data[0]['mes_inicio'], res.data[0]['mes_fim']
    except: pass
    return "JANEIRO", mes_atual_nome

def save_user_settings(inicio, fim):
    try:
        data = {"id": 1, "user_id": "breno.lima", "mes_inicio": inicio, "mes_fim": fim}
        supabase.table('configuracoes').upsert(data).execute()
    except: pass

# =============================================================================
# MÓDULO 4: GERADOR DE PDF (ORÇAMENTOS)
# =============================================================================
def gerar_pdf_orcamento(cliente, tel, produto, df_equip, desc_s, val_s, desc_o, val_o, total, obs, mostrar_val):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    if os.path.exists("logo.png"): pdf.image("logo.png", 10, 8, 40)
    
    pdf.cell(0, 10, "PROPOSTA COMERCIAL", ln=True, align="R")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y')}", ln=True, align="R")
    pdf.cell(0, 5, "Validade: 15 dias", ln=True, align="R")
    pdf.ln(10)
    
    pdf.set_fill_color(230, 240, 255)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, " DADOS DO CLIENTE", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, f" Nome: {cliente}", border=1, ln=True)
    pdf.cell(0, 8, f" Telefone: {tel}", border=1, ln=True)
    pdf.ln(5)

    img_urls = {
        "AQUECEDOR SOLAR TRADICIONAL": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+Solar+Tradicional",
        "AQUECEDOR SOLAR A VÁCUO ACOPLADO": "https://dummyimage.com/600x200/004488/fff&text=Tubos+a+Vacuo+Acoplado",
        "AQUECEDOR SOLAR MODULAR": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+Solar+Modular",
        "AQUECEDOR DE PISCINA - TRADICIONAL": "https://dummyimage.com/600x200/004488/fff&text=Aquecedor+de+Piscina",
        "AQUECEDOR DE PISCINA - TROCADOR DE CALOR": "https://dummyimage.com/600x200/004488/fff&text=Trocador+de+Calor",
        "SISTEMAS DE PRESSURIZAÇÃO": "https://dummyimage.com/600x200/004488/fff&text=Sistema+de+Pressurizacao"
    }
    try: pdf.image(img_urls.get(produto, img_urls["AQUECEDOR SOLAR TRADICIONAL"]), x=10, w=190)
    except: pdf.cell(0, 20, f"[IMAGEM: {produto}]", border=1, ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 8, " 1. EQUIPAMENTOS", border=1, ln=True, fill=True)
    if mostrar_val:
        pdf.cell(100, 8, " Item", border=1); pdf.cell(30, 8, " Qtd", border=1, align="C"); pdf.cell(60, 8, " Subtotal", border=1, ln=True, align="R")
    else:
        pdf.cell(160, 8, " Item", border=1); pdf.cell(30, 8, " Qtd", border=1, ln=True, align="C")
    
    for _, row in df_equip.iterrows():
        nome = row['Produto da Base'] if row['Produto da Base'] != "OUTRO" else row['Produto Manual']
        if str(nome).strip() != "":
            q, v = float(row['Quantidade']), float(row['Venda (R$)'])
            pdf.set_font("helvetica", "B", 10)
            if mostrar_val:
                pdf.cell(100, 8, f" {nome}", border=1); pdf.cell(30, 8, f" {int(q)}", border=1, align="C"); pdf.cell(60, 8, f" {to_br_currency(q*v, False)}", border=1, ln=True, align="R")
            else:
                pdf.cell(160, 8, f" {nome}", border=1); pdf.cell(30, 8, f" {int(q)}", border=1, ln=True, align="C")

    if val_s > 0:
        pdf.ln(5); pdf.set_font("helvetica", "B", 12); pdf.cell(0, 8, " 2. SERVIÇOS", border=1, ln=True, fill=True)
        pdf.set_font("helvetica", "", 10); pdf.multi_cell(0, 6, f" {desc_s}", border=1)
        pdf.cell(130, 8, " Valor do Serviço:", border=1); pdf.cell(60, 8, f" {to_br_currency(val_s, False)}", border=1, ln=True, align="R")

    if val_o > 0:
        pdf.ln(5); pdf.set_font("helvetica", "B", 12); pdf.cell(0, 8, " 3. DIVERSOS", border=1, ln=True, fill=True)
        pdf.set_font("helvetica", "", 10); pdf.multi_cell(0, 6, f" {desc_o}", border=1)
        pdf.cell(130, 8, " Valor Adicional:", border=1); pdf.cell(60, 8, f" {to_br_currency(val_o, False)}", border=1, ln=True, align="R")

    pdf.ln(5); pdf.set_font("helvetica", "B", 14); pdf.set_fill_color(0, 68, 136); pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 10, " INVESTIMENTO TOTAL", border=1, fill=True); pdf.cell(60, 10, f" {to_br_currency(total, False)}", border=1, ln=True, align="R", fill=True)
    pdf.ln(10); pdf.set_text_color(200, 0, 0); pdf.set_font("helvetica", "B", 10); pdf.multi_cell(0, 6, f"OBSERVAÇÕES:\n{obs}", border=0)
    
    return bytes(pdf.output())

# =============================================================================
# MÓDULO 5: CSS GLOBAL
# =============================================================================
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }
    div.container-tabelas div[data-testid="stVerticalBlock"] { gap: 0px !important; padding: 0px !important; }
    [data-testid="stTable"] { overflow: hidden !important; }
    .dvn-scroller { overflow-y: hidden !important; }
    .stDataFrame table, .stDataEditor table { table-layout: fixed !important; width: 100% !important; }
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { text-align: center !important; font-size: 0.85rem !important; }
    
    /* ESCONDE CABEÇALHOS DAS TABELAS DE RESULTADO NO FINANCEIRO */
    .financeiro div[data-testid="stDataFrame"] thead { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# MÓDULO 6: TELA PÁGINA INICIAL
# =============================================================================
def tela_inicial():
    st.markdown("## 🏠 Página Inicial")
    st.write(f"Bem-vindo, Breno. Hoje é {hoje.strftime('%d/%m/%Y')}")
    st.write("---")
    c1, c2 = st.columns(2); c3, c4 = st.columns(2)
    if c1.button("📝\n\nFazer Orçamento", use_container_width=True): st.session_state.pagina_atual = "Orçamentos"; st.rerun()
    if c2.button("📊\n\nControle Financeiro", use_container_width=True): st.session_state.pagina_atual = "Controle Financeiro"; st.rerun()
    if c3.button("⚙️\n\nConfigurações", use_container_width=True): st.session_state.pagina_atual = "Configurações"; st.rerun()
    if c4.button("🚪\n\nSair do Sistema", use_container_width=True): st.session_state.authenticated = False; st.rerun()

# =============================================================================
# MÓDULO 7: TELA CONFIGURAÇÕES
# =============================================================================
def tela_configuracoes():
    st.markdown("## ⚙️ Configurações e Base de Dados")
    
    with st.expander("📥 Importar Equipamentos via Excel", expanded=False):
        st.write("Planilha: **PRODUTO**, **CUSTO**, **DESCRIÇÃO**")
        file = st.file_uploader("Subir .xlsx", type=["xlsx"])
        if file:
            try:
                df_ex = pd.read_excel(file)
                if all(c in df_ex.columns for c in ["PRODUTO", "CUSTO", "DESCRIÇÃO"]):
                    novos = pd.DataFrame({"Item": df_ex["PRODUTO"], "Custo (R$)": df_ex["CUSTO"], "Margem (%)": 70.0, "Descrição": df_ex["DESCRIÇÃO"]})
                    if st.button("Confirmar Importação"):
                        save_catalog('catalogo_produtos', novos); st.success("Importado com sucesso!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

    tab1, tab2, tab3 = st.tabs(["🛒 Equipamentos", "🛠️ Serviços", "➕ Terceirizados"])
    
    def render_editor(table_name):
        df_db = load_catalog(table_name)
        col_cfg = {
            "Item": st.column_config.TextColumn("Item", width="medium"),
            "Custo (R$)": st.column_config.NumberColumn("Custo", format="R$ %.2f"),
            "Margem (%)": st.column_config.NumberColumn("Margem", format="%.1f%%"),
            "Lucro (R$)": st.column_config.NumberColumn("Lucro", disabled=True, format="R$ %.2f"),
            "Venda (R$)": st.column_config.NumberColumn("Venda (Final)", disabled=True, format="R$ %d"),
            "Descrição": st.column_config.TextColumn("Descrição PDF", width="large")
        }
        df_edit = st.data_editor(df_db, num_rows="dynamic", column_config=col_cfg, use_container_width=True, key=f"editor_{table_name}")
        
        df_edit['Venda (R$)'] = (df_edit['Custo (R$)'] * (1 + df_edit['Margem (%)'] / 100)).fillna(0).round().astype(int)
        df_edit['Lucro (R$)'] = df_edit['Venda (R$)'] - df_edit['Custo (R$)']
        
        if st.button(f"💾 Gravar Alterações: {table_name}"):
            save_catalog(table_name, df_edit); st.success("Banco de dados atualizado!"); st.rerun()

    with tab1: render_editor('catalogo_produtos')
    with tab2: render_editor('catalogo_servicos')
    with tab3: render_editor('catalogo_outros')

# =============================================================================
# MÓDULO 8: TELA ORÇAMENTOS
# =============================================================================
def tela_orcamentos():
    st.markdown("## 📝 Novo Orçamento")
    cat_p = load_catalog('catalogo_produtos'); lista_p = cat_p['Item'].tolist()
    cat_s = load_catalog('catalogo_servicos'); lista_s = cat_s['Item'].tolist()
    cat_o = load_catalog('catalogo_outros'); lista_o = cat_o['Item'].tolist()
    
    with st.container(border=True):
        st.subheader("👤 Cliente")
        c1, c2 = st.columns(2)
        nome_c = c1.text_input("Nome do Cliente")
        tel_c = c2.text_input("WhatsApp")
        capa = st.selectbox("Modelo para Capa", ["AQUECEDOR SOLAR TRADICIONAL", "AQUECEDOR SOLAR A VÁCUO ACOPLADO", "AQUECEDOR SOLAR MODULAR", "AQUECEDOR DE PISCINA - TRADICIONAL", "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", "SISTEMAS DE PRESSURIZAÇÃO"])

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        mostrar_pdf = st.checkbox("Mostrar Preços Unitários no PDF?", value=True)
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Quantidade": 1, "Venda (R$)": 0.0} for _ in range(5)])
        
        cfg = {"Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_p + ["OUTRO"]), "Venda (R$)": st.column_config.NumberColumn("Preço", format="R$ %d")}
        df_ed = st.data_editor(st.session_state.df_orc, column_config=cfg, num_rows="dynamic", use_container_width=True)
        
        for i in range(len(df_ed)):
            p = df_ed.at[i, 'Produto da Base']
            if p in lista_p and df_ed.at[i, 'Venda (R$)'] == 0:
                df_ed.at[i, 'Venda (R$)'] = cat_p.loc[cat_p['Item'] == p, 'Venda (R$)'].values[0]
                st.session_state.df_orc = df_ed; st.rerun()
        st.session_state.df_orc = df_ed
        total_e = sum(df_ed['Quantidade'] * df_ed['Venda (R$)'])
        st.write(f"Subtotal: {to_br_currency(total_e, False)}")

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços / Diversos")
        s_sel = st.selectbox("Selecionar Serviço:", [""] + lista_s + ["Manual"])
        if s_sel == "Manual": d_s = st.text_area("Descreva:"); v_s = st.number_input("Valor:", min_value=0.0)
        elif s_sel != "":
            d_s = f"{s_sel}\n{cat_s.loc[cat_s['Item']==s_sel, 'Descrição'].values[0]}"
            v_s = float(cat_s.loc[cat_s['Item']==s_sel, 'Venda (R$)'].values[0]); st.write(f"Valor: {to_br_currency(v_s, False)}")
        else: d_s, v_s = "", 0.0
        
        o_sel = st.selectbox("Selecionar Diversos:", [""] + lista_o + ["Manual"])
        if o_sel == "Manual": d_o = st.text_area("Descreva: "); v_o = st.number_input("Valor Adicional:", min_value=0.0)
        elif o_sel != "":
            d_o = f"{o_sel}\n{cat_o.loc[cat_o['Item']==o_sel, 'Descrição'].values[0]}"
            v_o = float(cat_o.loc[cat_o['Item']==o_sel, 'Venda (R$)'].values[0]); st.write(f"Valor: {to_br_currency(v_o, False)}")
        else: d_o, v_o = "", 0.0

    total_g = total_e + v_s + v_o
    st.subheader(f"INVESTIMENTO TOTAL: {to_br_currency(total_g, False)}")
    obs = st.text_area("Notas:", value="Material Hidráulico não inclusos na proposta")

    if st.button("🚀 SALVAR CRM E GERAR PDF", type="primary"):
        if nome_c:
            try:
                supabase.table("clientes_orcamentos").insert({"nome": nome_c, "telefone": tel_c, "produto_ref": capa, "valor_total": total_g, "status": "Em fase de orçamento"}).execute()
                st.success("Salvo no CRM!")
            except: st.warning("Erro ao salvar no Supabase.")
            
            pdf_bytes = gerar_pdf_orcamento(nome_c, tel_c, capa, df_ed, d_s, v_s, d_o, v_o, total_g, obs, mostrar_pdf)
            st.download_button("📥 BAIXAR ORÇAMENTO", pdf_bytes, f"Orcamento_{nome_c}.pdf", "application/pdf", use_container_width=True)
        else: st.error("Digite o nome do cliente!")

# =============================================================================
# MÓDULO 9: TELA CONTROLE FINANCEIRO (COMPLETO RESTAURADO)
# =============================================================================
def tela_financeira():
    st.markdown('<div class="financeiro">', unsafe_allow_html=True)
    st.subheader("📊 Controle Financeiro")
    
    with st.sidebar:
        ano_selecionado = st.selectbox("Ano Fiscal", options=[2025, 2026, 2027, 2028], index=1)
        st.write("---")
        st.markdown("### 👁️ Linha do Tempo")
        
        pref_inicio, pref_fim = load_user_settings()
        if pref_inicio not in meses_pt: pref_inicio = "JANEIRO"
        if pref_fim not in meses_pt: pref_fim = mes_atual_nome
            
        mes_inicio, mes_fim = st.select_slider("Período Visível:", options=meses_pt, value=(pref_inicio, pref_fim))
        if (mes_inicio != pref_inicio) or (mes_fim != pref_fim): save_user_settings(mes_inicio, mes_fim)
            
        idx_inicio = meses_pt.index(mes_inicio)
        idx_fim = meses_pt.index(mes_fim)
        colunas_visiveis = ["MESES"] + meses_pt[idx_inicio:idx_fim + 1]

        if st.button("🔄 Recarregar Dados"): st.session_state.pop('ano_dados_atual', None); st.rerun()

    contas_p = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
    contas_e = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']
    
    if 'ano_dados_atual' not in st.session_state or st.session_state.ano_dados_atual != ano_selecionado:
        st.session_state.df_p = load_year_data('patrimonio', contas_p, ano_selecionado)
        st.session_state.df_e = load_year_data('entradas', contas_e, ano_selecionado)
        st.session_state.ano_dados_atual = ano_selecionado

    col_cfg = {"MESES": st.column_config.TextColumn("MESES", width=220, disabled=True)}
    for m in meses_pt: col_cfg[m] = st.column_config.TextColumn(m, width=80) 

    st.markdown('<div class="container-tabelas">', unsafe_allow_html=True)
    
    # ---------------------------------------------
    # 9.1 PATRIMÔNIO (EDITÁVEL + RESULTADOS)
    # ---------------------------------------------
    df_p_display = st.session_state.df_p[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_p_display[m] = df_p_display[m].apply(lambda x: to_br_currency(x, False))
    styled_df_p = df_p_display.style.set_properties(subset=[mes_atual_nome] if mes_atual_nome in colunas_visiveis and ano_selecionado == ano_atual else [], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
    df_p_edit_str = st.data_editor(styled_df_p, hide_index=True, column_config=col_cfg, use_container_width=True, height=295)

    if not df_p_edit_str.equals(df_p_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_p.loc[:, m] = df_p_edit_str[m].apply(parse_br_currency)
        save_to_supabase('patrimonio', st.session_state.df_p, ano_selecionado); st.toast("💾 Salvo!", icon="✅"); st.rerun()

    df_n = st.session_state.df_p.set_index('MESES')
    pat_liq = df_n.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum()
    pat_tot = pat_liq + df_n.loc['IMÓVEIS'] + df_n.loc['VEÍCULOS']
    var_abs = pat_tot.diff().fillna(0); var_pct = (pat_tot.pct_change().fillna(0) * 100).round(2)

    for i, m in enumerate(meses_pt):
        if (ano_selecionado > ano_atual) or (ano_selecionado == ano_atual and i > mes_hoje_idx - 1):
            var_abs[m] = 0; var_pct[m] = 0

    df_res_p = pd.DataFrame({'MESES': ['PATRIMÔNIO LÍQUIDO', 'PATRIMÔNIO TOTAL', 'VARIAÇÃO MENSAL ($)', 'VARIAÇÃO MENSAL (%)']})
    for m in meses_pt: df_res_p[m] = [pat_liq[m], pat_tot[m], var_abs[m], f"{var_pct[m]:.2f}%"]
    styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_p.format(lambda x: x if isinstance(x, str) and "%" in x else to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

    # ---------------------------------------------
    # 9.2 ENTRADAS (EDITÁVEL + RESULTADOS)
    # ---------------------------------------------
    df_e_display = st.session_state.df_e[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_e_display[m] = df_e_display[m].apply(lambda x: to_br_currency(x, False))
    styled_df_e = df_e_display.style.set_properties(subset=[mes_atual_nome] if mes_atual_nome in colunas_visiveis and ano_selecionado == ano_atual else [], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
    df_e_edit_str = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

    if not df_e_edit_str.equals(df_e_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_e.loc[:, m] = df_e_edit_str[m].apply(parse_br_currency)
        save_to_supabase('entradas', st.session_state.df_e, ano_selecionado); st.toast("💾 Salvo!", icon="✅"); st.rerun()

    df_e_n = st.session_state.df_e.set_index('MESES'); tot_ent = df_e_n.sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
    for m in meses_pt: df_res_e[m] = [tot_ent[m]]
    styled_res_e = df_res_e[colunas_visiveis].style.apply(lambda row: [f'background-color: #9BC2E6; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_e.format(lambda x: to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

    # ---------------------------------------------
    # 9.3 RENDIMENTOS MENSAIS
    # ---------------------------------------------
    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    xp_val = df_n.loc['INVESTIMENTO XP']; inter_val = df_n.loc['CONTA INTER']
    xp_var = xp_val.diff().fillna(0); inter_var = inter_val.diff().fillna(0); rend_total = xp_var + inter_var; prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    df_rend = pd.DataFrame({'MESES': ['VARIAÇÃO INVESTIMENTO XP', 'VARIAÇÃO CONTA INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    for i, m in enumerate(meses_pt):
        if (ano_selecionado > ano_atual) or (ano_selecionado == ano_atual and i > mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt = rend_total[m]; pb = prev_bal[m]; pct_val = (rt / pb * 100) if pb > 0 else 0
            df_rend[m] = [xp_var[m], inter_var[m], rt, f"{pct_val:.2f}%".replace(".", ","), tot_ent[m] + rt]
    styled_rend = df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold; color: black; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_rend.format(lambda x: x if isinstance(x, str) and "%" in x else to_br_currency(x, False)), hide_index=True, column_config=col_cfg, use_container_width=True, height=215)
    st.markdown('</div></div>', unsafe_allow_html=True)

    # ---------------------------------------------
    # 9.4 MÉTRICAS E GRÁFICOS
    # ---------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calculo = meses_pt if ano_selecionado < ano_atual else meses_pt[:mes_hoje_idx]
    media_entradas = tot_ent[meses_calculo].mean(); media_rend_r = rend_total[meses_calculo].mean(); media_rend_p = (rend_total[meses_calculo] / prev_bal[meses_calculo].replace(0, np.nan)).mean() * 100
    idx_ref = 11 if ano_selecionado < ano_atual else (mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0)

    c1.metric("💰 MÉDIA ENTRADAS FIXAS", to_br_currency(media_entradas, False))
    c2.metric("🎯 LIMITE DE GASTO (MÉDIA REND.)", to_br_currency(media_rend_r, False))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", to_br_currency(pat_tot.iloc[idx_ref], False))

    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Aumento de Patrimônio Total"); st.line_chart(pat_tot[meses_pt])
        st.subheader("Rendimento Mensal (R$)"); st.bar_chart(rend_total[meses_pt])
    with g2:
        st.subheader("Salário + Rendimento Mensal"); st.area_chart(tot_ent[meses_pt] + rend_total[meses_pt])
        st.subheader("Faturamento Ecoclim"); st.line_chart(df_e_n.loc['ECOCLIM'][meses_pt])

# =============================================================================
# MÓDULO 10: ROTEAMENTO PRINCIPAL (LOGIN E MENUS)
# =============================================================================
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "pagina_atual" not in st.session_state: st.session_state.pagina_atual = "Página Inicial"

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        if os.path.exists("logo.png"): st.image("logo.png", width=200)
        st.subheader("Login Ecoclim ERP")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Acessar Sistema", use_container_width=True):
            if u == "breno.lima" and p == "Ecoclim2026@":
                st.session_state.authenticated = True; st.rerun()
            else: st.error("Credenciais inválidas.")
else:
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png")
        st.write("### Menu Principal")
        menu = st.radio("Navegação", ["Página Inicial", "Orçamentos", "Controle Financeiro", "Configurações"], label_visibility="collapsed")
        st.session_state.pagina_atual = menu
        st.write("---")
        if st.button("🚪 Sair"): st.session_state.authenticated = False; st.rerun()

    if st.session_state.pagina_atual == "Página Inicial": tela_inicial()
    elif st.session_state.pagina_atual == "Orçamentos": tela_orcamentos()
    elif st.session_state.pagina_atual == "Controle Financeiro": tela_financeira()
    elif st.session_state.pagina_atual == "Configurações": tela_configuracoes()
