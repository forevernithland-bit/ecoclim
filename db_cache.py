"""Cache de leitura do Supabase, por sessão — o que deixa os cliques rápidos.

O Streamlit re-executa a tela inteira a cada clique/tecla, e cada execução
refazia TODAS as consultas ao banco (Controle Financeiro: ~17 consultas por
clique, ~70 ms cada). Este módulo embrulha o cliente do Supabase da sessão:

* LEITURA (`select`): o resultado fica guardado por alguns segundos (TTL) e a
  próxima execução idêntica volta na hora, sem ir ao banco;
* ESCRITA (`insert` / `update` / `delete` / `upsert`, e `rpc`): executa no
  banco normalmente e APAGA o cache inteiro na hora — a leitura seguinte
  (inclusive no mesmo clique) já vem fresca do banco. Por isso nunca aparece
  "salvei e não mudou".
* Quem grava por fora do ERP (app do instalador, outra pessoa logada, scripts)
  aparece em no máximo TTL segundos — e o botão "🔄 Atualizar dados" da barra
  lateral limpa o cache na hora.

Nada aqui muda dado nenhum: é só uma memória curta de leituras. Se algo der
errado no cache, a consulta vai direto ao banco (nunca falha por causa dele).
A cópia devolvida é sempre nova (deepcopy), então quem mexer na lista que
recebeu não estraga o que está guardado.
"""
import copy
import threading
import time

TTL_PADRAO = 25.0        # segundos
_MAX_ENTRADAS = 400
_ESCRITAS = ("insert", "update", "delete", "upsert")


class _Resposta:
    """Cópia leve de uma resposta do postgrest (data/count)."""
    __slots__ = ("data", "count")

    def __init__(self, data, count):
        self.data = data
        self.count = count


class ClienteComCache:
    def __init__(self, cliente, ttl=TTL_PADRAO):
        self._cliente = cliente
        self._ttl = ttl
        self._cache = {}
        self._lock = threading.Lock()
        self.acertos = 0
        self.consultas = 0

    # --- API pública -----------------------------------------------------
    def table(self, nome):
        return _Consulta(self, self._cliente.table(nome), nome, ())

    def from_(self, nome):
        return self.table(nome)

    def rpc(self, *a, **k):
        # rpc pode gravar: trata como escrita (limpa o cache ao executar)
        return _Consulta(self, self._cliente.rpc(*a, **k), "__rpc__", (("rpc", repr(a), repr(k)),), escrita=True)

    def limpar_cache(self):
        with self._lock:
            self._cache.clear()

    def __getattr__(self, nome):
        # storage, auth, postgrest... passam direto
        return getattr(self._cliente, nome)

    # --- uso interno -----------------------------------------------------
    def _ler(self, chave):
        with self._lock:
            item = self._cache.get(chave)
            if item and (time.monotonic() - item[0]) < self._ttl:
                self.acertos += 1
                return copy.deepcopy(item[1]), True
        return None, False

    def _guardar(self, chave, resp):
        with self._lock:
            if len(self._cache) >= _MAX_ENTRADAS:
                # descarta as mais antigas
                for k in sorted(self._cache, key=lambda x: self._cache[x][0])[: _MAX_ENTRADAS // 4]:
                    self._cache.pop(k, None)
            self._cache[chave] = (time.monotonic(), resp)


class _Consulta:
    def __init__(self, dono, builder, tabela, cadeia, escrita=False):
        self._dono = dono
        self._b = builder
        self._t = tabela
        self._cadeia = cadeia
        self._escrita = escrita

    def __getattr__(self, nome):
        alvo = getattr(self._b, nome)
        escrita = self._escrita or nome in _ESCRITAS
        if nome == "execute":
            return self._executar
        if callable(alvo):
            def _encadear(*a, **k):
                r = alvo(*a, **k)
                if r is None or not hasattr(r, "execute"):
                    return r
                try:
                    passo = (nome, repr(a), repr(sorted(k.items())))
                except Exception:
                    passo = (nome, str(id(a)), "")
                return _Consulta(self._dono, r, self._t, self._cadeia + (passo,), escrita)
            return _encadear
        if hasattr(alvo, "execute"):  # propriedades como `.not_`
            return _Consulta(self._dono, alvo, self._t, self._cadeia + ((nome,),), escrita)
        return alvo

    def _executar(self, *a, **k):
        dono = self._dono
        if self._escrita or not self._cadeia or self._cadeia[0][0] != "select":
            r = self._b.execute(*a, **k)
            dono.limpar_cache()  # gravou algo: tudo que estava guardado pode ter mudado
            return r
        chave = (self._t, self._cadeia)
        try:
            guardado, achou = dono._ler(chave)
        except Exception:
            achou = False
        if achou:
            return guardado
        r = self._b.execute(*a, **k)
        dono.consultas += 1
        try:
            dono._guardar(chave, _Resposta(copy.deepcopy(getattr(r, "data", None)), getattr(r, "count", None)))
        except Exception:
            pass
        return r
