"""Catálogo de bichinhos: lê o arquivo JSON e oferece funções de consulta."""
import difflib
import json
import os
import unicodedata

CAMINHO_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "bichinhos.json")

ELEMENTOS = {
    "natureza": {"nome": "Natureza", "emoji": "🌿"},
    "fogo": {"nome": "Fogo", "emoji": "🔥"},
    "agua": {"nome": "Água", "emoji": "💧"},
    "eletrico": {"nome": "Elétrico", "emoji": "⚡"},
    "mistico": {"nome": "Místico", "emoji": "🔮"},
    "fera": {"nome": "Fera", "emoji": "🐾"},
}

# "ordem" vai da mais comum (1) para a mais rara (6)
RARIDADES = {
    "comum": {"nome": "Comum", "chance": 60, "cor": 0x9E9E9E, "ordem": 1},
    "incomum": {"nome": "Incomum", "chance": 25, "cor": 0x4CAF50, "ordem": 2},
    "raro": {"nome": "Raro", "chance": 10, "cor": 0x2196F3, "ordem": 3},
    "epico": {"nome": "Épico", "chance": 4, "cor": 0x9C27B0, "ordem": 4},
    "lendario": {"nome": "Lendário", "chance": 0.9, "cor": 0xFFB300, "ordem": 5},
    "mitico": {"nome": "Mítico", "chance": 0.1, "cor": 0xFF4081, "ordem": 6},
}

_cache = None  # lista de bichinhos já carregada
_por_id = {}   # id -> bichinho


def _normalizar(texto):
    """Tira acentos, deixa minúsculo e remove pontuação/espaços extras."""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = "".join(c if c.isalnum() else " " for c in texto)
    return " ".join(texto.split())


def normalizar(texto):
    """Versão pública de _normalizar (usada pelo chatbot e pelo main)."""
    return _normalizar(texto)


def carregar():
    """Lê o JSON uma única vez e guarda em cache."""
    global _cache
    if _cache is None:
        with open(CAMINHO_JSON, encoding="utf-8") as arquivo:
            _cache = json.load(arquivo)["bichinhos"]
        _por_id.clear()
        for bichinho in _cache:
            _por_id[bichinho["id"]] = bichinho
    return _cache


def por_id(id):
    """Devolve o bichinho com esse id, ou None."""
    carregar()
    return _por_id.get(id)


def filtrar(raridade=None, elemento=None):
    """Lista os bichinhos, opcionalmente só de uma raridade e/ou elemento."""
    resultado = []
    for b in carregar():
        if raridade is not None and b["raridade"] != raridade:
            continue
        if elemento is not None and b["elemento"] != elemento:
            continue
        resultado.append(b)
    return resultado


def buscar(nome):
    """Procura por nome: exato, parcial ou parecido (aceita erro de digitação)."""
    consulta = _normalizar(nome)
    if not consulta:
        return None
    nomes = {_normalizar(b["nome"]): b for b in carregar()}

    # 1) nome exato
    if consulta in nomes:
        return nomes[consulta]

    # 2) nome parcial (prefere quem começa com o texto, depois o menor nome)
    parciais = [n for n in nomes if consulta in n]
    if parciais:
        parciais.sort(key=lambda n: (not n.startswith(consulta), len(n)))
        return nomes[parciais[0]]

    # 3) erro de digitação: compara com o nome inteiro e com cada palavra
    parecidos = difflib.get_close_matches(consulta, list(nomes), n=1, cutoff=0.6)
    if parecidos:
        return nomes[parecidos[0]]
    melhor, melhor_nota = None, 0.0
    for n, b in nomes.items():
        for palavra in n.split():
            if len(palavra) < 4:
                continue
            nota = difflib.SequenceMatcher(None, consulta, palavra).ratio()
            if nota > melhor_nota:
                melhor, melhor_nota = b, nota
    if melhor_nota >= 0.75:
        return melhor
    return None
