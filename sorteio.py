"""Sorteio de bichinhos: chances por raridade, bônus por confiança e missão diária."""
import datetime
import random

import banco
import catalogo

# ---------- constantes ajustáveis ----------

# Se o YOLO tiver pelo menos esta certeza, o sorteio ganha bônus.
CONFIANCA_PARA_BONUS = 0.9

# Raridades que ficam mais prováveis com o bônus, e quanto (2 = o dobro).
RARIDADES_COM_BONUS = ["epico", "lendario", "mitico"]
MULTIPLICADOR_BONUS = 2


# ---------- chances ----------

def chances_base():
    """Chances normais de cada raridade, ex.: {"comum": 60, ...}. Somam 100."""
    return {raridade: dados["chance"] for raridade, dados in catalogo.RARIDADES.items()}


def chances_com_bonus():
    """Multiplica as raridades altas e reajusta tudo para somar 100 de novo."""
    chances = chances_base()
    for raridade in RARIDADES_COM_BONUS:
        chances[raridade] *= MULTIPLICADOR_BONUS
    return _renormalizar(chances)


def _renormalizar(chances):
    """Reescala as chances para que a soma volte a ser 100."""
    total = sum(chances.values())
    return {raridade: valor * 100 / total for raridade, valor in chances.items()}


def tem_bonus(confianca):
    """True se a detecção foi certeira o bastante para ganhar bônus."""
    return confianca >= CONFIANCA_PARA_BONUS


# ---------- sorteio ----------

def sortear_raridade(chances):
    """Escolhe uma raridade usando as chances como pesos."""
    raridades = list(chances)
    pesos = list(chances.values())
    return random.choices(raridades, weights=pesos, k=1)[0]


def sortear(elemento=None, com_bonus=False):
    """Sorteia um bichinho. elemento=None sorteia de qualquer elemento."""
    chances = chances_com_bonus() if com_bonus else chances_base()

    # Tira raridades sem nenhum bichinho daquele elemento (evita sortear "nada").
    chances = {r: c for r, c in chances.items() if catalogo.filtrar(raridade=r, elemento=elemento)}

    raridade = sortear_raridade(chances)
    candidatos = catalogo.filtrar(raridade=raridade, elemento=elemento)
    return random.choice(candidatos)


def entregar(usuario_id, bichinho, tipo, com_bonus=False):
    """Põe o bichinho no inventário e conta o roll nas estatísticas.

    tipo: "roll", "autoroll", "comprar" ou "capturar".
    Devolve True se é a primeira vez que o usuário pega esse bichinho (NOVO!).
    Depois de entregar, chame titulos.verificar_e_anunciar para avisar títulos novos.
    """
    novo = bichinho["id"] not in banco.descobertos(usuario_id)
    banco.adicionar_bichinho(usuario_id, bichinho["id"])
    banco.registrar_roll(usuario_id, tipo, bichinho["id"])
    _registrar_marcos(usuario_id, bichinho["raridade"], com_bonus)
    return novo


# ---------- marcos usados pelos títulos secretos ----------

RARIDADE_DA_SEQUENCIA = "epico"  # a sequência conta rolls seguidos desta raridade ou melhor


def _registrar_marcos(usuario_id, raridade, com_bonus):
    """Guarda a sequência de épicos+ seguidos e se saiu mítico com bônus de foto."""
    ordem = catalogo.RARIDADES[raridade]["ordem"]
    if ordem >= catalogo.RARIDADES[RARIDADE_DA_SEQUENCIA]["ordem"]:
        atual = banco.somar_contador(usuario_id, "sequencia_epica")
        if atual > banco.contador(usuario_id, "maior_sequencia_epica"):
            banco.definir_contador(usuario_id, "maior_sequencia_epica", atual)
    else:
        banco.definir_contador(usuario_id, "sequencia_epica", 0)
    if raridade == "mitico":
        _contar_mitico_do_dia(usuario_id)
        if com_bonus:
            banco.somar_contador(usuario_id, "mitico_com_bonus")


def _contar_mitico_do_dia(usuario_id):
    """Conta os míticos de hoje e guarda o recorde de míticos num mesmo dia."""
    hoje = datetime.date.today().toordinal()  # o dia vira um número para caber no contador
    if banco.contador(usuario_id, "dia_mitico") != hoje:
        banco.definir_contador(usuario_id, "dia_mitico", hoje)
        banco.definir_contador(usuario_id, "miticos_no_dia", 0)
    no_dia = banco.somar_contador(usuario_id, "miticos_no_dia")
    if no_dia > banco.contador(usuario_id, "max_miticos_dia"):
        banco.definir_contador(usuario_id, "max_miticos_dia", no_dia)


# ---------- missão diária ----------

def elemento_do_dia(data=None):
    """Elemento da missão de hoje. A mesma data sempre dá o mesmo elemento."""
    if data is None:
        data = datetime.date.today()
    # Random com a data como semente: todo mundo recebe o mesmo elemento no dia.
    gerador = random.Random(data.isoformat())
    return gerador.choice(list(catalogo.ELEMENTOS))


def _acao_missao(data):
    # Uma "ação" diferente por dia (ex.: "missao_2026-11-18"): assim o banco
    # registra se a missão daquele dia específico já foi feita.
    return f"missao_{data.isoformat()}"


def missao_concluida(usuario_id, data=None):
    """True se o usuário já completou a missão desse dia."""
    if data is None:
        data = datetime.date.today()
    # Janela enorme: se a ação do dia já foi registrada alguma vez, sobra tempo.
    um_ano = 365 * 24 * 60 * 60
    return banco.tempo_restante(usuario_id, _acao_missao(data), um_ano) > 0


def concluir_missao(usuario_id, data=None):
    """Marca a missão desse dia como feita."""
    if data is None:
        data = datetime.date.today()
    banco.registrar_uso(usuario_id, _acao_missao(data))
    banco.somar_contador(usuario_id, "missoes")  # usado pelo título de missões
