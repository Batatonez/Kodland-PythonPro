"""
sprites.py - gera os sprites (pixel art) dos bichinhos.

Cada bichinho é desenhado pixel a pixel numa grade de 32x32 e depois
ampliado 8x (sem suavizar) para um PNG de 256x256 com fundo transparente.
Bichinhos míticos viram um GIF animado (flutuando, com partículas e
brilho arco-íris).

O desenho é montado por partes, cada uma em sua própria função:
    corpo -> padrão -> sombreamento -> contorno -> acessório -> olhos -> boca
e por cima entram os efeitos do elemento e os efeitos da raridade.

Uso:
    python sprites.py                 # usa dados/bichinhos.json
    python sprites.py outro.json      # usa outro arquivo de catálogo
Gera todos os sprites em sprites/ e monta sprites/_galeria.png.
"""

import colorsys
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------------
# Configurações gerais
# ------------------------------------------------------------------
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
PASTA_SPRITES = os.path.join(PASTA_PROJETO, "sprites")
ARQUIVO_CATALOGO = os.path.join(PASTA_PROJETO, "dados", "bichinhos.json")

TAMANHO = 32          # a grade de desenho tem 32x32 pixels
ESCALA = 8            # cada pixel vira um quadrado de 8x8 na imagem final
EIXO = 15.5           # eixo de simetria vertical (entre as colunas 15 e 16)
CHAO_Y = 28           # linha onde fica a sombra no chão
QUADROS_GIF = 10      # quantidade de quadros da animação dos míticos
DURACAO_QUADRO = 110  # milissegundos por quadro

# Cores fixas usadas em várias partes
BRANCO = (255, 255, 255)
LUZ_QUENTE = (255, 250, 228)    # a luz "puxa" as cores para um branco quente
SOMBRA_FRIA = (44, 26, 78)      # a sombra "puxa" as cores para um roxo escuro
QUASE_PRETO = (24, 16, 34)

# Cor do contorno externo de cada raridade (o mítico usa arco-íris)
COR_RARIDADE = {
    "comum": None,
    "incomum": (96, 214, 120),
    "raro": (80, 164, 255),
    "epico": (184, 104, 255),
    "lendario": (255, 198, 46),
    "mitico": None,
}


# ------------------------------------------------------------------
# Funções de cor
# ------------------------------------------------------------------
def hex_para_rgb(texto):
    """'#5fbf4a' -> (95, 191, 74)"""
    texto = texto.strip().lstrip("#")
    return tuple(int(texto[i:i + 2], 16) for i in (0, 2, 4))


def misturar(cor_a, cor_b, t):
    """Mistura duas cores. t=0 devolve cor_a, t=1 devolve cor_b."""
    return tuple(round(cor_a[i] + (cor_b[i] - cor_a[i]) * t) for i in range(3))


def clarear(cor, t):
    return misturar(cor, LUZ_QUENTE, t)


def escurecer(cor, t):
    return misturar(cor, SOMBRA_FRIA, t)


def luminancia(cor):
    """Brilho percebido da cor, de 0 (preto) a 1 (branco)."""
    r, g, b = cor
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def arco_iris(posicao):
    """Cor do arco-íris para uma posição qualquer (o ciclo se repete a cada 1.0)."""
    r, g, b = colorsys.hsv_to_rgb(posicao % 1.0, 0.55, 1.0)
    return (round(r * 255), round(g * 255), round(b * 255))


def com_alfa(cor, alfa):
    return (cor[0], cor[1], cor[2], alfa)


# ------------------------------------------------------------------
# Funções de pixels
#
# Uma "camada" é um dicionário {(x, y): cor}. Juntar camadas é só usar
# .update(): a camada colada por último fica por cima.
# ------------------------------------------------------------------
def dentro(x, y):
    return 0 <= x < TAMANHO and 0 <= y < TAMANHO


def vizinhos(x, y):
    """Os 4 vizinhos de um pixel (direita, esquerda, baixo, cima)."""
    return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


def contorno_de(pixels):
    """Pixels vazios que encostam (pelos lados) nos pixels dados."""
    borda = set()
    for x, y in pixels:
        for vizinho in vizinhos(x, y):
            if vizinho not in pixels and dentro(*vizinho):
                borda.add(vizinho)
    return borda


def com_contorno(camada, cor):
    """Devolve a camada com um contorno de 1 pixel em volta."""
    resultado = {p: cor for p in contorno_de(camada)}
    resultado.update(camada)
    return resultado


def aneis_em_volta(pixels, quantidade):
    """Lista de 'anéis' cada vez mais afastados dos pixels (usado na aura)."""
    aneis = []
    ocupados = set(pixels)
    for _ in range(quantidade):
        novo = set()
        for x, y in ocupados:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    p = (x + dx, y + dy)
                    if p not in ocupados and dentro(*p):
                        novo.add(p)
        aneis.append(novo)
        ocupados |= novo
    return aneis


def mover(camada, dx, dy):
    return {(x + dx, y + dy): cor for (x, y), cor in camada.items() if dentro(x + dx, y + dy)}


def caixa_de(pixels):
    """Retângulo que envolve os pixels: (x_min, y_min, x_max, y_max)."""
    xs = [x for x, _ in pixels]
    ys = [y for _, y in pixels]
    return min(xs), min(ys), max(xs), max(ys)


def desenhar_mapa(camada, mapa, x0, y0, paleta):
    """Desenha um 'mapa' de texto. Cada letra vira a cor indicada na paleta;
    letras fora da paleta (como '.') ficam vazias."""
    for dy, linha in enumerate(mapa):
        for dx, letra in enumerate(linha):
            if letra in paleta and dentro(x0 + dx, y0 + dy):
                camada[(x0 + dx, y0 + dy)] = paleta[letra]


def pixels_do_mapa(mapa, x0, y0, letras="X"):
    """Conjunto de pixels do mapa que usam alguma das letras dadas."""
    pixels = set()
    for dy, linha in enumerate(mapa):
        for dx, letra in enumerate(linha):
            if letra in letras and dentro(x0 + dx, y0 + dy):
                pixels.add((x0 + dx, y0 + dy))
    return pixels


def espelhar(mapa):
    return [linha[::-1] for linha in mapa]


def pintar_peca(pixels, cor):
    """Pinta uma peça pequena (chifre, coroa, asa...) com 3 tons:
    lado esquerdo e topo claros, lado direito escuro (luz vem do topo-esquerda)."""
    camada = {}
    if not pixels:
        return camada
    topo = min(y for _, y in pixels)
    for x, y in pixels:
        esquerda_vazia = (x - 1, y) not in pixels
        direita_vazia = (x + 1, y) not in pixels
        cima_vazio = (x, y - 1) not in pixels
        baixo_vazio = (x, y + 1) not in pixels
        if (direita_vazia or baixo_vazio) and not (esquerda_vazia or cima_vazio):
            camada[(x, y)] = escurecer(cor, 0.3)
        elif esquerda_vazia or cima_vazio or y == topo:
            camada[(x, y)] = clarear(cor, 0.35)
        else:
            camada[(x, y)] = cor
    return camada


# ------------------------------------------------------------------
# Paleta de cada bichinho (derivada das duas cores do JSON)
# ------------------------------------------------------------------
def criar_paleta(aparencia):
    principal = hex_para_rgb(aparencia["cor_principal"])
    secundaria = hex_para_rgb(aparencia["cor_secundaria"])
    corpo_escuro = luminancia(principal) < 0.3
    paleta = {
        "principal": principal,
        "secundaria": secundaria,
        # contorno: a cor secundaria bem escura, puxada para quase preto
        "contorno": misturar(escurecer(secundaria, 0.55), QUASE_PRETO, 0.6),
        "bochecha": misturar(principal, (255, 96, 140), 0.55),
    }
    if corpo_escuro:
        # corpo escuro: olhos e boca "acesos" para não sumirem
        paleta["pupila"] = misturar(clarear(secundaria, 0.55), BRANCO, 0.2)
        paleta["iris"] = clarear(secundaria, 0.15)
    else:
        paleta["pupila"] = (30, 20, 44)
        paleta["iris"] = misturar((30, 20, 44), clarear(secundaria, 0.2), 0.55)
    paleta["brilho_iris"] = clarear(secundaria, 0.45)
    return paleta


# ------------------------------------------------------------------
# CORPOS
#
# Cada função devolve um dicionário com:
#   mascara   -> conjunto de pixels (x, y) do corpo
#   olho_y    -> linha de cima dos olhos
#   vao_olhos -> espaço (em pixels) entre os dois olhos
#   boca_y    -> linha de cima da boca
#   facetado  -> True para sombrear em faces retas (cristal)
#   detalhe   -> pixels extras opcionais (ex.: o broto do 'broto')
# O "teste(dx, y)" recebe dx = distância horizontal até o eixo central.
# ------------------------------------------------------------------
def mascara_por_teste(teste):
    return {(x, y) for y in range(TAMANHO) for x in range(TAMANHO) if teste(x - EIXO, y)}


def novo_corpo(mascara, olho_y, vao_olhos, boca_y, facetado=False, detalhe=None):
    return {"mascara": mascara, "olho_y": olho_y, "vao_olhos": vao_olhos,
            "boca_y": boca_y, "facetado": facetado, "detalhe": detalhe or {}}


def corpo_gota():
    """Gota d'água: base redonda e ponta fina no topo."""
    centro_y, raio, ponta_y = 19.5, 7.4, 6.5

    def teste(dx, y):
        if y >= centro_y:
            return dx * dx + (y - centro_y) ** 2 <= raio ** 2
        t = (centro_y - y) / (centro_y - ponta_y)
        if t >= 1:
            return False
        return abs(dx) <= raio * math.cos(t * math.pi / 2) ** 1.15 + 0.15

    return novo_corpo(mascara_por_teste(teste), olho_y=16, vao_olhos=2, boca_y=22)


def corpo_blob():
    """Bolinha macia, um pouco mais larga embaixo (tipo mochi)."""
    def teste(dx, y):
        dy = y - 18.5
        raio_x = 9.4 if dy > 0 else 8.8
        return (abs(dx) / raio_x) ** 2.4 + (abs(dy) / 7.7) ** 2.4 <= 1

    return novo_corpo(mascara_por_teste(teste), olho_y=16, vao_olhos=4, boca_y=22)


def corpo_chama():
    """Chama: base redonda com três 'línguas' de fogo no topo."""
    def teste(dx, y):
        if dx * dx + (y - 19.5) ** 2 <= 7.3 ** 2:
            return True
        # língua do meio (a mais alta)
        if y < 19.5:
            t = (19.5 - y) / (19.5 - 4.0)
            if t < 1 and abs(dx) <= 5.6 * math.cos(t * math.pi / 2) ** 1.4:
                return True
        # línguas dos lados, inclinadas para fora
        if 8 < y < 18:
            t = (18 - y) / (18 - 8)
            for lado in (-1, 1):
                centro = lado * (4.6 + (18 - y) * 0.36)
                if abs(dx - centro) <= 2.8 * math.cos(t * math.pi / 2) ** 1.2:
                    return True
        return False

    return novo_corpo(mascara_por_teste(teste), olho_y=16, vao_olhos=2, boca_y=22)


def corpo_cristal():
    """Cristal lapidado: topo e base em ponta, laterais retas."""
    def teste(dx, y):
        if y < 8 or y > 26:
            return False
        if y < 13:
            largura = 1.6 + (y - 8) / 5 * (7.7 - 1.6)
        elif y <= 20:
            largura = 7.7
        else:
            largura = 7.7 - (y - 20) / 6 * (7.7 - 2.6)
        return abs(dx) <= largura

    return novo_corpo(mascara_por_teste(teste), olho_y=14, vao_olhos=2, boca_y=20,
                      facetado=True)


def corpo_nuvem():
    """Nuvem fofinha: várias bolinhas juntas."""
    bolhas = [(0, 19.0, 6.6), (-6.2, 20.6, 4.5), (6.2, 20.6, 4.5),
              (-3.4, 14.6, 4.6), (3.6, 13.8, 5.0)]

    def teste(dx, y):
        if y > 25:
            return False
        return any((dx - bx) ** 2 + (y - by) ** 2 <= r * r for bx, by, r in bolhas)

    return novo_corpo(mascara_por_teste(teste), olho_y=16, vao_olhos=4, boca_y=21)


def corpo_broto():
    """Bulbo de semente com um brotinho no topo."""
    centro_y = 19.5

    def teste(dx, y):
        if y >= centro_y:
            return (dx / 8.0) ** 2 + ((y - centro_y) / 6.6) ** 2 <= 1
        t = (centro_y - y) / (centro_y - 9.0)
        if t >= 1:
            return False
        return abs(dx) <= 8.0 * (1 - t ** 1.8) ** 0.75 + 0.2

    mascara = mascara_por_teste(teste)
    topo = min(y for x, y in mascara if x in (15, 16))
    broto = {}
    mapa = ["...XX",
            "..XXX",
            "XXX..",
            "..X..",
            "..X.."]
    folhas = pixels_do_mapa(mapa, 14, topo - 4)
    broto.update(pintar_peca(folhas, (118, 204, 84)))
    return novo_corpo(mascara, olho_y=16, vao_olhos=2, boca_y=22, detalhe=broto)


def corpo_estrela():
    """Estrela de cinco pontas bem arredondadas."""
    def teste(dx, y):
        dy = y - 17.6
        angulo = math.atan2(dx, -dy)   # 0 = apontando para cima
        return math.hypot(dx, dy) <= 7.5 + 2.1 * math.cos(5 * angulo)

    return novo_corpo(mascara_por_teste(teste), olho_y=15, vao_olhos=2, boca_y=21)


def corpo_fantasma():
    """Fantasminha: cabeça redonda e barra ondulada embaixo."""
    def teste(dx, y):
        if y <= 15:
            return dx * dx + (y - 15) ** 2 <= 8.2 ** 2
        if abs(dx) > 8.2:
            return False
        return y <= 23.6 + 1.6 * math.cos(2 * math.pi * dx / 5.5)

    return novo_corpo(mascara_por_teste(teste), olho_y=14, vao_olhos=4, boca_y=20)


CORPOS = {
    "gota": corpo_gota,
    "blob": corpo_blob,
    "chama": corpo_chama,
    "cristal": corpo_cristal,
    "nuvem": corpo_nuvem,
    "broto": corpo_broto,
    "estrela": corpo_estrela,
    "fantasma": corpo_fantasma,
}


# ------------------------------------------------------------------
# Posições do rosto (usadas por padrões, olhos e boca)
# ------------------------------------------------------------------
def x_dos_olhos(corpo):
    """Coluna da esquerda de cada olho (olhos com 4 pixels de largura)."""
    x_esquerdo = 16 - corpo["vao_olhos"] // 2 - 4
    x_direito = 31 - (x_esquerdo + 3)
    return x_esquerdo, x_direito


def area_do_rosto(corpo):
    """Retângulo dos olhos e da boca: os padrões não desenham aqui."""
    x_esq, x_dir = x_dos_olhos(corpo)
    return {(x, y) for x in range(x_esq - 1, x_dir + 5)
            for y in range(corpo["olho_y"] - 1, corpo["boca_y"] + 3)}


def topo_da_coluna(mascara, x):
    ys = [py for px, py in mascara if px == x]
    return min(ys) if ys else None


def linha_com_largura(mascara, largura):
    """Primeira linha (de cima para baixo) onde o corpo tem pelo menos
    'largura' pixels contínuos no centro. Serve para apoiar coroas e folhas."""
    colunas = range(16 - largura // 2, 16 + largura // 2)
    for y in range(TAMANHO):
        if all((x, y) in mascara for x in colunas):
            return y
    return caixa_de(mascara)[1]


# ------------------------------------------------------------------
# PADRÕES
#
# Cada função devolve (cores_base, enfeites):
#   cores_base -> {pixel: cor} antes do sombreamento
#   enfeites   -> pixels desenhados por cima, sem sombra (ex.: estrelinhas)
# ------------------------------------------------------------------
def padrao_liso(mascara, corpo, paleta, rng):
    return {p: paleta["principal"] for p in mascara}, {}


def padrao_manchas(mascara, corpo, paleta, rng):
    cores = {p: paleta["principal"] for p in mascara}
    rosto = area_do_rosto(corpo)
    candidatos = sorted(p for p in mascara if p not in rosto)
    rng.shuffle(candidatos)
    centros = []
    for cx, cy in candidatos:
        if len(centros) == 5:
            break
        if all(abs(cx - ox) + abs(cy - oy) >= 6 for ox, oy in centros):
            centros.append((cx, cy))
    for i, (cx, cy) in enumerate(centros):
        raio = 1.6 if i % 2 == 0 else 1.0
        for x, y in mascara:
            if (x - cx) ** 2 + (y - cy) ** 2 <= raio * raio and (x, y) not in rosto:
                cores[(x, y)] = paleta["secundaria"]
    return cores, {}


def padrao_listras(mascara, corpo, paleta, rng):
    """Listras de tigre entrando pelas laterais, mais finas na ponta."""
    cores = {p: paleta["principal"] for p in mascara}
    rosto = area_do_rosto(corpo)
    x0, y0, x1, y1 = caixa_de(mascara)
    for y in range(y0 + 2, y1):
        fase = (y - y0 - 2) % 4
        if fase > 1:
            continue
        comprimento = 4 if fase == 0 else 2
        linha = sorted(x for x, py in mascara if py == y)
        if len(linha) < 8:
            continue
        for x in linha[:comprimento] + linha[-comprimento:]:
            if (x, y) not in rosto:
                cores[(x, y)] = paleta["secundaria"]
    # três risquinhos na testa
    topo = linha_com_largura(mascara, 6)
    for x, altura in ((13, 2), (15, 3), (16, 3), (18, 2)):
        for y in range(topo + 1, topo + 1 + altura):
            if (x, y) in mascara and (x, y) not in rosto:
                cores[(x, y)] = paleta["secundaria"]
    return cores, {}


def padrao_gradiente(mascara, corpo, paleta, rng):
    """Degradê da cor principal (topo) para a secundária (base), com
    pontilhado para manter o visual de pixel art."""
    cores = {}
    _, y0, _, y1 = caixa_de(mascara)
    pontilhado = [[0.0, 0.5], [0.75, 0.25]]
    for x, y in mascara:
        t = (y - y0) / max(y1 - y0, 1)
        t = max(0.0, (t - 0.3) / 0.7)
        nivel = min(3, int(t * 3 + pontilhado[y % 2][x % 2]))
        cores[(x, y)] = misturar(paleta["principal"], paleta["secundaria"], nivel / 3)
    return cores, {}


def padrao_estrelado(mascara, corpo, paleta, rng):
    """Corpo com pontinhos e estrelinhas brilhando, como um céu."""
    cores = {p: paleta["principal"] for p in mascara}
    rosto = area_do_rosto(corpo)
    if luminancia(paleta["principal"]) > 0.6:
        cor_estrela = escurecer(paleta["secundaria"], 0.1)
    else:
        cor_estrela = misturar(paleta["secundaria"], BRANCO, 0.65)
    livres = sorted(p for p in mascara
                    if p not in rosto and all(v in mascara for v in vizinhos(*p)))
    rng.shuffle(livres)
    enfeites = {}
    usados = []
    for x, y in livres:
        if len(usados) == 6:
            break
        if any(abs(x - ux) + abs(y - uy) < 4 for ux, uy in usados):
            continue
        usados.append((x, y))
        enfeites[(x, y)] = BRANCO if len(usados) <= 2 else cor_estrela
        if len(usados) <= 2:   # as duas primeiras viram estrelinhas em '+'
            for v in vizinhos(x, y):
                if v not in rosto:
                    enfeites[v] = cor_estrela
    return cores, enfeites


PADROES = {
    "liso": padrao_liso,
    "manchas": padrao_manchas,
    "listras": padrao_listras,
    "gradiente": padrao_gradiente,
    "estrelado": padrao_estrelado,
}


# ------------------------------------------------------------------
# Sombreamento do corpo (luz vindo do topo-esquerda)
# ------------------------------------------------------------------
def tom_arredondado(x, y, nx, ny, mascara):
    d = 0.55 * nx + 0.85 * ny           # >0 = lado de baixo/direita
    xadrez = (x + y) % 2 == 0           # pontilhado nas transições
    borda = (x + 1, y) not in mascara or (x, y + 1) not in mascara
    if borda and d > 0.1:
        return "sombra_forte"
    if d > 0.5 or (d > 0.38 and xadrez):
        return "sombra"
    if d < -0.55 or (d < -0.45 and xadrez):
        return "luz"
    return "base"


def tom_facetado(x, y, nx, ny, mascara):
    borda = (x + 1, y) not in mascara or (x, y + 1) not in mascara
    if borda and (nx > 0 or ny > 0.3):
        return "sombra_forte"
    if ny < -0.42:                       # faces de cima
        return "luz" if nx < 0.05 else "base"
    if ny > 0.33:                        # faces de baixo
        return "base" if nx < 0.05 else "sombra"
    if nx < -0.45:
        return "luz"
    if nx > 0.45:
        return "sombra"
    return "base"


def sombrear_corpo(mascara, cores_base, caixa, facetado):
    x0, y0, x1, y1 = caixa
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = max((x1 - x0) / 2, 1), max((y1 - y0) / 2, 1)
    escolher_tom = tom_facetado if facetado else tom_arredondado
    camada = {}
    for x, y in mascara:
        cor = cores_base[(x, y)]
        tom = escolher_tom(x, y, (x - cx) / rx, (y - cy) / ry, mascara)
        if tom == "luz":
            cor = clarear(cor, 0.3)
        elif tom == "sombra":
            cor = escurecer(cor, 0.24)
        elif tom == "sombra_forte":
            cor = escurecer(cor, 0.42)
        camada[(x, y)] = cor
    # brilho especular: um "L" quase branco no alto à esquerda
    bx, by = round(cx - rx * 0.5), round(cy - ry * 0.55)
    for p in ((bx, by), (bx + 1, by), (bx, by + 1)):
        if p in mascara and all(v in mascara for v in vizinhos(*p)):
            camada[p] = clarear(cores_base[p], 0.82)
    return camada


# ------------------------------------------------------------------
# ACESSÓRIOS
#
# Cada função devolve {"atras": camada, "frente": camada, "corpo": {...}}:
#   atras  -> desenhado antes do corpo (ex.: asas)
#   frente -> desenhado depois do corpo (ex.: coroa)
#   corpo  -> pixels que passam a fazer parte do corpo (ex.: orelhas)
#             com a cor-base de cada um (None = cor do padrão)
# As posições são calculadas a partir do topo real do corpo.
# ------------------------------------------------------------------
def acessorio_vazio():
    return {"atras": {}, "frente": {}, "corpo": {}}


def acessorio_nenhum(corpo, paleta):
    return acessorio_vazio()


def acessorio_chifres(corpo, paleta):
    resultado = acessorio_vazio()
    mapa = ["X...",
            "XX..",
            "XX..",
            ".XX.",
            ".XXX",
            ".XXX"]
    pixels = set()
    for x_base, desenho in ((11, mapa), (20, espelhar(mapa))):
        topo = topo_da_coluna(corpo["mascara"], x_base)
        x0 = x_base - 2 if desenho is mapa else x_base - 1
        pixels |= pixels_do_mapa(desenho, x0, topo - 4)
    cor_osso = misturar((244, 230, 196), paleta["secundaria"], 0.15)
    resultado["frente"] = com_contorno(pintar_peca(pixels, cor_osso), paleta["contorno"])
    return resultado


def acessorio_antenas(corpo, paleta):
    resultado = acessorio_vazio()
    cor_haste = escurecer(paleta["secundaria"], 0.35)
    cor_bolinha = clarear(paleta["secundaria"], 0.35)
    camada = {}
    bolinhas = set()
    for lado in (-1, 1):
        x_base = 13 if lado < 0 else 18
        topo = topo_da_coluna(corpo["mascara"], x_base)
        haste = [(0, -1), (0, -2), (-1, -3), (-1, -4), (-2, -5)]
        for dx, dy in haste:   # do lado direito a haste inclina para a direita
            camada[(x_base + dx * -lado, topo + dy)] = cor_haste
        ponta_x = x_base - 3 if lado < 0 else x_base + 2
        bolinhas |= {(ponta_x, topo - 7), (ponta_x + 1, topo - 7),
                     (ponta_x, topo - 6), (ponta_x + 1, topo - 6)}
    bola = pintar_peca(bolinhas, cor_bolinha)
    for x, y in bolinhas:   # pontinho de brilho no canto de cada bolinha
        if (x - 1, y) not in bolinhas and (x, y - 1) not in bolinhas:
            bola[(x, y)] = BRANCO
    camada.update(com_contorno(bola, paleta["contorno"]))
    resultado["frente"] = camada
    return resultado


def acessorio_coroa(corpo, paleta):
    resultado = acessorio_vazio()
    mapa = ["X..XX..X",
            "XX.XX.XX",
            "XXXXXXXX",
            "XXXggXXX"]
    apoio = linha_com_largura(corpo["mascara"], 6)
    x0, y0 = 12, apoio - 2
    ouro = pintar_peca(pixels_do_mapa(mapa, x0, y0, "Xg"), (255, 204, 64))
    desenhar_mapa(ouro, mapa, x0, y0, {"g": (232, 58, 104)})
    ouro[(x0 + 3, y0 + 3)] = (255, 160, 190)  # brilho na joia
    resultado["frente"] = com_contorno(ouro, paleta["contorno"])
    return resultado


def acessorio_folhas(corpo, paleta):
    resultado = acessorio_vazio()
    mapa = ["XX.....XX",
            "XXX...XXX",
            ".XXX.XXX.",
            "..XXHXX..",
            "....H....",
            "....H...."]
    apoio = linha_com_largura(corpo["mascara"], 2)
    x0, y0 = 12, apoio - 4
    folhas = pintar_peca(pixels_do_mapa(mapa, x0, y0, "X"), (112, 206, 82))
    desenhar_mapa(folhas, mapa, x0, y0, {"H": (60, 140, 58)})
    resultado["frente"] = com_contorno(folhas, paleta["contorno"])
    return resultado


def acessorio_orelhas(corpo, paleta):
    """Orelhas pontudas que fazem parte do corpo (mesma cor e contorno)."""
    resultado = acessorio_vazio()
    mapa = [".X...",
            ".XX..",
            "XiX..",
            "XiiX.",
            "XiiiX",
            "XXXXX"]
    cor_interna = misturar(paleta["secundaria"], (255, 150, 180), 0.35)
    for lado in (-1, 1):
        x_base = 10 if lado < 0 else 21
        topo = topo_da_coluna(corpo["mascara"], x_base)
        desenho = mapa if lado < 0 else espelhar(mapa)
        x0 = x_base - 2
        y0 = topo - 4
        for p in pixels_do_mapa(desenho, x0, y0, "X"):
            resultado["corpo"].setdefault(p, None)
        for p in pixels_do_mapa(desenho, x0, y0, "i"):
            if p not in corpo["mascara"]:
                resultado["corpo"][p] = cor_interna
            else:
                resultado["corpo"].setdefault(p, None)
    return resultado


def acessorio_asas(corpo, paleta):
    """Asinhas de pena atrás do corpo, presas nas laterais."""
    resultado = acessorio_vazio()
    mapa = ["XX.....",
            "XXXX...",
            ".XXXXXX",
            ".XXXXXX",
            "..XXXXX",
            "...XX.."]
    mascara = corpo["mascara"]
    y0 = corpo["olho_y"] - 2
    # a asa encaixa na parte mais "funda" da lateral (linhas y0+2 a y0+4),
    # assim ela nunca fica solta, nem em corpos com pontas (estrela)
    esquerda = max(min(x for x, y in mascara if y == linha) for linha in range(y0 + 2, y0 + 5))
    direita = min(max(x for x, y in mascara if y == linha) for linha in range(y0 + 2, y0 + 5))
    cor_pena = misturar(clarear(paleta["secundaria"], 0.75), BRANCO, 0.3)
    pixels = pixels_do_mapa(mapa, esquerda - 5, y0)
    pixels |= pixels_do_mapa(espelhar(mapa), direita - 1, y0)
    asas = pintar_peca(pixels, cor_pena)
    for x, y in pixels:   # risquinhos de pena
        if y == y0 + 4 and (x % 2 == 0):
            asas[(x, y)] = escurecer(cor_pena, 0.25)
    resultado["atras"] = com_contorno(asas, paleta["contorno"])
    return resultado


def acessorio_aureola(corpo, paleta):
    """Auréola flutuando acima da cabeça."""
    resultado = acessorio_vazio()
    pixels = set(corpo["mascara"]) | set(corpo["detalhe"])
    topo = min(y for x, y in pixels if 12 <= x <= 19)
    mapa = [".AAAAAA.",
            "B......B",
            ".CCCCCC."]
    camada = {}
    desenhar_mapa(camada, mapa, 12, max(0, topo - 5),
                  {"A": (255, 246, 170), "B": (255, 214, 72), "C": (232, 162, 30)})
    resultado["frente"] = camada
    return resultado


def acessorio_raios(corpo, paleta):
    """Dois raios saindo da cabeça, como chifres elétricos."""
    resultado = acessorio_vazio()
    mapa = ["..X.",
            ".XX.",
            "XX..",
            "XXXX",
            "..XX",
            ".XX.",
            ".X.."]
    pixels = set()
    for lado in (-1, 1):
        x_base = 11 if lado < 0 else 20
        topo = topo_da_coluna(corpo["mascara"], x_base)
        desenho = mapa if lado < 0 else espelhar(mapa)
        x0 = x_base - 2 if lado < 0 else x_base - 1
        pixels |= pixels_do_mapa(desenho, x0, topo - 5)
    raios = {p: (255, 226, 72) for p in pixels}
    for x, y in pixels:   # miolo mais claro, quase branco
        if (x - 1, y) in pixels and (x + 1, y) not in pixels:
            raios[(x, y)] = (255, 250, 200)
    resultado["frente"] = com_contorno(raios, paleta["contorno"])
    return resultado


ACESSORIOS = {
    "nenhum": acessorio_nenhum,
    "chifres": acessorio_chifres,
    "antenas": acessorio_antenas,
    "coroa": acessorio_coroa,
    "folhas": acessorio_folhas,
    "orelhas": acessorio_orelhas,
    "asas": acessorio_asas,
    "aureola": acessorio_aureola,
    "raios": acessorio_raios,
}


# ------------------------------------------------------------------
# OLHOS
#
# Mapas do olho ESQUERDO. Letras:
#   '#' pupila   'w' brilho branco   'i' íris (vira brilho extra nos raros+)
#   'c' íris colorida (olhos brilhantes)
# O olho direito é o espelho, mas o brilho continua do lado esquerdo
# (a luz vem do mesmo lugar para os dois olhos).
# ------------------------------------------------------------------
def espelhar_olho(mapa):
    resultado = []
    for y, linha in enumerate(mapa):
        nova = ""
        for x, letra in enumerate(linha[::-1]):
            if letra in "wic":
                letra = "#"
            if letra == "#" and mapa[y][x] in "wic":
                letra = mapa[y][x]
            nova += letra
        resultado.append(nova)
    return resultado


def desenhar_par_de_olhos(camada, mapa, corpo, paleta, brilho_extra, dy=0):
    x_esq, x_dir = x_dos_olhos(corpo)
    cores = {"#": paleta["pupila"], "w": BRANCO,
             "i": BRANCO if brilho_extra else paleta["iris"],
             "c": paleta["brilho_iris"]}
    desenhar_mapa(camada, mapa, x_esq, corpo["olho_y"] + dy, cores)
    desenhar_mapa(camada, espelhar_olho(mapa), x_dir, corpo["olho_y"] + dy, cores)


def desenhar_bochechas(camada, corpo, paleta, linha):
    x_esq, x_dir = x_dos_olhos(corpo)
    for x in (x_esq - 1, x_esq, x_dir + 3, x_dir + 4):
        if (x, linha) in corpo["mascara"]:
            camada[(x, linha)] = paleta["bochecha"]


def olhos_redondos(camada, corpo, paleta, brilho_extra):
    mapa = [".##.",
            "#ww#",
            "#w##",
            "##i#",
            ".##."]
    desenhar_par_de_olhos(camada, mapa, corpo, paleta, brilho_extra)


def olhos_sonolentos(camada, corpo, paleta, brilho_extra):
    mapa = ["....",
            "....",
            "####",
            "#w#i",
            ".##."]
    desenhar_par_de_olhos(camada, mapa, corpo, paleta, brilho_extra)
    desenhar_bochechas(camada, corpo, paleta, corpo["olho_y"] + 5)


def olhos_bravos(camada, corpo, paleta, brilho_extra):
    mapa = ["##..",
            ".###",
            "#w##",
            "##i#",
            ".##."]
    desenhar_par_de_olhos(camada, mapa, corpo, paleta, brilho_extra)


def olhos_brilhantes(camada, corpo, paleta, brilho_extra):
    mapa = [".##.",
            "#wc#",
            "#cc#",
            "#cw#",
            ".##."]
    desenhar_par_de_olhos(camada, mapa, corpo, paleta, brilho_extra)
    if brilho_extra:   # estrelinha extra ao lado
        x_esq, _ = x_dos_olhos(corpo)
        camada[(x_esq - 1, corpo["olho_y"] - 1)] = BRANCO


def olhos_ciclope(camada, corpo, paleta, brilho_extra):
    """Um olho grande no meio do rosto."""
    mapa = [".####.",
            "#wwcc#",
            "#wppC#",
            "#cppC#",
            "#ccCi#",
            ".####."]
    # a pupila do ciclope é sempre escura e a íris colorida, para ler bem
    # tanto em corpo claro quanto escuro
    iris = misturar(paleta["secundaria"], paleta["brilho_iris"], 0.45)
    if abs(luminancia(iris) - luminancia(paleta["principal"])) < 0.15:
        iris = misturar(iris, (90, 200, 255), 0.5)   # garante contraste com o corpo
    cores = {"#": QUASE_PRETO, "w": BRANCO, "c": iris, "C": escurecer(iris, 0.3),
             "p": QUASE_PRETO, "i": BRANCO if brilho_extra else escurecer(iris, 0.3)}
    desenhar_mapa(camada, mapa, 13, corpo["olho_y"] - 1, cores)


def olhos_felizes(camada, corpo, paleta, brilho_extra):
    """Olhinhos fechados de alegria (^ ^) com bochechas."""
    mapa = ["....",
            ".##.",
            "#..#",
            "#..#"]
    desenhar_par_de_olhos(camada, mapa, corpo, paleta, brilho_extra)
    desenhar_bochechas(camada, corpo, paleta, corpo["olho_y"] + 5)
    if brilho_extra:
        x_esq, x_dir = x_dos_olhos(corpo)
        camada[(x_esq - 1, corpo["olho_y"])] = BRANCO
        camada[(x_dir + 4, corpo["olho_y"])] = BRANCO


OLHOS = {
    "redondos": olhos_redondos,
    "sonolentos": olhos_sonolentos,
    "bravos": olhos_bravos,
    "brilhantes": olhos_brilhantes,
    "ciclope": olhos_ciclope,
    "felizes": olhos_felizes,
}


# ------------------------------------------------------------------
# BOCAS (centralizadas no eixo; '#' = traço, 'r' = dentro da boca,
# 'w' = dente, 'p' = língua)
# ------------------------------------------------------------------
def desenhar_boca(camada, mapa, corpo, paleta):
    largura = len(mapa[0])
    cores = {"#": paleta["pupila"], "r": (150, 40, 70), "w": BRANCO,
             "p": (255, 112, 150), "P": (214, 70, 110)}
    desenhar_mapa(camada, mapa, 16 - largura // 2, corpo["boca_y"], cores)


def boca_sorriso(camada, corpo, paleta):
    desenhar_boca(camada, ["#..#",
                           ".##."], corpo, paleta)


def boca_aberta(camada, corpo, paleta):
    desenhar_boca(camada, [".##.",
                           "#rr#",
                           ".##."], corpo, paleta)


def boca_dentes(camada, corpo, paleta):
    desenhar_boca(camada, ["#....#",
                           ".####.",
                           ".w..w."], corpo, paleta)


def boca_neutra(camada, corpo, paleta):
    desenhar_boca(camada, ["##"], corpo, paleta)


def boca_lingua(camada, corpo, paleta):
    desenhar_boca(camada, ["#..#",
                           ".##.",
                           ".pP."], corpo, paleta)


BOCAS = {
    "sorriso": boca_sorriso,
    "aberta": boca_aberta,
    "dentes": boca_dentes,
    "neutra": boca_neutra,
    "lingua": boca_lingua,
}


# ------------------------------------------------------------------
# EFEITOS DO ELEMENTO (pequenos desenhos espalhados em volta)
# ------------------------------------------------------------------
# Cantos de cima à esquerda onde os efeitos podem aparecer (no ar)
VAGAS_NO_AR = [(2, 4), (26, 3), (1, 11), (28, 10), (2, 18), (28, 18),
               (7, 1), (21, 1), (5, 23), (25, 23)]
# Vagas no chão (para pegadas)
VAGAS_NO_CHAO = [(1, 26), (26, 26), (3, 27), (24, 27)]

ENFEITES_ELEMENTO = {
    "natureza": {
        "formas": [[".ag", "aga", "g.."], ["ga.", "aga", "..g"], ["y"]],
        "cores": {"a": (176, 236, 112), "g": (84, 170, 68), "y": (236, 244, 140)},
    },
    "fogo": {
        "formas": [[".r.", "ror", "oyo", ".o."], ["o"], ["y"], [".r.", "ryr", ".r."]],
        "cores": {"r": (232, 72, 44), "o": (255, 150, 44), "y": (255, 232, 120)},
    },
    "agua": {
        "formas": [[".b.", "bwb", "bbB", ".B."], [".c.", "c.c", ".c."], ["c"]],
        "cores": {"b": (110, 190, 255), "B": (58, 128, 228), "w": BRANCO,
                  "c": (176, 226, 255)},
    },
    "eletrico": {
        "formas": [["..y", ".y.", "yyy", ".y.", "y.."], [".y.", "ywy", ".y."], ["w"]],
        "cores": {"y": (255, 226, 70), "w": (255, 255, 210)},
    },
    "mistico": {
        "formas": [["..p..", "..p..", "ppwpp", "..p..", "..p.."],
                   [".m.", "m.m", ".m."], [".p.", "pwp", ".p."]],
        "cores": {"p": (232, 152, 255), "m": (162, 112, 255), "w": (255, 240, 255)},
    },
    "fera": {
        # marcas de garra e patinhas
        "formas": [["t.t..", ".t.t.", "..t.t"], ["..t.t", ".t.t.", "t.t.."], ["t.t", ".T."]],
        "pegada": ["t.t.t", ".....", ".TTT.", ".TTT."],
        "cores": {"t": (214, 172, 124), "T": (160, 112, 72)},
    },
}


def espalhar_formas(rng, formas, cores, vagas, ocupado, quantidade):
    """Coloca 'quantidade' formas em vagas livres (sem encostar no bichinho)."""
    vagas = list(vagas)
    rng.shuffle(vagas)
    colocadas = []
    for x0, y0 in vagas:
        if len(colocadas) == quantidade:
            break
        forma = rng.choice(formas)
        pixels = pixels_do_mapa(forma, x0, y0, "".join(cores))
        if pixels and not (pixels & ocupado) and all(dentro(*p) for p in pixels):
            colocadas.append((forma, x0, y0, rng.random()))
    return colocadas


def efeitos_do_elemento(elemento, rng, ocupado, quantidade, quadro, total):
    dados = ENFEITES_ELEMENTO.get(elemento)
    camada = {}
    if not dados:
        return camada
    colocadas = espalhar_formas(rng, dados["formas"], dados["cores"],
                                VAGAS_NO_AR, ocupado, quantidade)
    for forma, x0, y0, fase in colocadas:
        subida = 0
        if total > 1:   # no GIF as partículas sobem devagar e recomeçam
            subida = int(((quadro / total) + fase) * 4) % 4
        desenhar_mapa(camada, forma, x0, y0 - subida, dados["cores"])
    if "pegada" in dados:
        pegadas = espalhar_formas(rng, [dados["pegada"]], dados["cores"],
                                  VAGAS_NO_CHAO, ocupado, 1)
        for forma, x0, y0, _ in pegadas:
            desenhar_mapa(camada, forma, x0, y0, dados["cores"])
    return camada


# ------------------------------------------------------------------
# EFEITOS DA RARIDADE
# ------------------------------------------------------------------
def desenhar_sombra(caixa_corpo, subida, modo_gif):
    """Sombra elíptica no chão (menor quando o bichinho sobe)."""
    x0, _, x1, _ = caixa_corpo
    meia_largura = (x1 - x0) / 2 * 0.62 - subida * 0.5
    camada = {}
    for y in (CHAO_Y, CHAO_Y + 1):
        for x in range(TAMANHO):
            dx = (x - EIXO) / meia_largura
            dy = (y - CHAO_Y - 0.5) / 1.1
            if dx * dx + dy * dy <= 1:
                if modo_gif:   # GIF não tem meia transparência: usamos xadrez
                    if (x + y) % 2 == 0:
                        camada[(x, y)] = (40, 30, 56)
                else:
                    camada[(x, y)] = (24, 14, 36, 80)
    return camada


def cor_do_contorno_raro(raridade, x, y, quadro, total):
    if raridade == "mitico":
        return arco_iris((x + y) / 24 + quadro / total)
    return COR_RARIDADE[raridade]


def desenhar_aura(silhueta, raridade, quadro, total, modo_gif):
    """Brilho suave em volta do bichinho (épico, lendário e mítico)."""
    camada = {}
    aneis = aneis_em_volta(silhueta, 3)
    alfas = [120, 64, 26]
    for numero, anel in enumerate(aneis):
        for x, y in anel:
            if raridade == "mitico":
                cor = arco_iris((x - y) / 30 + quadro / total)
            elif raridade == "lendario":
                cor = (255, 206, 72)
            else:
                cor = (176, 104, 255)
            if modo_gif:
                # GIF não tem meia transparência: a aura vira pontinhos que
                # cintilam (mudam de lugar a cada quadro)
                if numero < 2 and (x * 7 + y * 13 + quadro * 3) % (5 + numero * 3) == 0:
                    camada[(x, y)] = cor
            else:
                camada[(x, y)] = com_alfa(cor, alfas[numero])
    return camada


def brilhos_da_raridade(raridade, rng, ocupado, quadro, total):
    """Estrelinhas de destaque: raro (brancas), lendário (douradas),
    mítico (arco-íris, piscando)."""
    if raridade == "raro":
        formas, quantidade = [[".w.", "wWw", ".w."]], 2
        cores = {"w": (190, 222, 255), "W": BRANCO}
    elif raridade == "lendario":
        formas, quantidade = [["..g..", ".gWg.", "gWWWg", ".gWg.", "..g.."],
                              [".g.", "gWg", ".g."], ["W"]], 4
        cores = {"g": (255, 196, 40), "W": (255, 246, 196)}
    elif raridade == "mitico":
        formas, quantidade = [["..g..", "..g..", "ggWgg", "..g..", "..g.."],
                              [".g.", "gWg", ".g."]], 4
        cores = {"g": (255, 255, 255), "W": BRANCO}
    else:
        return {}
    camada = {}
    colocadas = espalhar_formas(rng, formas, cores, VAGAS_NO_AR, ocupado, quantidade)
    for numero, (forma, x0, y0, fase) in enumerate(colocadas):
        if raridade == "mitico":
            # cada estrela pisca em um momento diferente
            momento = (quadro / total + fase) % 1
            if momento > 0.6:
                continue
            cores = {"g": arco_iris(fase + quadro / total), "W": BRANCO}
            if momento < 0.15 or momento > 0.45:
                forma = ["W"] if len(forma) > 3 else forma
                x0, y0 = x0 + 2, y0 + 2
        desenhar_mapa(camada, forma, x0, y0, cores)
    return camada


# ------------------------------------------------------------------
# Montagem do bichinho
# ------------------------------------------------------------------
def validar_aparencia(aparencia):
    opcoes = {"corpo": CORPOS, "olhos": OLHOS, "boca": BOCAS,
              "acessorio": ACESSORIOS, "padrao": PADROES}
    for campo, permitidos in opcoes.items():
        valor = aparencia.get(campo)
        if valor not in permitidos:
            raise ValueError(f"aparencia.{campo} = {valor!r} não é suportado "
                             f"(use um de: {', '.join(permitidos)})")


def desenhar_personagem(corpo, aparencia, paleta, raridade, rng):
    """Junta corpo, padrão, sombra, contorno, acessório e rosto."""
    caixa = caixa_de(corpo["mascara"])
    acessorio = ACESSORIOS[aparencia["acessorio"]](corpo, paleta)

    # 1) corpo (com orelhas, se houver) + padrão + sombreamento
    mascara = set(corpo["mascara"]) | set(acessorio["corpo"])
    cores_base, enfeites = PADROES[aparencia["padrao"]](mascara, corpo, paleta, rng)
    for p, cor in acessorio["corpo"].items():
        if cor is not None:
            cores_base[p] = cor
    pele = sombrear_corpo(mascara, cores_base, caixa, corpo["facetado"])
    pele.update(enfeites)

    # 2) empilha as camadas: o que vem depois fica por cima
    personagem = {}
    personagem.update(acessorio["atras"])
    personagem.update(com_contorno(pele, paleta["contorno"]))
    if corpo["detalhe"] and aparencia["acessorio"] not in ("coroa", "folhas"):
        personagem.update(com_contorno(corpo["detalhe"], paleta["contorno"]))
    personagem.update(acessorio["frente"])

    # 3) rosto
    rosto = {}
    brilho_extra = raridade in ("raro", "epico", "lendario", "mitico")
    OLHOS[aparencia["olhos"]](rosto, corpo, paleta, brilho_extra)
    BOCAS[aparencia["boca"]](rosto, corpo, paleta)
    personagem.update(rosto)
    return personagem


def desenhar_quadro(bichinho, quadro=0, total=1):
    """Desenha um quadro 32x32 do bichinho (total > 1 = animação do mítico)."""
    aparencia = bichinho["aparencia"]
    validar_aparencia(aparencia)
    raridade = bichinho.get("raridade", "comum")
    elemento = bichinho.get("elemento", "")
    modo_gif = total > 1

    # O mesmo id sempre gera os mesmos sorteios (manchas, partículas...)
    rng = random.Random(bichinho["id"])
    paleta = criar_paleta(aparencia)
    corpo = CORPOS[aparencia["corpo"]]()
    personagem = desenhar_personagem(corpo, aparencia, paleta, raridade, rng)

    # flutuação: no GIF o bichinho sobe e desce de 0 a 3 pixels
    subida = 0
    if modo_gif:
        subida = round(1.5 - 1.5 * math.cos(2 * math.pi * quadro / total))
    silhueta_parada = set(personagem)
    personagem = mover(personagem, 0, -subida)
    silhueta = set(personagem)

    # área onde efeitos não podem ficar (bichinho + folga, em qualquer altura)
    ocupado = set()
    for anel in aneis_em_volta(silhueta_parada, 2):
        ocupado |= anel
    ocupado |= silhueta_parada
    for desloc in range(1, 4):
        ocupado |= {(x, y - desloc) for x, y in ocupado}

    rng_efeitos = random.Random(bichinho["id"] + "/efeitos")
    contorno_raro = contorno_de(silhueta) if COR_RARIDADE.get(raridade) or raridade == "mitico" else set()

    tela = {}
    if raridade in ("epico", "lendario", "mitico"):
        tela.update(desenhar_aura(silhueta | contorno_raro, raridade, quadro, total, modo_gif))
    tela.update(desenhar_sombra(caixa_de(corpo["mascara"]), subida, modo_gif))
    quantidade = 4 if raridade in ("lendario", "mitico") else 3
    tela.update(efeitos_do_elemento(elemento, rng_efeitos, ocupado, quantidade, quadro, total))
    for x, y in contorno_raro:
        tela[(x, y)] = cor_do_contorno_raro(raridade, x, y, quadro, total)
    tela.update(personagem)
    brilhos = brilhos_da_raridade(raridade, rng_efeitos, ocupado, quadro, total)
    tela.update({p: c for p, c in brilhos.items() if p not in tela or len(tela[p]) == 4})
    return camada_para_imagem(tela)


def camada_para_imagem(camada):
    imagem = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
    pixels = imagem.load()
    for (x, y), cor in camada.items():
        pixels[x, y] = cor if len(cor) == 4 else (cor[0], cor[1], cor[2], 255)
    return imagem


def ampliar(imagem):
    return imagem.resize((TAMANHO * ESCALA, TAMANHO * ESCALA), Image.NEAREST)


# ------------------------------------------------------------------
# Salvando os arquivos
# ------------------------------------------------------------------
def quadro_com_paleta(imagem):
    """Converte um quadro RGBA em imagem de paleta para GIF.
    O índice 255 da paleta é a cor transparente."""
    convertida = Image.new("P", imagem.size, 255)
    indices = {}
    paleta = []
    origem = imagem.load()
    destino = convertida.load()
    for y in range(imagem.height):
        for x in range(imagem.width):
            r, g, b, a = origem[x, y]
            if a < 128:
                continue
            cor = (r, g, b)
            if cor not in indices:
                if len(indices) < 255:
                    indices[cor] = len(indices)
                    paleta.extend(cor)
                else:   # paleta cheia: usa a cor mais parecida
                    cor = min(indices, key=lambda c: sum((c[i] - cor[i]) ** 2 for i in range(3)))
            destino[x, y] = indices[cor]
    paleta.extend([0, 0, 0] * (256 - len(paleta) // 3))
    convertida.putpalette(paleta)
    convertida.info["transparency"] = 255
    return convertida


def gerar_sprite(bichinho, caminho):
    """Desenha o bichinho e salva em 'caminho' (PNG ou GIF animado)."""
    if bichinho.get("raridade") == "mitico":
        quadros = [quadro_com_paleta(ampliar(desenhar_quadro(bichinho, q, QUADROS_GIF)))
                   for q in range(QUADROS_GIF)]
        quadros[0].save(caminho, save_all=True, append_images=quadros[1:],
                        duration=DURACAO_QUADRO, loop=0, disposal=2,
                        transparency=255, optimize=False)
    else:
        ampliar(desenhar_quadro(bichinho)).save(caminho)


def caminho_sprite(bichinho):
    """Gera o sprite (se ainda não existir) e devolve o caminho do arquivo."""
    os.makedirs(PASTA_SPRITES, exist_ok=True)
    extensao = ".gif" if bichinho.get("raridade") == "mitico" else ".png"
    caminho = os.path.join(PASTA_SPRITES, bichinho["id"] + extensao)
    if not os.path.exists(caminho):
        gerar_sprite(bichinho, caminho)
    return caminho


# ------------------------------------------------------------------
# Galeria (todos os sprites numa imagem só, para conferir)
# ------------------------------------------------------------------
def carregar_fonte(tamanho):
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


def montar_galeria(bichinhos, caminho_saida, colunas=8, celula=128):
    altura_texto = 18
    linhas = max(1, math.ceil(len(bichinhos) / colunas))
    galeria = Image.new("RGBA", (colunas * celula, linhas * (celula + altura_texto)),
                        (43, 45, 49, 255))
    desenho = ImageDraw.Draw(galeria)
    fonte = carregar_fonte(11)
    for i, bichinho in enumerate(bichinhos):
        x = (i % colunas) * celula
        y = (i // colunas) * (celula + altura_texto)
        if (i + i // colunas) % 2 == 0:   # fundo quadriculado leve
            desenho.rectangle([x, y, x + celula - 1, y + celula + altura_texto - 1],
                              fill=(49, 51, 56, 255))
        with Image.open(caminho_sprite(bichinho)) as arquivo:
            arquivo.seek(0)
            sprite = arquivo.convert("RGBA").resize((celula, celula), Image.NEAREST)
        galeria.alpha_composite(sprite, (x, y))
        cor = COR_RARIDADE.get(bichinho.get("raridade")) or (230, 230, 230)
        if bichinho.get("raridade") == "mitico":
            cor = (255, 150, 230)
        desenho.text((x + 4, y + celula + 2), bichinho["id"][:22], fill=cor, font=fonte)
    galeria.save(caminho_saida)
    return caminho_saida


# ------------------------------------------------------------------
# Execução direta: python sprites.py [caminho_json]
# ------------------------------------------------------------------
def main():
    caminho_json = sys.argv[1] if len(sys.argv) > 1 else ARQUIVO_CATALOGO
    with open(caminho_json, encoding="utf-8") as arquivo:
        bichinhos = json.load(arquivo)["bichinhos"]
    os.makedirs(PASTA_SPRITES, exist_ok=True)

    gerados = []
    for bichinho in bichinhos:
        extensao = ".gif" if bichinho.get("raridade") == "mitico" else ".png"
        caminho = os.path.join(PASTA_SPRITES, bichinho["id"] + extensao)
        try:
            gerar_sprite(bichinho, caminho)   # sempre redesenha
            gerados.append(bichinho)
        except (KeyError, ValueError) as erro:
            print(f"Erro em {bichinho.get('id')}: {erro}")

    galeria = montar_galeria(gerados, os.path.join(PASTA_SPRITES, "_galeria.png"))
    print(f"{len(gerados)} sprites gerados em {PASTA_SPRITES}")
    print(f"Galeria: {galeria}")


if __name__ == "__main__":
    main()
