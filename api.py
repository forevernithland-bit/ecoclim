from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import datetime
import utils

# Inicia a API
app = FastAPI(title="Ecoclim API", description="API para integração com n8n e WhatsApp")

# Conecta no seu Supabase (usando a mesma função do seu ERP)
supabase = utils.init_connection()

# ==========================================
# ESTRUTURA DOS DADOS QUE O ROBÔ VAI MANDAR
# ==========================================
class ItemOrcamento(BaseModel):
    produto: str
    quantidade: int
    preco_unidade: float
    descricao: Optional[str] = ""

class OrcamentoRequest(BaseModel):
    nome_cliente: str
    telefone: str
    itens: List[ItemOrcamento]
    com_instalacao: bool
    valor_instalacao: float = 0.0
    descricao_instalacao: Optional[str] = ""
    observacoes: Optional[str] = "Material hidráulico não incluso nesta proposta."

# ==========================================
# ROTA DE GERAÇÃO DE ORÇAMENTO
# ==========================================
@app.post("/gerar-orcamento")
async def criar_orcamento_bot(req: OrcamentoRequest):
    try:
        # 1. Montar a tabela de itens para o PDF
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
                "Custo (R$)": 0.0,  # Oculto para o bot
                "Venda (R$)": item.preco_unidade,
                "Custo Total": 0.0,
                "Venda Total": v_tot
            })
            
        df_itens = pd.DataFrame(linhas_pdf)
        
        # 2. Configurar Serviços e Instalação
        val_serv = req.valor_instalacao if req.com_instalacao else 0.0
        desc_serv = req.descricao_instalacao if req.com_instalacao else ""
        total_geral = total_equipamentos + val_serv
        
        # 3. Gerar o arquivo PDF usando o seu utils.py
        pdf_buffer = utils.gerar_pdf_orcamento(
            nome=req.nome_cliente,
            tel=req.telefone,
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
        
        # 4. Salvar os dados no seu Supabase para aparecer no Painel do ERP
        string_data = datetime.datetime.now().strftime('%y%m%d-%H%M')
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
            "telefone_cliente": req.telefone,
            "valor_venda_total": total_geral,
            "status_projeto": "Orçamento Enviado",
            "detalhamento_itens": snapshot_itens,
            "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
            "notas_internas": "Gerado automaticamente via Bot WhatsApp" # Marcação no ERP
        }
        
        supabase.table("servicos_andamento").insert(payload).execute()
        
        # 5. Fazer upload do PDF para o Google Drive
        mes_atual = utils.mes_atual_nome
        nome_arquivo = f"ORC_{req.nome_cliente.replace(' ', '_')}_{string_data}.pdf"
        
        sucesso, drive_id_ou_erro = utils.upload_to_drive(
            file_buffer=pdf_buffer,
            filename=nome_arquivo,
            mimetype="application/pdf",
            folder_path=["Orçamentos", mes_atual]
        )
        
        # 6. Devolver a resposta para o robô enviar no WhatsApp
        if sucesso:
            # Esse link o robô vai usar para baixar o arquivo e enviar como documento
            link_drive = f"https://drive.google.com/uc?export=download&id={drive_id_ou_erro}"
            return {
                "sucesso": True,
                "mensagem": "Orçamento gerado e salvo no sistema com sucesso!",
                "link_pdf_download": link_drive,
                "numero_orcamento": numero_orc,
                "valor_total_reais": total_geral
            }
        else:
            return {"sucesso": False, "erro": f"Erro ao salvar no Drive: {drive_id_ou_erro}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
