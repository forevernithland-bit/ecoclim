from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import datetime
import requests
import utils
import orcamento_personalizado
import base64

# Inicia a API
app = FastAPI(title="Ecoclim API - V2", description="API para integração com n8n, ERP e envio automático de PDF via Evolution API")

# Libera o PWA (GitHub Pages) a chamar esta API pelo navegador — sem isso o
# navegador bloqueia a chamada (CORS), mesmo com HTTPS dos dois lados.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://forevernithland-bit.github.io"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conecta no seu Supabase
supabase = utils.init_connection()

# CONFIGURAÇÕES CRÍTICAS DA EVOLUTION API
EVOLUTION_BASE_URL = "http://187.127.21.127:8080"
EVOLUTION_API_KEY = "E76FE78F42C9-411F-A6E5-EE8432420A65"
INSTANCE_NAME = "ERP"

# ==========================================
# ESTRUTURA DOS DADOS QUE O ROBÔ VAI MANDAR (MANUAL)
# ==========================================
class ItemOrcamento(BaseModel):
    produto: str
    quantidade: int
    preco_unidade: float
    descricao: Optional[str] = ""

class OrcamentoRequest(BaseModel):
    nome_cliente: str
    telefone: Optional[str] = ""  # Agora é opcional!
    itens: List[ItemOrcamento]
    com_instalacao: bool
    valor_instalacao: float = 0.0
    descricao_instalacao: Optional[str] = ""
    observacoes: Optional[str] = "Material hidráulico não incluso nesta proposta."

# ==========================================
# ESTRUTURA PARA O NOVO ORÇAMENTO VIA IA (KITS INTELIGENTES)
# ==========================================
class OrcamentoKitRequest(BaseModel):
    nome_cliente: str
    telefone: Optional[str] = ""  # Agora é opcional!
    nome_do_kit: str
    com_instalacao: bool
    observacoes: Optional[str] = "Material hidráulico não incluso nesta proposta."

# ==========================================
# FUNÇÃO AUXILIAR PARA DISPARAR O PDF VIA WHATSAPP (AGORA COM BASE64)
# ==========================================
def enviar_pdf_via_whatsapp(telefone_cliente: str, b64_pdf: str, nome_arquivo: str, nome_cliente: str):
    # Se o telefone vier do n8n com o formato nativo do WhatsApp (@lid ou @s.whatsapp.net), usa a string exata.
    if "@" in telefone_cliente:
        numero_final = telefone_cliente
    else:
        # Limpa o número de telefone para garantir o formato correto (testes manuais)
        numero_final = "".join(filter(str.isdigit, telefone_cliente))
        if not numero_final.startswith("55") and len(numero_final) > 0:
            numero_final = f"55{numero_final}"
            
    endpoint = f"{EVOLUTION_BASE_URL}/message/sendMedia/{INSTANCE_NAME}"
    
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Payload configurado para enviar documento via base64 direto da memória
    payload = {
        "number": numero_final,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "media": b64_pdf,
        "fileName": nome_arquivo,
        "caption": f"Olá, {nome_cliente}! Conforme conversamos, segue em anexo a sua proposta comercial detalhada da Ecoclim. Qualquer dúvida estou à disposição!",
        "options": {
            "delay": 1200,
            "presence": "composing"
        }
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        return response.status_code in [200, 201], response.json()
    except Exception as e:
        return False, str(e)

# ==========================================
# ROTA ORIGINAL: GERAÇÃO E ENVIO DE ORÇAMENTO MANUAL
# ==========================================
@app.post("/gerar-orcamento")
async def criar_orcamento_bot(req: OrcamentoRequest):
    try:
        linhas_pdf = []
        total_equipamentos = 0.0
        
        for item in req.itens:
            v_tot = item.quantidade * item.preco_unidade
            total_equipamentos += v_tot
            
            linhas_pdf.append({
                "Produto da Base": item.produto,
                "Produto Manual": "",
                "Descrição": item.descricao,
                "Quantidade": item.quantidade,
                "Custo (R$)": 0.0,
                "Venda (R$)": item.preco_unidade,
                "Custo Total": 0.0,
                "Venda Total": v_tot
            })
            
        df_itens = pd.DataFrame(linhas_pdf)
        
        val_serv = req.valor_instalacao if req.com_instalacao else 0.0
        desc_serv = req.descricao_instalacao if req.com_instalacao else ""
        total_geral = total_equipamentos + val_serv
        
        pdf_buffer = utils.gerar_pdf_orcamento(
            nome=req.nome_cliente,
            tel=req.telefone if req.telefone else "Não informado",
            capa="Aquecedor Solar Tradicional", 
            df_items=df_itens,
            d_s=desc_serv,
            v_s=val_serv,
            d_o="",
            v_o=0.0,
            total=total_geral,
            obs=req.observacoes,
            mostrar_un=True
        )
        
        string_data = datetime.datetime.now().strftime('%y%m%d-%H%M%S')
        numero_orc = f"ORC-BOT-{string_data}"
        
        snapshot_itens = []
        for item in req.itens:
            snapshot_itens.append({
                "Item": item.produto,
                "Qtd": item.quantidade,
                "Venda Un.": item.preco_unidade,
                "Descrição": item.descricao
            })
            
        payload = {
            "numero_orcamento": numero_orc,
            "nome_cliente": req.nome_cliente,
            "telefone_cliente": req.telefone if req.telefone else "",
            "valor_venda_total": total_geral,
            "status_projeto": "Orçamento Enviado",
            "detalhamento_itens": snapshot_itens,
            "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
            "notas_internas": "Gerado automaticamente via Bot WhatsApp"
        }
        
        supabase.table("servicos_andamento").insert(payload).execute()
        
        mes_atual = utils.mes_atual_nome
        nome_arquivo = f"ORC_{req.nome_cliente.replace(' ', '_')}_{string_data}.pdf"
        
        # Salva no Drive apenas para backup
        sucesso_drive, drive_id_ou_erro = utils.upload_to_drive(
            file_buffer=pdf_buffer,
            filename=nome_arquivo,
            mimetype="application/pdf",
            folder_path=["Orçamentos", mes_atual]
        )
        
        if not sucesso_drive:
            return {"sucesso": False, "erro": f"Erro ao salvar no Drive: {drive_id_ou_erro}"}

        link_drive = f"https://drive.google.com/uc?export=download&id={drive_id_ou_erro}"
        
        # Converte o buffer do PDF direto para Base64 para envio via API
        pdf_b64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        
        sucesso_whatsapp = False
        retorno_whatsapp = "Não enviado (telefone não informado na requisição)"
        mensagem_final = "Orçamento gerado e salvo no ERP com sucesso!"
        
        if req.telefone and req.telefone.strip():
            sucesso_whatsapp, retorno_whatsapp = enviar_pdf_via_whatsapp(
                telefone_cliente=req.telefone,
                b64_pdf=pdf_b64,
                nome_arquivo=nome_arquivo,
                nome_cliente=req.nome_cliente
            )
            mensagem_final = "Orçamento gerado, registrado no ERP e enviado ao WhatsApp do cliente!"
        
        return {
            "sucesso": True,
            "mensagem": mensagem_final,
            "link_pdf_download": link_drive,
            "numero_orcamento": numero_orc,
            "valor_total_reais": total_geral,
            "whatsapp_enviado": sucesso_whatsapp,
            "detalhes_whatsapp": retorno_whatsapp
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# NOVA ROTA: GERAÇÃO DE ORÇAMENTO INTELIGENTE POR KIT (USADA PELO N8N)
# ==========================================
@app.post("/gerar-orcamento-kit")
async def gerar_orcamento_kit_bot(req: OrcamentoKitRequest):
    try:
        res_kit = supabase.table('config_kits_lote').select('*').eq('nome_kit', req.nome_do_kit).execute()
        
        if not res_kit.data:
            raise HTTPException(status_code=404, detail=f"O Kit '{req.nome_do_kit}' não foi encontrado na base de dados.")
            
        kit = res_kit.data[0]

        db_produtos = utils.load_catalog('catalogo_produtos')
        db_servicos = utils.load_catalog('catalogo_servicos')

        linhas_pdf = []
        total_equipamentos = 0.0
        snapshot_itens = []
        
        itens_do_kit = kit.get('itens', [])
        
        for ik in itens_do_kit:
            p_nome = str(ik.get('Produto', '')).strip()
            p_qtd = int(ik.get('Quantidade', 1))
            
            p_preco = 0.0
            p_desc = ""
            
            match_p = db_produtos[db_produtos['Item'].astype(str).str.strip().str.upper() == p_nome.upper()]
            if not match_p.empty:
                try: 
                    p_preco = float(match_p['Venda (R$)'].values[0])
                except: 
                    pass
                p_desc = str(match_p['Descrição'].values[0])
                if p_desc.lower() == 'nan': 
                    p_desc = ""
                    
            subtotal_item = p_preco * p_qtd
            total_equipamentos += subtotal_item
            
            linhas_pdf.append({
                "Produto da Base": p_nome,
                "Produto Manual": "",
                "Descrição": p_desc,
                "Quantidade": p_qtd,
                "Custo (R$)": 0.0,
                "Venda (R$)": p_preco,
                "Custo Total": 0.0,
                "Venda Total": subtotal_item
            })
            
            snapshot_itens.append({
                "Item": p_nome,
                "Qtd": p_qtd,
                "Venda Un.": p_preco,
                "Descrição": p_desc
            })
            
        df_itens = pd.DataFrame(linhas_pdf)

        val_serv = 0.0
        desc_serv = ""
        
        if req.com_instalacao:
            servico_nome = str(kit.get('servico_base', '')).strip()
            if servico_nome:
                match_s = db_servicos[db_servicos['Item'].astype(str).str.strip().str.upper() == servico_nome.upper()]
                if not match_s.empty:
                    try: 
                        val_serv = float(match_s['Venda (R$)'].values[0])
                    except: 
                        pass
                    nome_real_serv = str(match_s['Item'].values[0])
                    desc_real_serv = str(match_s['Descrição'].values[0])
                    
                    desc_serv = f"{nome_real_serv}\n{desc_real_serv}"
                    if desc_serv.endswith('\nnan') or desc_serv.endswith('\n'): 
                        desc_serv = nome_real_serv

        total_geral = total_equipamentos + val_serv
        capa_modelo = str(kit.get('modelo_capa', 'Aquecedor Solar Tradicional'))

        pdf_buffer = utils.gerar_pdf_orcamento(
            nome=req.nome_cliente,
            tel=req.telefone if req.telefone else "Não informado",
            capa=capa_modelo,
            df_items=df_itens,
            d_s=desc_serv,
            v_s=val_serv,
            d_o="",
            v_o=0.0,
            total=total_geral,
            obs=req.observacoes,
            mostrar_un=True 
        )

        string_data = datetime.datetime.now().strftime('%y%m%d-%H%M%S')
        numero_orc = f"ORC-IA-{string_data}"
        
        payload_erp = {
            "numero_orcamento": numero_orc,
            "nome_cliente": req.nome_cliente,
            "telefone_cliente": req.telefone if req.telefone else "",
            "valor_venda_total": total_geral,
            "status_projeto": "Orçamento Enviado",
            "detalhamento_itens": snapshot_itens,
            "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
            "notas_internas": f"Gerado automaticamente pelo Agente IA. (Kit Utilizado: {req.nome_do_kit})"
        }
        
        supabase.table("servicos_andamento").insert(payload_erp).execute()

        mes_atual = utils.mes_atual_nome
        nome_arquivo = f"ORC_{req.nome_cliente.replace(' ', '_')}_{string_data}.pdf"
        
        # Salva no Drive apenas para backup
        sucesso_drive, drive_id_ou_erro = utils.upload_to_drive(
            file_buffer=pdf_buffer,
            filename=nome_arquivo,
            mimetype="application/pdf",
            folder_path=["Orçamentos", mes_atual]
        )
        
        if not sucesso_drive:
            return {"sucesso": False, "erro": f"Erro ao salvar no Drive: {drive_id_ou_erro}"}

        link_drive = f"https://drive.google.com/uc?export=download&id={drive_id_ou_erro}"
        
        # Converte o buffer do PDF direto para Base64 para envio via API
        pdf_b64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        
        sucesso_whatsapp = False
        retorno_whatsapp = "Não enviado (telefone não informado na requisição)"
        mensagem_final = f"Orçamento gerado pelo Kit '{req.nome_do_kit}' e salvo com sucesso!"
        
        if req.telefone and req.telefone.strip():
            sucesso_whatsapp, retorno_whatsapp = enviar_pdf_via_whatsapp(
                telefone_cliente=req.telefone,
                b64_pdf=pdf_b64,
                nome_arquivo=nome_arquivo,
                nome_cliente=req.nome_cliente
            )
            mensagem_final = f"Orçamento gerado pelo Kit '{req.nome_do_kit}' e enviado ao cliente!"
        
        return {
            "sucesso": True,
            "mensagem": mensagem_final,
            "numero_orcamento": numero_orc,
            "link_pdf_download": link_drive,
            "valor_total_reais": total_geral,
            "whatsapp_enviado": sucesso_whatsapp,
            "detalhes_whatsapp": retorno_whatsapp
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# ORÇAMENTO PERSONALIZADO (usado pelo PWA — aba Orçamentos do admin)
# ==========================================
# Estes 3 endpoints são chamados pelo app mobile (js/orcamentos.js). Em vez de
# reimplementar a lógica de negócio em JavaScript (que ficaria desatualizada
# toda vez que orcamento_personalizado.py mudasse), eles importam e chamam AS
# MESMAS funções Python que o ERP (Streamlit) usa — detecção de capa/serviço,
# nome de arquivo, e a geração do PDF em si (utils.gerar_pdf_orcamento). Assim
# qualquer alteração feita no ERP desktop se reflete automaticamente aqui,
# sem precisar tocar no PWA.
class ItemOrcamentoPersonalizado(BaseModel):
    nome: str
    descricao: Optional[str] = ""
    quantidade: float
    custo_unitario: float = 0.0
    venda_unitario: float = 0.0


def _df_itens_orcamento(itens: List[ItemOrcamentoPersonalizado]) -> pd.DataFrame:
    linhas = []
    for it in itens:
        venda_tot = it.quantidade * it.venda_unitario
        custo_tot = it.quantidade * it.custo_unitario
        linhas.append({
            "Produto da Base": it.nome, "Produto Manual": "",
            "Descrição": it.descricao or "", "Quantidade": it.quantidade,
            "Custo (R$)": it.custo_unitario, "Venda (R$)": it.venda_unitario,
            "Custo Total": custo_tot, "Venda Total": venda_tot,
        })
    return pd.DataFrame(linhas) if linhas else pd.DataFrame(
        columns=["Produto da Base", "Produto Manual", "Descrição", "Quantidade", "Custo (R$)", "Venda (R$)", "Custo Total", "Venda Total"])


class SugestaoRequest(BaseModel):
    itens: List[ItemOrcamentoPersonalizado]


@app.post("/orcamento-personalizado/sugestao")
async def orcamento_personalizado_sugestao(req: SugestaoRequest):
    """Mesma automação do ERP (Partes 1 e 2 de orcamento_personalizado.py):
    a partir dos equipamentos escolhidos, sugere o modelo de capa e o
    serviço de instalação correspondente do catálogo."""
    try:
        df = _df_itens_orcamento(req.itens)
        db_servicos = utils.load_catalog('catalogo_servicos')

        capa = orcamento_personalizado.detectar_capa_por_produtos(df)
        sugestao = orcamento_personalizado.sugerir_servico_por_produtos(df, db_servicos)

        servico_detalhe = None
        if sugestao and sugestao.get("item_catalogo"):
            linha = db_servicos.loc[db_servicos['Item'] == sugestao["item_catalogo"]]
            if not linha.empty:
                desc = linha['Descrição'].values[0]
                servico_detalhe = {
                    "nome": sugestao["item_catalogo"],
                    "descricao": str(desc) if pd.notna(desc) else "",
                    "valor": float(linha['Venda (R$)'].values[0]) if pd.notna(linha['Venda (R$)'].values[0]) else 0.0,
                }

        return {"capa_sugerida": capa, "sugestao": sugestao, "servico_detalhe": servico_detalhe}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GerarPdfOrcamentoRequest(BaseModel):
    nome_cliente: str
    telefone: Optional[str] = ""
    endereco: Optional[str] = ""
    modelo_capa: str = "Aquecedor Solar Tradicional"
    itens: List[ItemOrcamentoPersonalizado]
    descricao_servico: Optional[str] = ""
    valor_servico: float = 0.0
    descricao_outros: Optional[str] = ""
    valor_outros: float = 0.0
    observacoes: Optional[str] = "Material Hidráulico não incluído na proposta"
    mostrar_precos_unitarios: bool = False
    detalhar_itens_pdf: bool = False
    numero_orcamento: Optional[str] = None
    rascunho_id: Optional[int] = None


@app.post("/orcamento-personalizado/gerar-pdf")
async def orcamento_personalizado_gerar_pdf(req: GerarPdfOrcamentoRequest):
    """Gera o PDF EXATAMENTE como o ERP (mesma função utils.gerar_pdf_orcamento),
    salva uma cópia de backup no Drive (melhor esforço — não falha a chamada
    se o Drive não estiver acessível) e devolve o PDF em base64 pro celular
    baixar/compartilhar direto."""
    try:
        df_itens = _df_itens_orcamento(req.itens)
        subtotal_equip = float(df_itens['Venda Total'].sum()) if not df_itens.empty else 0.0
        total_investimento = subtotal_equip + req.valor_servico + req.valor_outros

        pdf_buffer = utils.gerar_pdf_orcamento(
            nome=req.nome_cliente, tel=req.telefone or "Não informado",
            capa=req.modelo_capa, df_items=df_itens,
            d_s=req.descricao_servico or "", v_s=req.valor_servico,
            d_o=req.descricao_outros or "", v_o=req.valor_outros,
            total=total_investimento, obs=req.observacoes,
            mostrar_un=req.mostrar_precos_unitarios, detalhar_itens=req.detalhar_itens_pdf,
        )

        numero_prop = req.numero_orcamento or datetime.datetime.now().strftime('%y%m%d-%H%M')
        nome_base = orcamento_personalizado.gerar_nome_arquivo_orcamento(numero_prop, req.nome_cliente, df_itens)
        nome_arquivo = f"{nome_base}.pdf"

        drive_link = None
        try:
            if utils.drive_nome_existe(utils.DRIVE_FOLDER_ORCAMENTOS, nome_arquivo):
                i = 2
                while utils.drive_nome_existe(utils.DRIVE_FOLDER_ORCAMENTOS, f"{nome_base}_v{i}.pdf"):
                    i += 1
                nome_arquivo = f"{nome_base}_v{i}.pdf"
            ok_drive, res_drive = utils.upload_to_drive_folder_id(pdf_buffer, nome_arquivo, "application/pdf", utils.DRIVE_FOLDER_ORCAMENTOS)
            if ok_drive:
                drive_link = f"https://drive.google.com/file/d/{res_drive}/view"
        except Exception:
            pass  # backup no Drive é melhor-esforço; o PDF já foi gerado e vai pro celular de qualquer jeito

        # Toda prévia já vira Rascunho automaticamente, agrupado no MESMO
        # cliente (por telefone/nome) — nunca duplica o cliente na lista só
        # por gerar mais de uma prévia/versão pra ele. Mesma função que o ERP
        # usa no botão "GERAR PRÉVIA".
        rascunho_id = req.rascunho_id
        try:
            rascunho_id = orcamento_personalizado.registrar_previa_como_rascunho(
                supabase, req.rascunho_id, req.nome_cliente, req.telefone or "", req.endereco or "",
                df_itens, req.descricao_servico or "", req.valor_servico, req.descricao_outros or "",
                req.valor_outros, req.observacoes, numero_prop, total_investimento,
                drive_link=drive_link, nome_arquivo=nome_arquivo,
            )
        except Exception:
            pass  # registrar o rascunho é melhor-esforço; o PDF já foi gerado e vai pro celular de qualquer jeito

        pdf_b64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        return {
            "sucesso": True, "pdf_base64": pdf_b64, "nome_arquivo": nome_arquivo,
            "numero_orcamento": numero_prop, "valor_total": total_investimento,
            "drive_link": drive_link, "rascunho_id": rascunho_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CalculoCustosRequest(BaseModel):
    venda_produtos: float
    custo_produtos: float
    venda_instalacao: float = 0.0
    custo_instalacao: float = 0.0
    venda_outros: float = 0.0
    custo_outros: float = 0.0
    emite_nf: bool = False
    forma_pagamento: str = "Nenhum / Dinheiro / PIX"
    comissao_pct: float = 0.0
    desconto_reais: float = 0.0


@app.post("/orcamento-personalizado/calculo-custos")
async def orcamento_personalizado_calculo_custos(req: CalculoCustosRequest):
    """Mesma matemática do modal 'Cálculo de Custos — Lucro Líquido' do ERP
    (orcamento_personalizado.py::_modal_calculo_custos), lendo as taxas
    cadastradas (catalogo_taxas) direto do Supabase em vez de session_state."""
    try:
        db_taxas = utils.load_taxas()
        taxa_nf = 6.0
        dict_taxas = {"Nenhum / Dinheiro / PIX": 0.0}
        for _, t in db_taxas.iterrows():
            nome = str(t.get('Item', '')).strip()
            up = nome.upper()
            try:
                val = float(t.get('Taxa (%)', 0.0))
            except Exception:
                val = 0.0
            if "NF" in up or "NOTA FISCAL" in up:
                taxa_nf = val
            elif nome:
                dict_taxas[nome] = val

        venda_bruta = req.venda_produtos + req.venda_instalacao + req.venda_outros
        venda_liquida = max(venda_bruta - req.desconto_reais, 0.0)
        taxa_cartao_pct = dict_taxas.get(req.forma_pagamento, 0.0)
        custo_nf = venda_liquida * (taxa_nf / 100.0) if req.emite_nf else 0.0
        custo_cartao = venda_liquida * (taxa_cartao_pct / 100.0)
        custo_comissao = venda_liquida * (req.comissao_pct / 100.0)
        custo_fixo = req.custo_produtos + req.custo_instalacao + req.custo_outros
        custo_variavel = custo_nf + custo_cartao + custo_comissao
        custo_total = custo_fixo + custo_variavel
        lucro_liquido = venda_liquida - custo_total
        margem = (lucro_liquido / venda_liquida * 100.0) if venda_liquida > 0 else 0.0

        return {
            "venda_bruta": venda_bruta, "venda_liquida": venda_liquida,
            "taxa_nf_pct": taxa_nf, "custo_nf": custo_nf,
            "taxa_cartao_pct": taxa_cartao_pct, "custo_cartao": custo_cartao,
            "custo_comissao": custo_comissao, "custo_fixo": custo_fixo,
            "custo_variavel": custo_variavel, "custo_total": custo_total,
            "lucro_liquido": lucro_liquido, "margem_pct": margem,
            "opcoes_pagamento": list(dict_taxas.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# PDF DE LISTA DE MATERIAIS (usado pelo PWA — aba Materiais do cliente, admin)
# ==========================================
# Mesma lógica do botão "Gerar PDF" do ERP (materiais_hid.py): uma função só
# (utils.gerar_pdf_lista_materiais) resolve o preço de venda no Supabase e
# monta o PDF, pra nunca desalinhar preço entre ERP e app.
class ItemListaMateriais(BaseModel):
    item: str
    qtd: float = 1.0
    venda_override: Optional[float] = None


class GerarPdfMateriaisRequest(BaseModel):
    nome_cliente: str
    telefone: Optional[str] = ""
    itens: List[ItemListaMateriais]
    observacoes: Optional[str] = "Lista de materiais para instalação."


@app.post("/materiais/gerar-pdf")
async def materiais_gerar_pdf(req: GerarPdfMateriaisRequest):
    try:
        pdf_buffer, total, itens_sem_preco = utils.gerar_pdf_lista_materiais(
            supabase, req.nome_cliente, req.telefone or "",
            [it.model_dump() for it in req.itens], req.observacoes,
        )
        pdf_b64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        nome_arquivo = f"materiais_{req.nome_cliente.replace(' ', '_')}.pdf"
        return {
            "sucesso": True, "pdf_base64": pdf_b64, "nome_arquivo": nome_arquivo,
            "valor_total": total, "itens_sem_preco": itens_sem_preco,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# NOTIFICAÇÕES PUSH (app do instalador — Android e iPhone)
# ==========================================
# O app registra o aparelho aqui uma vez (quando o usuário autoriza) e depois
# o ERP/API disparam avisos por estes endpoints. Ver push.py para o envio em si.
class PushSubscription(BaseModel):
    usuario: str
    perfil: Optional[str] = None
    instalador_vinculado: Optional[str] = None
    endpoint: str
    p256dh: str
    auth: str
    user_agent: Optional[str] = None


@app.post("/push/registrar")
async def push_registrar(req: PushSubscription):
    """Guarda (ou reativa) a assinatura deste aparelho.

    O endpoint é único por aparelho: se a pessoa reinstala o app ou troca de
    usuário no mesmo celular, o registro é atualizado em vez de duplicar —
    senão a mesma notificação chegaria várias vezes.
    """
    try:
        dados = req.model_dump()
        existente = supabase.table("push_subscriptions").select("id").eq(
            "endpoint", req.endpoint).execute().data
        if existente:
            supabase.table("push_subscriptions").update(
                {**dados, "ativo": True}).eq("endpoint", req.endpoint).execute()
        else:
            supabase.table("push_subscriptions").insert({**dados, "ativo": True}).execute()
        return {"sucesso": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/push/remover")
async def push_remover(endpoint: str):
    try:
        supabase.table("push_subscriptions").update({"ativo": False}).eq(
            "endpoint", endpoint).execute()
        return {"sucesso": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PushEnvio(BaseModel):
    titulo: str
    mensagem: str
    usuario: Optional[str] = None
    instalador: Optional[str] = None
    perfil: Optional[str] = None
    url: Optional[str] = "./index.html"
    tag: Optional[str] = None


@app.post("/push/enviar")
async def push_enviar(req: PushEnvio):
    """Dispara a notificação. Usado pelo app do instalador (quando ele conclui
    algo e o Breno precisa saber) e por qualquer automação futura."""
    try:
        import push
        enviadas, falhas = push.enviar(
            supabase, req.titulo, req.mensagem,
            usuario=req.usuario, instalador=req.instalador, perfil=req.perfil,
            url=req.url, tag=req.tag,
        )
        return {"sucesso": True, "enviadas": enviadas, "falhas": falhas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
