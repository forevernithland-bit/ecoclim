"""Sincronização AUTOMÁTICA da carteira (Inter + XP) via Pluggy — plano gratuito
"Meu Pluggy" (até 5 conexões). Sem Streamlit.

Como ligar (uma vez, ~10 min, feito por você porque envolve login/senha):
  1. Criar conta grátis em https://meu.pluggy.ai e conectar Inter e XP lá
     (a Pluggy pede o login e o MFA dos bancos — isso você faz na tela dela).
  2. Em https://dashboard.pluggy.ai criar uma aplicação -> Client ID e Client Secret.
  3. Colocar no secrets do Streamlit:
        [pluggy]
        client_id = "..."
        client_secret = "..."
        item_ids = ["uuid-do-item-inter", "uuid-do-item-xp"]   # opcional
Sem item_ids, o sistema usa todos os itens da conta.

Limitações da Pluggy: Inter e XP não têm atualização 100% automática (podem pedir
MFA de novo) — o dado é tão fresco quanto a última atualização feita lá.
Ainda NÃO testado com chaves reais (as chaves só você pode criar).
"""
import json
import re
import urllib.request

API = "https://api.pluggy.ai"


def _req(path, metodo="GET", corpo=None, api_key=None):
    h = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "ecoclim-erp"}
    if api_key:
        h["X-API-KEY"] = api_key
    dados = json.dumps(corpo).encode() if corpo is not None else None
    with urllib.request.urlopen(urllib.request.Request(API + path, data=dados, headers=h, method=metodo), timeout=40) as r:
        return json.loads(r.read())


def _corretora(nome):
    n = (nome or "").lower()
    for k, v in (("xp", "XP"), ("inter", "Inter"), ("btg", "BTG"), ("nu", "NuInvest"), ("rico", "Rico"), ("clear", "Clear")):
        if k in n:
            return v
    return (nome or "Pluggy").strip()


def buscar_posicoes(client_id, client_secret, item_ids=None):
    """Devolve (posicoes, avisos). Posição = {ticker, qtd, pm, corretora, alugada, grupo}.
    A Pluggy informa preço e saldo; preço médio só quando `amount`/`quantity` vierem."""
    avisos, saida = [], []
    key = _req("/auth", "POST", {"clientId": client_id, "clientSecret": client_secret})["apiKey"]
    if not item_ids:
        item_ids = [i["id"] for i in _req("/items", api_key=key).get("results", [])]
    for iid in item_ids:
        try:
            item = _req(f"/items/{iid}", api_key=key)
            corr = _corretora((item.get("connector") or {}).get("name"))
            if item.get("status") not in ("UPDATED", "OUTDATED", None):
                avisos.append(f"{corr}: status {item.get('status')} — atualize a conexão em meu.pluggy.ai.")
            for tipo in ("EQUITY", "ETF"):
                for inv in _req(f"/investments?itemId={iid}&type={tipo}&pageSize=500", api_key=key).get("results", []):
                    cod = str(inv.get("code") or inv.get("name") or "").strip().upper()
                    if cod.endswith("F") and cod[:-1][-1:].isdigit():
                        cod = cod[:-1]  # fracionário
                    qtd = inv.get("quantity")
                    if not re.fullmatch(r"[A-Z][A-Z0-9]{3}[0-9]{1,2}", cod) or not qtd:
                        continue  # ignora nomes livres que não são ticker
                    amount = inv.get("amount") or 0
                    # `amount` costuma ser o saldo atual, não o custo -> não vira preço médio
                    saida.append({"ticker": cod, "qtd": float(qtd), "pm": 0.0, "corretora": corr, "alugada": 0, "grupo": ""})
        except Exception as e:  # noqa: BLE001
            avisos.append(f"Item {iid}: {str(e)[:100]}")
    return saida, avisos
