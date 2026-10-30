"""Ajustes do catálogo de equipamentos (catalogo_produtos) que não cabem em coluna do banco.

1. ITENS OCULTOS (pedido do Breno, 2026-10-27: "oculte da lista o que está sem
   estoque"). Item oculto continua existindo no catálogo (preço, NCM, histórico
   dos clientes que já o usam) — só deixa de aparecer nas listas de escolha de
   orçamento, serviços, kits e na busca global. A lista de nomes fica em
   fin_configuracoes, chave `catalogo_produtos_ocultos` (JSON em valor1); não
   precisa de coluna nova no banco. Para reexibir: Configurações → Produtos →
   "Itens ocultos".
2. ALIAS DE NOMES ANTIGOS: os reservatórios "BOILER BP 600 LITROS D 72 AÇO 304
   SOLAR GLOBAL" etc. foram trocados pelos nomes novos ("Boiler 600 litros 304 -
   BP - Metalic 68 mm"). Orçamentos/serviços antigos guardam o nome antigo como
   texto; o alias deixa a emissão de NF achar o produto novo.
"""
import json
import unicodedata

CHAVE_OCULTOS = "catalogo_produtos_ocultos"


def norm(t):
    t = unicodedata.normalize("NFD", str(t or "").strip().lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").split())


def _alias():
    a = {}
    for aco in ("304", "316"):
        for litros in (200, 300, 400, 500, 600, 800, 1000):
            antigo = f"BOILER BP {litros} LITROS " + ("D 72 " if litros == 600 else "") + f"AÇO {aco} SOLAR GLOBAL"
            a[norm(antigo)] = f"Boiler {litros} litros {aco} - BP - Metalic 68 mm"
    a[norm("BOILER AP 1050 LITROS AÇO 316 SOLAR GLOBAL")] = "Boiler 1050 litros 316 - AP - Tradicional"
    return a


ALIAS_NOMES_ANTIGOS = _alias()


def nome_atual(nome):
    """Nome novo do item se `nome` for um dos antigos; senão o próprio nome."""
    return ALIAS_NOMES_ANTIGOS.get(norm(nome), nome)


def ler_ocultos(sb):
    """Conjunto de nomes (normalizados) ocultos."""
    try:
        r = sb.table("fin_configuracoes").select("valor1").eq("chave", CHAVE_OCULTOS).execute().data or []
        return {norm(n) for n in json.loads(r[0]["valor1"])} if r else set()
    except Exception:
        return set()


def ler_ocultos_nomes(sb):
    try:
        r = sb.table("fin_configuracoes").select("valor1").eq("chave", CHAVE_OCULTOS).execute().data or []
        return list(json.loads(r[0]["valor1"])) if r else []
    except Exception:
        return []


def gravar_ocultos(sb, nomes):
    texto = json.dumps(list(dict.fromkeys(nomes)), ensure_ascii=False)
    r = sb.table("fin_configuracoes").select("id").eq("chave", CHAVE_OCULTOS).execute().data or []
    if r:
        sb.table("fin_configuracoes").update({"valor1": texto}).eq("id", r[0]["id"]).execute()
    else:
        sb.table("fin_configuracoes").insert({"chave": CHAVE_OCULTOS, "valor1": texto}).execute()


def visiveis(sb, nomes, manter=()):
    """`nomes` sem os ocultos. `manter`: nomes que precisam continuar na lista
    mesmo ocultos/removidos (ex.: item já escolhido naquela linha da grade —
    senão a célula do editor mostra erro)."""
    ocultos = ler_ocultos(sb)
    saida = [n for n in nomes if norm(n) not in ocultos]
    vistos = {norm(n) for n in saida}
    for m in manter:
        m = str(m or "").strip()
        if m and m.upper() != "OUTRO" and m.lower() != "nan" and norm(m) not in vistos:
            saida.append(m)
            vistos.add(norm(m))
    return saida
