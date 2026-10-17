"""Itens que vivem nas DUAS bases ao mesmo tempo — `materiais_padrao` (Lista de
Materiais hidráulicos) e `catalogo_produtos` (equipamentos de aquecedor solar,
tela Configurações → Edição de Catálogos).

Pedido do Breno (2026-10-16): a "Caixa Auxiliar de Quebra de Pressão" é um item
de alta recorrência e precisa aparecer nas duas listas; mudou o valor numa,
muda na outra. O casamento é pelo NOME (igual, sem diferenciar maiúsculas,
acento ou espaços) — por isso o nome tem que ficar igual nas duas bases.

Módulo puro (sem streamlit): recebe o cliente do Supabase por parâmetro, então
serve tanto pro ERP quanto pros scripts da skill (`espelhar_item.py`).

Regras:
- Só CUSTO e VENDA são espelhados (margem e lucro são derivados deles:
  as duas tabelas usam margem = (venda − custo) / custo × 100).
- Estoque é só da Lista de Materiais (`materiais_padrao`): equipamento não tem
  estoque. Por isso, no Gestão Click, este item é UM produto só, mandado a
  partir de `materiais_padrao` (ver redirecionamento em
  `gestao_click.garantir_produto`) — senão o catálogo de equipamentos
  zeraria o estoque dele lá e o código interno (HID-/EQP-) ficaria trocando.
"""
import re
import unicodedata

ITENS_ESPELHADOS = ["Caixa Auxiliar de Quebra de Pressão"]


def _n(texto):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().casefold()


_NORMALIZADOS = {_n(x) for x in ITENS_ESPELHADOS}


def eh_espelhado(nome):
    return _n(nome) in _NORMALIZADOS


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _margem(custo, venda):
    return round((venda - custo) / custo * 100, 2) if custo > 0 else 0.0


def _achar(sb, tabela, nome):
    """Linha da tabela cujo nome casa com `nome` (None se não houver)."""
    alvo = _n(nome)
    for r in (sb.table(tabela).select("*").execute().data or []):
        if _n(r.get("item")) == alvo:
            return r
    return None


def valores_atuais(sb, tabela):
    """{nome normalizado: (custo, venda)} dos itens espelhados nesta tabela —
    foto de ANTES de um salvamento em massa, pra saber o que mudou de verdade."""
    out = {}
    for r in (sb.table(tabela).select("item,custo,venda").execute().data or []):
        if eh_espelhado(r.get("item")):
            out[_n(r.get("item"))] = (_f(r.get("custo")), _f(r.get("venda")))
    return out


def material_equivalente(sb, nome):
    """Linha de `materiais_padrao` do item espelhado (ou None se o item não é
    espelhado). Usada pelo Gestão Click pra mandar o produto certo."""
    if not eh_espelhado(nome):
        return None
    return _achar(sb, "materiais_padrao", nome)


def garantir_espelho(sb, nome):
    """Cria a linha em `catalogo_produtos` (a partir de `materiais_padrao`) se
    ainda não existir. Devolve 'criado', 'ja_existia' ou 'sem_origem'."""
    mat = _achar(sb, "materiais_padrao", nome)
    if not mat:
        return "sem_origem"
    if _achar(sb, "catalogo_produtos", nome):
        return "ja_existia"
    custo, venda = _f(mat.get("custo")), _f(mat.get("venda"))
    sb.table("catalogo_produtos").insert({
        "item": mat.get("item"), "descricao": "",
        "custo": custo, "venda": venda,
        "margem": _margem(custo, venda), "lucro": round(venda - custo, 2),
        "ncm": mat.get("ncm"), "codigo_externo": mat.get("codigo_externo"),
        "codigo_barra": mat.get("codigo_barra"),
    }).execute()
    return "criado"


def propagar(sb, origem, nome, custo, venda):
    """Copia custo/venda de `origem` ('materiais_padrao' | 'catalogo_produtos')
    pra OUTRA base. Devolve True se alterou alguma coisa. Nunca levanta:
    espelhar não pode derrubar o salvamento que o usuário acabou de fazer."""
    try:
        if not eh_espelhado(nome):
            return False
        custo, venda = round(_f(custo), 2), round(_f(venda), 2)
        destino = "catalogo_produtos" if origem == "materiais_padrao" else "materiais_padrao"
        linha = _achar(sb, destino, nome)
        if linha is None:
            if destino == "catalogo_produtos":
                garantir_espelho(sb, nome)
                linha = _achar(sb, destino, nome)
            if linha is None:
                return False
        if abs(_f(linha.get("custo")) - custo) < 0.005 and abs(_f(linha.get("venda")) - venda) < 0.005:
            return False
        if destino == "catalogo_produtos":
            dados = {"custo": custo, "venda": venda, "margem": _margem(custo, venda), "lucro": round(venda - custo, 2)}
        else:
            dados = {"custo": custo, "venda": venda, "margem_percentual": _margem(custo, venda)}
        sb.table(destino).update(dados).eq("id", linha["id"]).execute()
        return True
    except Exception:
        return False
