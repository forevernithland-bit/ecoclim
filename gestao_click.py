"""Cliente da API do Gestão Click — usado pra deixar a Nota Fiscal de venda
de materiais hidráulicos pronta pra emitir (cliente + produtos já
cadastrados, NF em rascunho), sem nunca emitir automaticamente. A emissão
de verdade sempre exige um clique separado do admin (mesmo padrão que
nunca fazemos nada irreversível sem confirmação explícita).

Autenticação e endpoints vêm da documentação oficial (gestaoclick.apib):
base https://api.gestaoclick.com, headers access-token/secret-access-token
em toda chamada.
"""
import streamlit as st
import urllib.request
import urllib.parse
import json

BASE_URL = "https://api.gestaoclick.com"


class GestaoClickError(Exception):
    pass


def _headers():
    try:
        return {
            "access-token": st.secrets["GESTAO_CLICK_ACCESS_TOKEN"],
            "secret-access-token": st.secrets["GESTAO_CLICK_SECRET_TOKEN"],
            "Content-Type": "application/json",
        }
    except Exception:
        raise GestaoClickError(
            "Faltam as credenciais do Gestão Click no st.secrets "
            "(GESTAO_CLICK_ACCESS_TOKEN / GESTAO_CLICK_SECRET_TOKEN)."
        )


def _request(metodo, caminho, corpo=None, parametros=None):
    url = f"{BASE_URL}{caminho}"
    if parametros:
        url += "?" + urllib.parse.urlencode(parametros)
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")
        raise GestaoClickError(f"Gestão Click retornou erro {e.code}: {detalhe}")
    except Exception as e:
        raise GestaoClickError(f"Falha ao chamar o Gestão Click: {e}")


def buscar_loja_id():
    """A maioria das contas só tem uma loja — usa a primeira e guarda em
    sessão pra não bater na API de novo a cada operação."""
    if st.session_state.get("_gc_loja_id"):
        return st.session_state["_gc_loja_id"]
    resp = _request("GET", "/lojas")
    lojas = resp.get("data") or []
    if not lojas:
        raise GestaoClickError("Nenhuma loja encontrada na conta do Gestão Click.")
    loja_id = lojas[0]["id"]
    st.session_state["_gc_loja_id"] = loja_id
    return loja_id


def buscar_cliente_por_cpf(cpf_cnpj):
    cpf_limpo = "".join(c for c in str(cpf_cnpj or "") if c.isdigit())
    if not cpf_limpo:
        return None
    resp = _request("GET", "/clientes", parametros={"cpf_cnpj": cpf_limpo})
    clientes = resp.get("data") or []
    return clientes[0] if clientes else None


def criar_cliente(nome, cpf_cnpj, telefone=""):
    cpf_limpo = "".join(c for c in str(cpf_cnpj or "") if c.isdigit())
    tipo_pessoa = "PJ" if len(cpf_limpo) > 11 else "PF"
    corpo = {
        "tipo_pessoa": tipo_pessoa,
        "nome": nome,
        "cpf": cpf_cnpj if tipo_pessoa == "PF" else "",
        "cnpj": cpf_cnpj if tipo_pessoa == "PJ" else "",
        "telefone": telefone or "",
    }
    resp = _request("POST", "/clientes", corpo=corpo)
    return resp.get("data")


def garantir_produto(supabase, material):
    """Se o material já tem codigo_externo (id do produto lá), reaproveita.
    Senão, cadastra no Gestão Click e salva o id retornado de volta no
    materiais_padrao — pra nunca duplicar o mesmo produto numa próxima venda."""
    if material.get("codigo_externo"):
        return material["codigo_externo"]

    corpo = {
        "nome": material.get("item"),
        "codigo_interno": str(material.get("id")),
        "codigo_barra": material.get("codigo_barra") or "",
        "valor_custo": float(material.get("custo") or 0),
        "valor_venda": float(material.get("venda") or 0),
        "estoque": float(material.get("estoque_atual") or 0),
        "ncm": material.get("ncm") or "",
    }
    resp = _request("POST", "/produtos", corpo=corpo)
    produto_id = (resp.get("data") or {}).get("id")
    if produto_id:
        supabase.table("materiais_padrao").update({"codigo_externo": str(produto_id)}).eq("id", material["id"]).execute()
    return produto_id


def criar_nota_fiscal_rascunho(loja_id, cliente_id, itens):
    """itens: lista de {produto_id, quantidade, valor_venda, valor_custo, ncm}.
    envio_automatico sempre 0 — a NF fica em rascunho, emitir é outro passo."""
    corpo = {
        "loja_id": loja_id,
        "tipo_nf": 1,  # saída
        "id_destinatario": cliente_id,
        "envio_automatico": 0,
        "produtos": [
            {
                "produto_id": it["produto_id"],
                "quantidade": it["quantidade"],
                "valor_venda": it["valor_venda"],
                "valor_custo": it["valor_custo"],
                "NCM": it.get("ncm") or "",
            }
            for it in itens
        ],
    }
    resp = _request("POST", "/notas_fiscais_produtos", corpo=corpo)
    return (resp.get("data") or {}).get("dados")


def emitir_nota_fiscal(nf_id):
    resp = _request("POST", f"/notas_fiscais_produtos/emitir/{nf_id}")
    dados = resp.get("data") or {}
    if not dados.get("ok"):
        raise GestaoClickError(dados.get("mensagem") or "Erro desconhecido ao emitir.")
    return dados
