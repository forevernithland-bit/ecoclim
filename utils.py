import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# ==========================================
# VARIÁVEIS GLOBAIS DE DATA
# ==========================================
hoje = datetime.date.today()
ano_atual = hoje.year
meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
mes_hoje_idx = hoje.month
mes_atual_nome = meses_pt[mes_hoje_idx - 1]

def init_connection():
    from supabase import create_client
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ==========================================
# FUNÇÕES FINANCEIRAS
# ==========================================
def load_year_data(nome_tabela, contas_padrao, ano):
    supabase = st.session_state.supabase
    try:
        res = supabase.table(nome_tabela).select("*").eq("ano", ano).execute()
        df_banco = pd.DataFrame(res.data)
        
        if df_banco.empty:
            df_novo = pd.DataFrame({"MESES": contas_padrao})
            for mes in meses_pt: df_novo[mes] = 0.0
            return df_novo
        
        df_banco.columns = df_banco.columns.str.upper()
        colunas_ordenadas = ["MESES"] + meses_pt
        for col in colunas_ordenadas:
            if col not in df_banco.columns: df_banco[col] = 0.0 if col != "MESES" else ""
        return df_banco[colunas_ordenadas]
    except:
        return pd.DataFrame({"MESES": contas_padrao, **{m: 0.0 for m in meses_pt}})

def save_to_supabase(nome_tabela, df, ano):
    supabase = st.session_state.supabase
    dados_finais = []
    for _, linha in df.iterrows():
        registro = {"ano": ano, "MESES": linha["MESES"]}
        for mes_coluna in meses_pt: registro[mes_coluna] = float(linha[mes_coluna]) if pd.notna(linha[mes_coluna]) else 0.0
        dados_finais.append(registro)
    try:
        supabase.table(nome_tabela).delete().eq("ano", ano).execute()
        supabase.table(nome_tabela).insert(dados_finais).execute()
    except Exception as e: st.error(f"Erro ao salvar: {e}")

# ==========================================
# CATÁLOGOS E UTILITÁRIOS
# ==========================================
def load_catalog(nome_tabela):
    supabase = st.session_state.supabase
    colunas_corretas = ["Item", "Descrição", "Custo (R$)", "Margem (%)", "Lucro (R$)", "Venda (R$)"]
    try:
        res = supabase.table(nome_tabela).select("*").order("item").execute()
        df = pd.DataFrame(res.data)
        mapeamento = {"item": "Item", "descricao": "Descrição", "custo": "Custo (R$)", "margem": "Margem (%)", "lucro": "Lucro (R$)", "venda": "Venda (R$)"}
        
        if df.empty: return pd.DataFrame(columns=colunas_corretas)
        df = df.rename(columns={k: v for k, v in mapeamento.items() if k in df.columns})
        
        for coluna in colunas_corretas:
            if coluna not in df.columns:
                df[coluna] = "" if "Desc" in coluna or "Item" in coluna else 0.0
        return df[colunas_corretas]
    except:
        return pd.DataFrame(columns=colunas_corretas)

def save_catalog(nome_tabela, df):
    supabase = st.session_state.supabase
    lista_dados = []
    for _, linha in df.iterrows():
        if linha.get('Item') and str(linha['Item']).strip() != "":
            lista_dados.append({
                "item": linha['Item'],
                "descricao": str(linha.get('Descrição', '')),
                "custo": float(linha.get('Custo (R$)', 0.0)),
                "margem": float(linha.get('Margem (%)', 0.0)),
                "lucro": float(linha.get('Lucro (R$)', 0.0)),
                "venda": float(linha.get('Venda (R$)', 0.0))
            })
    try:
        supabase.table(nome_tabela).delete().neq("item", "___VAZIO___").execute()
        if lista_dados: supabase.table(nome_tabela).insert(lista_dados).execute()
    except Exception as e: st.error(f"Erro ao salvar catálogo: {e}")

def to_br_currency(valor, incluir_simbolo=True):
    try: valor_float = float(valor)
    except: valor_float = 0.0
    res = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {res}" if incluir_simbolo else res

def parse_br_currency(texto_valor):
    if isinstance(texto_valor, (int, float)): return float(texto_valor)
    s = str(texto_valor).replace("R$", "").strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def load_taxas():
    try:
        res = st.session_state.supabase.table('catalogo_taxas').select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame(columns=["Item", "Taxa (%)"])
        return df.rename(columns={"item": "Item", "taxa_percentual": "Taxa (%)"})
    except: return pd.DataFrame(columns=["Item", "Taxa (%)"])

def save_taxas(df):
    dados = [{"item": r['Item'], "taxa_percentual": float(r.get('Taxa (%)', 0.0))} for _, r in df.iterrows() if r.get('Item')]
    st.session_state.supabase.table('catalogo_taxas').delete().neq("item", "___").execute()
    if dados: st.session_state.supabase.table('catalogo_taxas').insert(dados).execute()

# ==========================================
# GERAÇÃO DE PDF
# ==========================================
def gerar_pdf_orcamento(nome, tel, capa, df_items, d_s, v_s, d_o, v_o, total, obs, mostrar_un):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    
    # Cabeçalho e Logos
    try: p.drawImage("logo.png", 2*cm, altura - 3.5*cm, width=4*cm, preserveAspectRatio=True, mask='auto')
    except: p.setFont("Helvetica-Bold", 16); p.drawString(2*cm, altura - 2.5*cm, "ECOCLIM")
    
    p.setFont("Helvetica-Bold", 14); p.drawString(largura - 9*cm, altura - 1.5*cm, "PROPOSTA COMERCIAL")
    p.setFont("Helvetica", 8); p.setFillColor(colors.grey)
    p.drawString(largura - 9*cm, altura - 2.1*cm, "WWW.ECOCLIM.COM.BR"); p.drawString(largura - 9*cm, altura - 2.5*cm, "COMERCIAL@ECOCLIM.COM.BR")
    
    # Datas e Validade
    p.setFillColor(colors.black); p.setFont("Helvetica", 9)
    p.drawString(largura - 9*cm, altura - 3.5*cm, f"Data: {datetime.date.today().strftime('%d/%m/%Y')}")
    p.drawString(largura - 9*cm, altura - 4.0*cm, "Validade da Proposta: 15 dias")
    
    # Dados do Cliente
    y = altura - 5.5*cm
    p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 1.5*cm, largura - 4*cm, 2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 10); p.drawString(2.3*cm, y, "DADOS DO CLIENTE")
    p.setFont("Helvetica", 10); p.drawString(2.3*cm, y - 0.5*cm, f"Nome: {nome}"); p.drawString(2.3*cm, y - 1*cm, f"WhatsApp: {tel}")
    
    # Imagem de Capa
    y -= 2.2*cm
    img_map = {
        "Aquecedor Solar Tradicional": "aquecedor_tradicional.jpg",
        "Aquecedor Solar a Vácuo Acoplado": "vacuo_acoplado.jpg",
        "Aquecedor Solar Modular": "modular.jpg",
        "Aquecedor de Piscina - Tradicional": "piscina_tradicional.jpg",
        "Aquecedor de Piscina - Trocador de Calor": "piscina_trocador.jpg",
        "Sistema de Pressurização": "pressurizacao.jpg"
    }
    
    try: 
        p.drawImage(img_map.get(capa, ""), 2*cm, y - 5.5*cm, width=largura-4*cm, height=5.5*cm, preserveAspectRatio=True)
    except: 
        pass
    
    # 1. Equipamentos
    y -= 6.5*cm
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "1. EQUIPAMENTOS")
    y -= 0.6*cm; p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 9)
    p.drawString(2.3*cm, y - 0.3*cm, "Item"); p.drawString(12.5*cm, y - 0.3*cm, "Qtd"); p.drawRightString(largura - 2.3*cm, y - 0.3*cm, "Subtotal")
    y -= 0.8*cm
    
    for _, row in df_items.iterrows():
        if row['Quantidade'] > 0:
            item = row['Produto da Base'] if row['Produto da Base'] != "OUTRO" else row['Produto Manual']
            p.setFont("Helvetica-Bold", 9); p.drawString(2.3*cm, y, str(item)[:60])
            p.setFont("Helvetica", 9); p.drawString(12.8*cm, y, str(int(row['Quantidade'])))
            p.drawRightString(largura - 2.3*cm, y, to_br_currency(row.get('Venda Total', 0)))
            y -= 0.4*cm
            desc = str(row.get('Descrição', ""))
            if desc and desc != "nan":
                p.setFont("Helvetica", 8); p.setFillColor(colors.grey)
                for l in desc.split('\n'): p.drawString(2.3*cm, y, l.strip()); y -= 0.35*cm
                p.setFillColor(colors.black)
            y -= 0.2*cm
            
    # 2. Serviços
    y -= 1.0*cm 
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "2. SERVIÇOS")
    y -= 0.8*cm; p.setFillColor(colors.black); p.setFont("Helvetica", 10)
    
    if d_s:
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_s))
        for l in d_s.split('\n'): p.drawString(2.3*cm, y, l); y -= 0.45*cm
    else:
        p.drawString(2.3*cm, y, "Nenhum serviço selecionado."); y -= 0.45*cm
        
    # 3. Outros / Terceiros
    y -= 0.5*cm 
    p.setFillColor(colors.HexColor("#004488")); p.rect(2*cm, y, largura - 4*cm, 0.7*cm, fill=1, stroke=0)
    p.setFillColor(colors.white); p.setFont("Helvetica-Bold", 11); p.drawString(2.3*cm, y + 0.2*cm, "3. OUTROS / TERCEIROS")
    y -= 0.8*cm; p.setFillColor(colors.black); p.setFont("Helvetica", 10)
    
    if d_o:
        p.drawRightString(largura - 2.3*cm, y, to_br_currency(v_o))
        for l in d_o.split('\n'): p.drawString(2.3*cm, y, l); y -= 0.45*cm
    else:
        p.drawString(2.3*cm, y, "Nenhum item adicional selecionado."); y -= 0.45*cm
        
    # Total
    y -= 1.0*cm; p.setFillColor(colors.HexColor("#f0f0f0")); p.rect(2*cm, y - 0.2*cm, largura - 4*cm, 1.2*cm, fill=1, stroke=0)
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold", 12); p.drawString(2.3*cm, y + 0.2*cm, "INVESTIMENTO TOTAL"); p.drawRightString(largura - 2.3*cm, y + 0.2*cm, to_br_currency(total))
    
    # Observações
    y -= 1.8*cm; p.setFillColor(colors.red); p.setFont("Helvetica-Bold", 10); p.drawString(2*cm, y, "OBSERVAÇÕES:"); p.setFont("Helvetica", 9); p.setFillColor(colors.black); p.drawString(2*cm, y - 0.5*cm, str(obs)[:100])
    
    p.save()
    buffer.seek(0)
    return buffer
# ==========================================
# BUSCA DE CEP AUTOMÁTICA
# ==========================================
import urllib.request
import json

def buscar_cep(cep):
    """Busca o endereço na API pública do ViaCEP"""
    cep = str(cep).replace('-', '').replace('.', '').strip()
    if len(cep) != 8:
        return None
    try:
        url = f"https://viacep.com.br/ws/{cep}/json/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            dados = json.loads(response.read().decode('utf-8'))
            if "erro" not in dados:
                return dados
    except:
        pass
    return None
