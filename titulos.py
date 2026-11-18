"""Títulos: conquistas que o jogador desbloqueia jogando e pode equipar.

Cada título tem uma "regra" escrita como tupla, por exemplo ("rolls", 100)
= "fazer 100 rolls". A função progresso() sabe ler cada tipo de regra, então
para criar um título novo basta acrescentar uma linha na lista TITULOS.

A lista está em ordem de dificuldade: os primeiros saem logo, os últimos
(e os secretos) são para os jogadores mais dedicados. Quanto mais difícil,
mais chamativa a cor.
"""
import difflib

import banco
import catalogo


def _titulo(id, nome, emoji, cor, descricao, regra, secreto=False):
    """Monta o dicionário de um título (só para a lista abaixo ficar curta)."""
    return {"id": id, "nome": nome, "emoji": emoji, "cor": cor, "descricao": descricao,
            "regra": regra, "secreto": secreto}


TITULOS = [
    # --- começo da jornada (cores suaves) ---
    _titulo("filhote_curioso", "Filhote Curioso", "🐣", "#BCAAA4", "Fazer 10 rolls.", ("rolls", 10)),
    _titulo("clique_certeiro", "Clique Certeiro", "📸", "#90A4AE", "Capturar 1 bichinho por foto.",
            ("tipo", "capturar", 1)),
    _titulo("aperto_de_pata", "Aperto de Pata", "🤝", "#FFB74D", "Concluir 1 troca com alguém.",
            ("contador", "trocas", 1)),
    _titulo("olho_de_safira", "Olho de Safira", "🔷", "#64B5F6", "Conseguir um bichinho Raro.",
            ("raridade", "raro")),
    _titulo("dado_inquieto", "Dado Inquieto", "🎲", "#78909C", "Fazer 100 rolls.", ("rolls", 100)),
    _titulo("colecionador_aprendiz", "Colecionador Aprendiz", "📒", "#A1887F", "Descobrir 25 bichinhos.",
            ("descobertos", 25)),
    _titulo("piloto_automatico", "Piloto Automático", "🤖", "#607D8B", "Fazer 100 autorolls.",
            ("tipo", "autoroll", 100)),
    _titulo("aura_violeta", "Aura Violeta", "💜", "#AB47BC", "Conseguir um bichinho Épico.",
            ("raridade", "epico")),
    _titulo("coracao_generoso", "Coração Generoso", "🎁", "#F06292", "Dar 5 presentes com !dar.",
            ("contador", "presentes", 5)),
    _titulo("cofrinho_cheio", "Cofrinho Cheio", "🐷", "#C0CA33", "Ter 1.000 moedas de uma vez.",
            ("moedas", 1000)),
    _titulo("lente_afiada", "Lente Afiada", "🔍", "#26C6DA", "Capturar 25 bichinhos por foto.",
            ("tipo", "capturar", 25)),
    _titulo("guardiao_do_album", "Guardião do Álbum", "📖", "#5C6BC0", "Descobrir 50 bichinhos.",
            ("descobertos", 50)),
    _titulo("explorador_diario", "Explorador Diário", "🧭", "#8BC34A", "Completar 7 missões diárias.",
            ("contador", "missoes", 7)),
    _titulo("mare_de_sorte", "Maré de Sorte", "🌊", "#26A69A", "Fazer 500 rolls.", ("rolls", 500)),
    _titulo("coroa_dourada", "Coroa Dourada", "👑", "#FFB300", "Conseguir um bichinho Lendário.",
            ("raridade", "lendario")),
    _titulo("mercador_viajante", "Mercador Viajante", "🧳", "#EF6C00", "Concluir 10 trocas.",
            ("contador", "trocas", 10)),
    _titulo("roda_da_fortuna", "Roda da Fortuna", "🎡", "#42A5F5", "Fazer 1.000 rolls.", ("rolls", 1000)),
    _titulo("engrenagem_incansavel", "Engrenagem Incansável", "⚙️", "#546E7A", "Fazer 1.000 autorolls.",
            ("tipo", "autoroll", 1000)),
    _titulo("fotografo_elemental", "Fotógrafo Elemental", "📷", "#00ACC1", "Capturar 100 bichinhos por foto.",
            ("tipo", "capturar", 100)),
    _titulo("enciclopedia_viva", "Enciclopédia Viva", "📚", "#00897B", "Descobrir 100 bichinhos.",
            ("descobertos", 100)),
    _titulo("toque_do_arco_iris", "Toque do Arco-Íris", "🌈", "#FF4081", "Conseguir um bichinho Mítico.",
            ("raridade", "mitico")),
    _titulo("tesouro_do_dragao", "Tesouro do Dragão", "💰", "#FFC400", "Ter 10.000 moedas de uma vez.",
            ("moedas", 10000)),
    _titulo("sabio_dos_espiritos", "Sábio dos Espíritos", "🦉", "#D81B60", "Descobrir 150 bichinhos.",
            ("descobertos", 150)),
    _titulo("lenda_do_giro", "Lenda do Giro", "🌀", "#7C4DFF", "Fazer 5.000 rolls.", ("rolls", 5000)),
    # --- mestres de elemento: todos os bichinhos do elemento, inclusive os míticos ---
    _titulo("coracao_da_floresta", "Coração da Floresta", "🌿", "#2E7D32",
            "Descobrir todos os bichinhos de Natureza.", ("elemento", "natureza")),
    _titulo("chama_eterna", "Chama Eterna", "🔥", "#FF3D00", "Descobrir todos os bichinhos de Fogo.",
            ("elemento", "fogo")),
    _titulo("alma_das_mares", "Alma das Marés", "💧", "#0091EA", "Descobrir todos os bichinhos de Água.",
            ("elemento", "agua")),
    _titulo("faisca_viva", "Faísca Viva", "⚡", "#FFEA00", "Descobrir todos os bichinhos Elétricos.",
            ("elemento", "eletrico")),
    _titulo("oraculo_arcano", "Oráculo Arcano", "🔮", "#D500F9", "Descobrir todos os bichinhos Místicos.",
            ("elemento", "mistico")),
    _titulo("rei_da_matilha", "Rei da Matilha", "🐾", "#FF6D00", "Descobrir todos os bichinhos Fera.",
            ("elemento", "fera")),
    # --- secretos: aparecem como "❓ ???" até alguém conseguir ---
    _titulo("trovao_gemeo", "Trovão Gêmeo", "🌩️", "#00E5FF", "Tirar 2 bichinhos Épicos ou melhores seguidos.",
            ("contador", "maior_sequencia_epica", 2), secreto=True),
    _titulo("moeda_da_sorte", "Moeda da Sorte", "🍀", "#76FF03", "Conseguir um Mítico num roll comprado.",
            ("tipo_raridade", "comprar", "mitico"), secreto=True),
    _titulo("sorte_adormecida", "Sorte Adormecida", "😴", "#B388FF", "Conseguir um Mítico no autoroll.",
            ("tipo_raridade", "autoroll", "mitico"), secreto=True),
    _titulo("clique_divino", "Clique Divino", "🌟", "#FFD600", "Capturar um Mítico com bônus de foto nítida.",
            ("contador", "mitico_com_bonus", 1), secreto=True),
    _titulo("tempestade_perfeita", "Tempestade Perfeita", "🌪️", "#18FFFF",
            "Tirar 3 bichinhos Épicos ou melhores seguidos.", ("contador", "maior_sequencia_epica", 3),
            secreto=True),
    _titulo("guardiao_dos_mitos", "Guardião dos Mitos", "🐉", "#FF1744", "Descobrir todos os bichinhos Míticos.",
            ("todos_raridade", "mitico"), secreto=True),
    _titulo("eterno_colecionador", "Eterno Colecionador", "🌌", "#E040FB",
            "Descobrir TODOS os bichinhos do jogo (coleção completa).", ("colecao",), secreto=True),
    # --- secretos MUITO difíceis ---
    _titulo("dia_abencoado", "Dia Abençoado", "☀️", "#FFAB00", "Conseguir 2 Míticos no mesmo dia.",
            ("contador", "max_miticos_dia", 2), secreto=True),
    _titulo("dez_mil_giros", "Dez Mil Giros", "♾️", "#651FFF", "Fazer 10.000 rolls.", ("rolls", 10000),
            secreto=True),
    _titulo("trindade_mitica", "Trindade Mítica", "🔱", "#F50057",
            "Ter 3 cópias de cada bichinho Mítico ao mesmo tempo.", ("copias_raridade", "mitico", 3),
            secreto=True),
    _titulo("colecionador_puro", "Colecionador Puro", "💎", "#FFFFFE",
            "Completar a coleção inteira sem nunca vender um Mítico.", ("colecao_pura",), secreto=True),
]

_POR_ID = {titulo["id"]: titulo for titulo in TITULOS}


def por_id(titulo_id):
    """Título com esse id, ou None (ex.: um título que foi removido da lista)."""
    return _POR_ID.get(titulo_id)


def cor_int(titulo):
    """Cor do título como número (o Discord usa assim): "#FFB300" -> 0xFFB300."""
    return int(titulo["cor"].lstrip("#"), 16)


def texto(titulo):
    """Ex.: "👑 Coroa Dourada"."""
    return f"{titulo['emoji']} {titulo['nome']}"


def oculto(titulo, desbloqueados):
    """True se é secreto e o jogador ainda não tem: não pode aparecer o nome."""
    return titulo["secreto"] and titulo["id"] not in desbloqueados


# ---------- dados do jogador e regras ----------

def coletar_dados(usuario_id):
    """Junta numa vez só tudo o que as regras precisam saber do jogador."""
    return {
        "stats": banco.estatisticas(usuario_id),
        "por_tipo_raridade": banco.rolls_por_tipo_e_raridade(usuario_id),
        "descobertos": banco.descobertos(usuario_id),
        "inventario": banco.inventario(usuario_id),
        "moedas": banco.moedas(usuario_id),
        "contadores": banco.contadores(usuario_id),
    }


def _quantos_descobertos(dados, raridade=None, elemento=None):
    """(descobertos, total) dos bichinhos com esse filtro."""
    todos = catalogo.filtrar(raridade=raridade, elemento=elemento)
    achados = sum(1 for b in todos if b["id"] in dados["descobertos"])
    return achados, len(todos)


def progresso(titulo, dados):
    """(quanto já tem, quanto precisa) para a regra do título."""
    tipo, *args = titulo["regra"]
    if tipo == "rolls":
        return dados["stats"]["total"], args[0]
    if tipo == "tipo":
        return dados["stats"]["por_tipo"].get(args[0], 0), args[1]
    if tipo == "contador":
        return dados["contadores"].get(args[0], 0), args[1]
    if tipo == "moedas":
        return dados["moedas"], args[0]
    if tipo == "descobertos":
        return len(dados["descobertos"]), args[0]
    if tipo == "raridade":
        achados, _ = _quantos_descobertos(dados, raridade=args[0])
        return min(achados, 1), 1
    if tipo == "tipo_raridade":
        return min(dados["por_tipo_raridade"].get((args[0], args[1]), 0), 1), 1
    if tipo == "elemento":
        return _quantos_descobertos(dados, elemento=args[0])
    if tipo == "todos_raridade":
        return _quantos_descobertos(dados, raridade=args[0])
    if tipo == "colecao":
        return _quantos_descobertos(dados)
    if tipo == "copias_raridade":
        raridade, copias = args
        todos = catalogo.filtrar(raridade=raridade)
        com_copias = sum(1 for b in todos if dados["inventario"].get(b["id"], 0) >= copias)
        return com_copias, len(todos)
    if tipo == "colecao_pura":
        # Vendeu um mítico uma vez? Esse título fica impossível para sempre.
        if dados["contadores"].get("miticos_vendidos", 0) > 0:
            return 0, len(catalogo.carregar())
        return _quantos_descobertos(dados)
    raise ValueError(f"Regra de título desconhecida: {tipo}")


def cumpre(titulo, dados):
    """True se o jogador já cumpriu a regra do título."""
    atual, meta = progresso(titulo, dados)
    return atual >= meta


# ---------- interface usada pelo bot ----------

def verificar_titulos(usuario_id):
    """Desbloqueia os títulos que o jogador acabou de conquistar e devolve a lista deles."""
    ja_tem = banco.titulos_desbloqueados(usuario_id)
    faltam = [t for t in TITULOS if t["id"] not in ja_tem]
    if not faltam:
        return []
    dados = coletar_dados(usuario_id)
    novos = []
    for titulo in faltam:
        if cumpre(titulo, dados) and banco.desbloquear_titulo(usuario_id, titulo["id"]):
            novos.append(titulo)
    return novos


def desbloqueados(usuario_id):
    """Títulos que o jogador tem, na ordem da lista (do mais fácil ao mais difícil)."""
    ids = banco.titulos_desbloqueados(usuario_id)
    return [t for t in TITULOS if t["id"] in ids]


def equipado(usuario_id):
    """Título equipado (dicionário) ou None."""
    titulo_id = banco.titulo_equipado(usuario_id)
    return por_id(titulo_id) if titulo_id else None


def buscar(texto_digitado, permitidos=None):
    """Acha um título pelo nome (sem acento, parcial ou com erro de digitação).

    permitidos: lista de títulos onde procurar (padrão: todos que não são secretos).
    """
    if permitidos is None:
        permitidos = [t for t in TITULOS if not t["secreto"]]
    procurado = catalogo.normalizar(texto_digitado)
    if not procurado:
        return None
    nomes = {catalogo.normalizar(t["nome"]): t for t in permitidos}
    if procurado in nomes:
        return nomes[procurado]
    for regra in (lambda n: n.startswith(procurado), lambda n: procurado in n):
        achados = [n for n in nomes if regra(n)]
        if achados:
            return nomes[min(achados, key=len)]
    parecidos = difflib.get_close_matches(procurado, list(nomes), n=1, cutoff=0.6)
    return nomes[parecidos[0]] if parecidos else None


async def verificar_e_anunciar(destino, usuario_id):
    """Verifica títulos novos e manda um embed para cada um no canal.

    Chamado depois de todo roll, captura, troca, venda e autoroll.
    destino é qualquer coisa com .send() (canal ou contexto de comando).
    """
    import embeds  # importado aqui para os módulos não se importarem em círculo

    novos = verificar_titulos(usuario_id)
    if destino is None:
        return novos
    for titulo in novos:
        try:
            await destino.send(embed=embeds.embed_titulo_novo(titulo, usuario_id))
        except Exception as erro:  # um aviso que falha não pode estragar o comando
            print(f"Não consegui anunciar o título {titulo['id']}: {erro!r}")
    return novos
