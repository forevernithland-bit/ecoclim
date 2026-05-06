import streamlit as st
import pandas as pd
import numpy as np
import datetime
import re
import os
from supabase import create_client
from fpdf import FPDF

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO
# ==========================================
st.set_page_config(page_title="Controle Financeiro", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Erro na conexão Supabase: {e}")

# ==========================================
# 2. VARIÁVEIS, FORMATAÇÃO E BASES DE DADOS
# ==========================================
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
hoje = datetime.datetime.now()
ano_atual = hoje.year
mes_hoje_idx = hoje.month 
mes_atual_nome = meses_pt[mes_hoje_idx - 1] 

def to_br_currency(val):
    try:
        v = float(val)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def parse_br_currency(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        clean = re.sub(r'[^\d,-]', '', str(val)).replace(",", ".")
        return float(clean) if clean else 0.0
    except: return 0.0

# --- BASES DE DADOS SIMULADAS (Depois podemos puxar do Supabase) ---
# Tabela de Produtos
db_produtos = {
    "Boiler Aquecedor Solar 200L": 2500.00,
    "Boiler Aquecedor Solar 400L": 3800.00,
    "Placa Coletora Solar 1x1m": 850.00,
    "Trocador de Calor Piscina 40m3": 9500.00,
    "Bomba Pressurizadora 1/2 CV": 1200.00,
    "Tubo a Vácuo (Unidade)": 150.00
}

# Tabela de Serviços
db_servicos = {
    "Instalação Padrão Aquecedor Solar": 1500.00,
    "Instalação Trocador de Calor": 1200.00,
    "Manutenção Preventiva Sistema": 450.00,
    "Limpeza de Placas e Boiler": 300.00
}

# Tabela de Outros (Terceirizados)
db_outros = {
    "Locação de Guindaste/Munck": 800.00,
    "Frete Terceirizado Especial": 350.00,
    "Material Hidráulico Extra": 500.00
}

# ==========================================
# 3. FUNÇÕES FINANCEIRAS
# ==========================================
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
        df_pivot[meses_pt] = df_pivot[meses_pt].astype(int)
        return df_pivot
    except:
        df = pd.DataFrame(0, index=range(len(itens_padrao)), columns=meses_pt)
        df.insert(0, 'MESES', itens_padrao); return df

def save_to_supabase(table_name, df_int, ano_escolhido):
    try:
        df_melted = df_int.melt(id_vars=['MESES'], var_name='mes', value_name='valor')
        df_melted['ano'] = ano_escolhido; df_melted.rename(columns={'MESES': 'conta'}, inplace=True)
        df_melted['valor'] = df_melted['valor'].astype(int)
        data = df_melted.to_dict(orient='records')
        supabase.table(table_name).delete().eq('ano', ano_escolhido).execute()
        supabase.table(table_name).insert(data).execute()
    except Exception as e: pass

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

# ==========================================
# 4. CSS GERAL E LOGIN
# ==========================================
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }
    div.container-tabelas div[data-testid="stVerticalBlock"] { gap: 0px !important; padding: 0px !important; }
    [data-testid="stTable"] { overflow: hidden !important; }
    .dvn-scroller { overflow-y: hidden !important; }
    .stDataFrame table, .stDataEditor table { table-layout: fixed !important; width: 100% !important; }
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { text-align: center !important; font-size: 0.85rem !important; }
    .financeiro section.main div[data-testid="stDataFrame"]:nth-of-type(1) thead, .financeiro section.main div[data-testid="stDataEditor"]:nth-of-type(2) thead, .financeiro section.main div[data-testid="stDataFrame"]:nth-of-type(2) thead, .financeiro section.main div[data-testid="stDataFrame"]:nth-of-type(3) thead { display: none !important; }
    </style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "pagina_atual" not in st.session_state: st.session_state.pagina_atual = "Página Inicial"

def login_screen():
    if os.path.exists("logo.png"):
        col_img1, col_img2, col_img3 = st.columns([1, 1, 1])
        with col_img2: st.image("logo.png", use_container_width=True)
    st.markdown("<br><h2 style='text-align: center;'>Acesso ao Sistema</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        user = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        if st.button("Entrar", use_container_width=True):
            if user == "breno.lima" and password == "Ecoclim2026@":
                st.session_state.authenticated = True; st.rerun()
            else: st.error("Usuário ou senha incorretos")

# ==========================================
# 5. GERADOR DE PDF (ORÇAMENTOS)
# ==========================================
def gerar_pdf_orcamento(cliente, telefone, produto, df_equip, desc_serv, val_serv, desc_outros, val_outros, total, obs, mostrar_val_equip):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    
    if os.path.exists("logo.png"): pdf.image("logo.png", 10, 8, 40)
    
    pdf.cell(0, 10, "PROPOSTA COMERCIAL", ln=True, align="R")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y')}", ln=True, align="R")
    pdf.cell(0, 5, "Validade da proposta: 15 dias", ln=True, align="R")
    pdf.ln(10)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.set_fill_color(230, 240, 255)
    pdf.cell(0, 8, " DADOS DO CLIENTE", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, f" Nome: {cliente}", border=1, ln=True)
    pdf.cell(0, 8, f" Telefone: {telefone}", border=1, ln=True)
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
    except: pdf.cell(0, 20, f"[IMAGEM DO PRODUTO: {produto}]", border=1, ln=True, align="C")
    pdf.ln(5)

    # 1. Equipamentos
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, " 1. DESCRIÇÃO DE EQUIPAMENTOS", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "B", 10)
    
    # Lógica de Ocultar/Mostrar Valores
    if mostrar_val_equip:
        pdf.cell(100, 8, " Item", border=1)
        pdf.cell(30, 8, " Qtd", border=1, align="C")
        pdf.cell(60, 8, " Subtotal", border=1, ln=True, align="R")
    else:
        pdf.cell(160, 8, " Item", border=1)
        pdf.cell(30, 8, " Qtd", border=1, ln=True, align="C")
    
    pdf.set_font("helvetica", "", 10)
    for _, row in df_equip.iterrows():
        nome = row['Produto da Base'] if row['Produto da Base'] != "OUTRO (Digitar)" else row['Produto Manual']
        if nome.strip() != "":
            q = float(row['Quantidade'])
            v = float(row['Valor Un.'])
            if mostrar_val_equip:
                pdf.cell(100, 8, f" {nome}", border=1)
                pdf.cell(30, 8, f" {int(q)}", border=1, align="C")
                pdf.cell(60, 8, f" {to_br_currency(q * v)}", border=1, ln=True, align="R")
            else:
                pdf.cell(160, 8, f" {nome}", border=1)
                pdf.cell(30, 8, f" {int(q)}", border=1, ln=True, align="C")

    # 2. Serviços
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, " 2. ORÇAMENTO DO SERVIÇO", border=1, ln=True, fill=True)
    pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 6, f"Descrição: {desc_serv}", border=1)
    if val_serv > 0:
        pdf.cell(130, 8, "Valor do Serviço:", border=1)
        pdf.cell(60, 8, f" {to_br_currency(val_serv)}", border=1, ln=True, align="R")

    # 3. Outros
    if val_outros > 0 or desc_outros.strip() != "":
        pdf.ln(5)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, " 3. OUTROS SERVIÇOS / PRODUTOS", border=1, ln=True, fill=True)
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(0, 6, f"Descrição: {desc_outros}", border=1)
        if val_outros > 0:
            pdf.cell(130, 8, "Valor Adicional:", border=1)
            pdf.cell(60, 8, f" {to_br_currency(val_outros)}", border=1, ln=True, align="R")

    # Total Geral
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_fill_color(0, 68, 136)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 10, " INVESTIMENTO TOTAL", border=1, fill=True)
    pdf.cell(60, 10, f" {to_br_currency(total)}", border=1, ln=True, align="R", fill=True)
    
    # Observações
    pdf.ln(10)
    pdf.set_text_color(200, 0, 0)
    pdf.set_font("helvetica", "B", 10)
    pdf.multi_cell(0, 6, f"OBSERVAÇÕES IMPORTANTES:\n{obs}", border=0)

    # Nova forma blindada de retornar o PDF na fpdf2
    return bytes(pdf.output())

# ==========================================
# 6. TELAS E MÓDULOS
# ==========================================
def tela_inicial():
    st.markdown("## Página Inicial")
    st.write("Bem-vindo ao sistema de gestão, Breno. Selecione uma opção abaixo:")
    st.write("---")
    col1, col2 = st.columns(2); col3, col4 = st.columns(2)
    with col1:
        if st.button("📝\n\nFazer Orçamento", use_container_width=True): 
            st.session_state.pagina_atual = "Orçamentos"; st.rerun()
    with col2:
        if st.button("📊\n\nControle Financeiro", use_container_width=True):
            st.session_state.pagina_atual = "Controle Financeiro"; st.rerun()
    with col3:
        if st.button("🏠\n\nAirbnb", use_container_width=True): st.info("Módulo em desenvolvimento.")
    with col4:
        if st.button("🛠️\n\nServiços Ecoclim", use_container_width=True): st.info("Módulo em desenvolvimento.")

def tela_orcamentos():
    st.markdown("## 📝 Novo Orçamento Ecoclim")
    st.write("Preencha os dados abaixo para gerar a proposta comercial.")
    
    # DADOS DO CLIENTE
    with st.container(border=True):
        st.subheader("👤 1. Dados do Cliente")
        col1, col2 = st.columns(2)
        cliente = col1.text_input("Nome do Cliente", placeholder="Ex: João da Silva")
        telefone = col2.text_input("Telefone / WhatsApp", placeholder="(00) 00000-0000")
        produtos_lista = ["AQUECEDOR SOLAR TRADICIONAL", "AQUECEDOR SOLAR A VÁCUO ACOPLADO", "AQUECEDOR SOLAR MODULAR", "AQUECEDOR DE PISCINA - TRADICIONAL", "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", "SISTEMAS DE PRESSURIZAÇÃO"]
        produto_selecionado = st.selectbox("Selecione a Imagem do Produto para a Capa", produtos_lista)

    # EQUIPAMENTOS
    with st.container(border=True):
        col_eq1, col_eq2 = st.columns([3, 1])
        with col_eq1: st.subheader("⚙️ 2. Descrição de Equipamentos")
        with col_eq2: mostrar_pdf = st.checkbox("Mostrar R$ no PDF?", value=True, help="Se desmarcado, o cliente verá os itens mas não os preços individuais.")
        
        opcoes_db_produtos = [""] + list(db_produtos.keys()) + ["OUTRO (Digitar)"]
        
        # Inicia a tabela com 5 linhas em branco
        if 'df_equip' not in st.session_state:
            st.session_state.df_equip = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Quantidade": 1, "Valor Un.": 0.0} for _ in range(5)])
        
        # Configuração das colunas
        config_colunas = {
            "Produto da Base": st.column_config.SelectboxColumn("Selecionar Produto (Base)", options=opcoes_db_produtos, width="medium"),
            "Produto Manual": st.column_config.TextColumn("Se 'OUTRO', digite aqui:", width="medium"),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=1, step=1, width="small"),
            "Valor Un.": st.column_config.NumberColumn("Valor Un. (R$)", format="R$ %.2f", width="small")
        }

        # A mágica do autopreenchimento
        df_equip_edit = st.data_editor(st.session_state.df_equip, column_config=config_colunas, num_rows="dynamic", use_container_width=True)
        
        # Lógica para puxar o valor do BD automaticamente
        mudou_algo = False
        for i in range(len(df_equip_edit)):
            prod_selecionado = df_equip_edit.at[i, 'Produto da Base']
            valor_atual = df_equip_edit.at[i, 'Valor Un.']
            # Se o usuário escolheu algo da base e o valor está zerado, puxa da base!
            if prod_selecionado in db_produtos and valor_atual == 0.0:
                df_equip_edit.at[i, 'Valor Un.'] = db_produtos[prod_selecionado]
                mudou_algo = True

        if mudou_algo:
            st.session_state.df_equip = df_equip_edit
            st.rerun()
        else:
            st.session_state.df_equip = df_equip_edit

        # Calcula Subtotal
        total_equip = sum([float(r['Quantidade']) * float(r['Valor Un.']) for _, r in df_equip_edit.iterrows() if r['Produto da Base'] != ""])
        st.markdown(f"**Subtotal Equipamentos:** {to_br_currency(total_equip)}")

    # SERVIÇOS
    with st.container(border=True):
        st.subheader("🛠️ 3. Orçamento do Serviço")
        opcoes_db_serv = ["Selecione da Base..."] + list(db_servicos.keys()) + ["Outro (Digitar manualmente)"]
        servico_selecionado = st.selectbox("Selecione um serviço cadastrado ou digite:", opcoes_db_serv)
        
        if servico_selecionado == "Outro (Digitar manualmente)":
            desc_servico = st.text_area("Descreva o serviço:")
            valor_servico = st.number_input("Valor do Serviço (R$)", min_value=0.0, step=100.0, format="%.2f")
        elif servico_selecionado != "Selecione da Base...":
            desc_servico = st.text_area("Descreva o serviço:", value=servico_selecionado)
            valor_servico = st.number_input("Valor do Serviço (R$)", value=db_servicos[servico_selecionado], min_value=0.0, step=100.0, format="%.2f")
        else:
            desc_servico = ""; valor_servico = 0.0

    # OUTROS SERVIÇOS/PRODUTOS
    with st.container(border=True):
        st.subheader("➕ 4. Outros Serviços / Produtos (Terceirizados)")
        opcoes_db_outros = ["Selecione da Base..."] + list(db_outros.keys()) + ["Outro (Digitar manualmente)"]
        outros_selecionado = st.selectbox("Selecione um item extra cadastrado ou digite:", opcoes_db_outros)
        
        if outros_selecionado == "Outro (Digitar manualmente)":
            desc_outros = st.text_area("Descreva materiais ou serviços extras:")
            valor_outros = st.number_input("Valor Adicional (R$)", min_value=0.0, step=100.0, format="%.2f")
        elif outros_selecionado != "Selecione da Base...":
            desc_outros = st.text_area("Descreva materiais ou serviços extras:", value=outros_selecionado)
            valor_outros = st.number_input("Valor Adicional (R$)", value=db_outros[outros_selecionado], min_value=0.0, step=100.0, format="%.2f")
        else:
            desc_outros = ""; valor_outros = 0.0

    # OBSERVAÇÕES E TOTAL
    with st.container(border=True):
        total_geral = total_equip + valor_servico + valor_outros
        st.markdown(f"<h3 style='color: #004488;'>💰 INVESTIMENTO TOTAL: {to_br_currency(total_geral)}</h3>", unsafe_allow_html=True)
        obs_padrao = "Material Hidráulico não inclusos na proposta\nValores válidos para pagamento conforme negociação."
        observacoes = st.text_area("Observações (Aparecerá em VERMELHO no PDF):", value=obs_padrao, height=100)
    
    # BOTÕES
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🚀 SALVAR E GERAR PDF", use_container_width=True, type="primary"):
            if cliente == "": st.warning("Preencha o nome do cliente!")
            else:
                # Salva no BD (Com Try/Except silencioso para não assustar se a tabela não existir)
                try:
                    data_db = {"nome": cliente, "telefone": telefone, "produto_ref": produto_selecionado, "valor_total": total_geral, "status": "Em fase de orçamento", "data_entrada": datetime.datetime.now().strftime("%Y-%m-%d")}
                    supabase.table("clientes_orcamentos").insert(data_db).execute()
                    st.success("✅ Cliente salvo no sistema como 'Em fase de orçamento'!")
                except Exception as e:
                    st.toast("⚠️ Tabela 'clientes_orcamentos' não encontrada no banco. O PDF será gerado, mas os dados não foram salvos na nuvem.", icon="⚠️")
                
                # Gera o PDF
                pdf_bytes = gerar_pdf_orcamento(cliente, telefone, produto_selecionado, df_equip_edit, desc_servico, valor_servico, desc_outros, valor_outros, total_geral, observacoes, mostrar_pdf)
                
                st.download_button(label="📥 BAIXAR PDF DO ORÇAMENTO", data=pdf_bytes, file_name=f"Orcamento_{cliente.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True)

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
    
    # [O Bloco do Patrimônio e Entradas segue inalterado da versão anterior...]
    df_p_display = st.session_state.df_p[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_p_display[m] = df_p_display[m].apply(lambda x: to_br_currency(x).replace(",00", ""))
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
    styled_res_p = df_res_p[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "PATRIMÔNIO TOTAL" else "#FFF2CC" if "LÍQUIDO" in row["MESES"] else "white"}; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_p.format(lambda x: to_br_currency(x).replace(",00","") if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=175)

    df_e_display = st.session_state.df_e[colunas_visiveis].copy()
    for m in [c for c in colunas_visiveis if c != "MESES"]: df_e_display[m] = df_e_display[m].apply(lambda x: to_br_currency(x).replace(",00", ""))
    styled_df_e = df_e_display.style.set_properties(subset=[mes_atual_nome] if mes_atual_nome in colunas_visiveis and ano_selecionado == ano_atual else [], **{'background-color': '#e0f0ff', 'font-weight': 'bold'})
    df_e_edit_str = st.data_editor(styled_df_e, hide_index=True, column_config=col_cfg, use_container_width=True, height=190)

    if not df_e_edit_str.equals(df_e_display):
        for m in [c for c in colunas_visiveis if c != "MESES"]: st.session_state.df_e.loc[:, m] = df_e_edit_str[m].apply(parse_br_currency)
        save_to_supabase('entradas', st.session_state.df_e, ano_selecionado); st.toast("💾 Salvo!", icon="✅"); st.rerun()

    df_e_n = st.session_state.df_e.set_index('MESES'); tot_ent = df_e_n.sum()
    df_res_e = pd.DataFrame({'MESES': ['TOTAL RECEBIMENTOS:']})
    for m in meses_pt: df_res_e[m] = [tot_ent[m]]
    styled_res_e = df_res_e[colunas_visiveis].style.apply(lambda row: [f'background-color: #9BC2E6; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_res_e.format(lambda x: to_br_currency(x).replace(",00","") if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=75)

    st.markdown("#### 📈 Rendimento Mensal (Investimentos)")
    xp_val = df_n.loc['INVESTIMENTO XP']; inter_val = df_n.loc['CONTA INTER']
    xp_var = xp_val.diff().fillna(0); inter_var = inter_val.diff().fillna(0); rend_total = xp_var + inter_var; prev_bal = (xp_val + inter_val).shift(1).fillna(0)
    df_rend = pd.DataFrame({'MESES': ['VARIAÇÃO INVESTIMENTO XP', 'VARIAÇÃO CONTA INTER', 'RENDIMENTO TOTAL', '% RETORNO MÊS', 'SALÁRIO + RENDIMENTO MÊS']})
    for i, m in enumerate(meses_pt):
        if (ano_selecionado > ano_atual) or (ano_selecionado == ano_atual and i > mes_hoje_idx - 1): df_rend[m] = [0, 0, 0, "0,00%", 0]
        else:
            rt = rend_total[m]; pb = prev_bal[m]; pct_val = (rt / pb * 100) if pb > 0 else 0
            df_rend[m] = [xp_var[m], inter_var[m], rt, f"{pct_val:.2f}%".replace(".", ","), tot_ent[m] + rt]
    styled_rend = df_rend[colunas_visiveis].style.apply(lambda row: [f'background-color: {"#FF9900" if row["MESES"] == "RENDIMENTO TOTAL" else "#FFF2CC" if "%" in row["MESES"] else "#9BC2E6" if "SALÁRIO" in row["MESES"] else "white"}; font-weight: bold; border-left: {"3px solid #4A90E2" if col == mes_atual_nome and ano_selecionado == ano_atual else "none"}' for col in colunas_visiveis], axis=1)
    st.dataframe(styled_rend.format(lambda x: to_br_currency(x).replace(",00","") if isinstance(x, (int, float, np.integer, np.floating)) else x), hide_index=True, column_config=col_cfg, use_container_width=True, height=215)
    st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    meses_calculo = meses_pt if ano_selecionado < ano_atual else meses_pt[:mes_hoje_idx]
    media_entradas = tot_ent[meses_calculo].mean(); media_rend_r = rend_total[meses_calculo].mean(); media_rend_p = (rend_total[meses_calculo] / prev_bal[meses_calculo].replace(0, np.nan)).mean() * 100
    idx_ref = 11 if ano_selecionado < ano_atual else (mes_hoje_idx - 1 if mes_hoje_idx > 0 else 0)

    c1.metric("💰 MÉDIA ENTRADAS FIXAS", to_br_currency(media_entradas))
    c2.metric("🎯 LIMITE DE GASTO (MÉDIA REND.)", to_br_currency(media_rend_r))
    c3.metric("📈 MÉDIA RETORNO (%)", f"{media_rend_p:.2f}%".replace(".", ","))
    c4.metric("🏛️ PATRIMÔNIO ATUAL", to_br_currency(pat_tot.iloc[idx_ref]))

    st.write("---")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Aumento de Patrimônio Total"); st.line_chart(pat_tot[meses_pt])
        st.subheader("Rendimento Mensal (R$)"); st.bar_chart(rend_total[meses_pt])
    with g2:
        st.subheader("Salário + Rendimento Mensal"); st.area_chart(tot_ent[meses_pt] + rend_total[meses_pt])
        st.subheader("Faturamento Ecoclim"); st.line_chart(df_e_n.loc['ECOCLIM'][meses_pt])

# ==========================================
# 7. EXECUÇÃO PRINCIPAL
# ==========================================
if not st.session_state.authenticated:
    login_screen()
else:
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
        st.write("### Menu Principal")
        opcoes_menu = ["Página Inicial", "Orçamentos", "Controle Financeiro"]
        idx_menu = opcoes_menu.index(st.session_state.pagina_atual) if st.session_state.pagina_atual in opcoes_menu else 0
        escolha = st.radio("Navegação:", opcoes_menu, index=idx_menu)
        
        if escolha != st.session_state.pagina_atual:
            st.session_state.pagina_atual = escolha; st.rerun()
            
        st.write("---")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.authenticated = False; st.rerun()

    if st.session_state.pagina_atual == "Página Inicial": tela_inicial()
    elif st.session_state.pagina_atual == "Orçamentos": tela_orcamentos()
    elif st.session_state.pagina_atual == "Controle Financeiro": tela_financeira()
