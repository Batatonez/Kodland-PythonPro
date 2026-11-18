"""Visão: o YOLO olha a foto, acha o objeto e diz qual elemento ele define."""

import os
from dataclasses import dataclass

from PIL import Image, ImageDraw
from ultralytics import YOLO

# Pasta onde está este arquivo (raiz do projeto)
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
CAMINHO_MODELO = os.path.join(PASTA_PROJETO, "dados", "yolo11n.pt")
PASTA_TEMP = os.path.join(PASTA_PROJETO, "dados", "temp")

# Só aceitamos detecções com pelo menos 35% de certeza
CONFIANCA_MINIMA = 0.35

# Classes do COCO (o que o YOLO pré-treinado conhece) -> elemento do bichinho.
# Classes que não estão aqui (ex.: "person") são ignoradas.
ELEMENTO_POR_CLASSE: dict[str, str] = {
    # natureza
    "potted plant": "natureza",
    "broccoli": "natureza",
    "carrot": "natureza",
    "apple": "natureza",
    "orange": "natureza",
    "banana": "natureza",
    # fogo
    "pizza": "fogo",
    "hot dog": "fogo",
    "donut": "fogo",
    "cake": "fogo",
    "sandwich": "fogo",
    "oven": "fogo",
    "microwave": "fogo",
    "toaster": "fogo",
    # agua
    "cup": "agua",
    "bottle": "agua",
    "wine glass": "agua",
    "bowl": "agua",
    "sink": "agua",
    "umbrella": "agua",
    # eletrico
    "cell phone": "eletrico",
    "laptop": "eletrico",
    "tv": "eletrico",
    "remote": "eletrico",
    "keyboard": "eletrico",
    "mouse": "eletrico",
    "hair drier": "eletrico",
    "clock": "eletrico",
    # mistico
    "book": "mistico",
    "vase": "mistico",
    "teddy bear": "mistico",
    "scissors": "mistico",
    "kite": "mistico",
    # fera
    "cat": "fera",
    "dog": "fera",
    "bird": "fera",
    "horse": "fera",
    "sheep": "fera",
    "cow": "fera",
    "elephant": "fera",
    "bear": "fera",
    "zebra": "fera",
    "giraffe": "fera",
}


@dataclass
class Deteccao:
    classe: str          # nome do objeto, ex.: "cat"
    elemento: str        # elemento do bichinho, ex.: "fera"
    confianca: float     # de 0 a 1
    # Posição da caixa na foto: (x1, y1, x2, y2). Opcional, usado para desenhar.
    caixa: tuple | None = None


_modelo_yolo = None


def _modelo() -> YOLO:
    """Carrega o modelo YOLO só na primeira vez que for preciso."""
    global _modelo_yolo
    if _modelo_yolo is None:
        os.makedirs(os.path.dirname(CAMINHO_MODELO), exist_ok=True)
        # Se o arquivo não existir, o ultralytics baixa sozinho
        _modelo_yolo = YOLO(CAMINHO_MODELO)
    return _modelo_yolo


def detectar(caminho_imagem: str) -> list[Deteccao]:
    """Devolve os objetos da foto que têm elemento, do mais certo para o menos certo."""
    modelo = _modelo()
    resultado = modelo(caminho_imagem, conf=CONFIANCA_MINIMA, verbose=False)[0]

    deteccoes = []
    caixas = resultado.boxes.xyxy.tolist()
    confiancas = resultado.boxes.conf.tolist()
    indices = resultado.boxes.cls.tolist()

    for caixa, confianca, indice in zip(caixas, confiancas, indices):
        classe = modelo.names[int(indice)]
        if classe not in ELEMENTO_POR_CLASSE:
            continue  # objeto sem elemento (ex.: pessoa)
        deteccoes.append(
            Deteccao(
                classe=classe,
                elemento=ELEMENTO_POR_CLASSE[classe],
                confianca=float(confianca),
                caixa=tuple(caixa),
            )
        )

    deteccoes.sort(key=lambda d: d.confianca, reverse=True)
    return deteccoes


def melhor_deteccao(caminho_imagem: str) -> Deteccao | None:
    """Devolve a detecção mais confiável, ou None se não achou nada útil."""
    deteccoes = detectar(caminho_imagem)
    if not deteccoes:
        return None
    return deteccoes[0]


def desenhar_deteccoes(caminho_imagem: str, deteccoes: list[Deteccao]) -> str:
    """Salva uma cópia da foto com caixas e rótulos. Devolve o caminho da cópia."""
    os.makedirs(PASTA_TEMP, exist_ok=True)

    imagem = Image.open(caminho_imagem).convert("RGB")
    desenho = ImageDraw.Draw(imagem)

    for d in deteccoes:
        if d.caixa is None:
            continue  # sem posição, não tem como desenhar
        x1, y1, x2, y2 = d.caixa
        desenho.rectangle([x1, y1, x2, y2], outline="red", width=3)

        # Rótulo em cima da caixa, ex.: "cat (fera) 87%"
        texto = f"{d.classe} ({d.elemento}) {round(d.confianca * 100)}%"
        topo = max(0, y1 - 14)
        fundo = desenho.textbbox((x1 + 2, topo), texto)
        desenho.rectangle(
            [fundo[0] - 2, fundo[1] - 2, fundo[2] + 2, fundo[3] + 2], fill="red"
        )
        desenho.text((x1 + 2, topo), texto, fill="white")

    nome = os.path.splitext(os.path.basename(caminho_imagem))[0] + "_deteccoes.png"
    caminho_saida = os.path.join(PASTA_TEMP, nome)
    imagem.save(caminho_saida)
    return caminho_saida
