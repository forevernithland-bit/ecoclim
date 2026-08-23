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
import utils

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


def buscar_cidade_id(nome_cidade):
    if not nome_cidade:
        return None
    resp = _request("GET", "/cidades", parametros={"nome": nome_cidade})
    cidades = resp.get("data") or []
    return cidades[0]["id"] if cidades else None


def atualizar_endereco_cliente(cliente_id, cep, numero, complemento=""):
    """A API do Gestão Click EXIGE endereço do destinatário pra criar Nota
    Fiscal (POST /notas_fiscais_produtos falha com 'É necessário informar
    endereço do destinatário!' sem isso) — descoberto testando em produção em
    2026-08-22. Formato do payload (não fica claro na doc pública): PUT
    /clientes/{id} precisa reenviar tipo_pessoa/nome/cpf/cnpj/telefone do
    cliente JUNTO com "enderecos": [{...}] (array, não objeto único) — senão a
    API responde 200 sem erro mas não salva nada. cidade_id vem de /cidades
    (não é o nome da cidade direto)."""
    dados_cep = utils.buscar_cep(cep)
    if not dados_cep:
        raise GestaoClickError(f"CEP {cep} não encontrado (ViaCEP).")
    cidade_id = buscar_cidade_id(dados_cep["localidade"])
    if not cidade_id:
        raise GestaoClickError(f"Cidade '{dados_cep['localidade']}' não encontrada no cadastro do Gestão Click.")
    cliente_atual = (_request("GET", f"/clientes/{cliente_id}") or {}).get("data") or {}
    corpo = {
        "tipo_pessoa": cliente_atual.get("tipo_pessoa") or "PF",
        "nome": cliente_atual.get("nome") or "",
        "cpf": cliente_atual.get("cpf") or "",
        "cnpj": cliente_atual.get("cnpj") or "",
        "telefone": cliente_atual.get("telefone") or "",
        "enderecos": [
            {
                "nome": "Principal",
                "cep": dados_cep["cep"].replace("-", ""),
                "logradouro": dados_cep["logradouro"],
                "numero": numero,
                "complemento": complemento,
                "bairro": dados_cep["bairro"],
                "cidade_id": cidade_id,
                "nome_cidade": dados_cep["localidade"],
                "estado": dados_cep["uf"],
            }
        ],
    }
    _request("PUT", f"/clientes/{cliente_id}", corpo=corpo)


# Prefixo do "código interno" mandado pro Gestão Click, por catálogo de origem —
# materiais_padrao e catalogo_produtos são tabelas diferentes e podem ter o mesmo
# id numérico (ex: os dois terem um item id=25); sem prefixo, os dois chegariam lá
# com o mesmo código interno e ficariam indistinguíveis num relatório/busca de lá.
PREFIXO_CODIGO_INTERNO = {"materiais_padrao": "HID", "catalogo_produtos": "EQP"}


def garantir_produto(supabase, material, tabela="materiais_padrao"):
    """Cria OU atualiza o produto no Gestão Click a partir do registro local
    (materiais_padrao ou catalogo_produtos) — nunca duplica (usa codigo_externo,
    o ID DE VERDADE que o Gestão Click atribui, salvo no nosso banco, pra saber
    se já existe), e sempre reenvia preço/estoque/NCM atualizados, pra nunca
    deixar o Gestão Click desatualizado em relação ao nosso catálogo (regra
    combinada em 2026-08-22: os dois lados têm que andar sincronizados).
    codigo_interno é só um campo de referência (tipo SKU) — prefixado por
    catálogo (HID-/EQP-) pra nunca colidir entre materiais_padrao e
    catalogo_produtos, nem com algo cadastrado manualmente lá. Chamada sempre
    que preço/estoque muda no ERP — ver pontos de chamada em
    estoque_materiais.py, servicos_painel.py e tela_configuracoes.py."""
    prefixo = PREFIXO_CODIGO_INTERNO.get(tabela, tabela.upper())
    corpo = {
        "nome": material.get("item"),
        "codigo_interno": f"{prefixo}-{material.get('id')}",
        "codigo_barra": material.get("codigo_barra") or "",
        "valor_custo": float(material.get("custo") or 0),
        "valor_venda": float(material.get("venda") or 0),
        "estoque": float(material.get("estoque_atual") or 0),
        "ncm": material.get("ncm") or "",
    }
    if material.get("codigo_externo"):
        _request("PUT", f"/produtos/{material['codigo_externo']}", corpo=corpo)
        return material["codigo_externo"]

    resp = _request("POST", "/produtos", corpo=corpo)
    produto_id = (resp.get("data") or {}).get("id")
    if produto_id:
        supabase.table(tabela).update({"codigo_externo": str(produto_id)}).eq("id", material["id"]).execute()
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
