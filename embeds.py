"""Montagem dos embeds (as "caixinhas" coloridas que o bot manda no Discord)."""
import discord

import titulos
from catalogo import ELEMENTOS, RARIDADES, carregar, filtrar, por_id
from visao import ELEMENTO_POR_CLASSE

COR_PADRAO = discord.Color.from_rgb(88, 101, 242)
COR_SUCESSO = discord.Color.from_rgb(46, 139, 87)
COR_AVISO = discord.Color.from_rgb(204, 136, 0)
COR_ERRO = discord.Color.from_rgb(178, 34, 34)

# Emoji que aparece antes do nome, para reconhecer a raridade de longe.
EMOJI_RARIDADE = {
    "comum": "⚪",
    "incomum": "🟢",
    "raro": "🔵",
    "epico": "🟣",
    "lendario": "🟡",
    "mitico": "🌈",
}


# ---------- pequenos ajudantes de texto ----------

def cor_raridade(raridade):
    """Cor do embed de acordo com a raridade (definida em catalogo.RARIDADES)."""
    return discord.Color(RARIDADES[raridade]["cor"])


def texto_raridade(raridade):
    """Ex.: "🟡 Lendário"."""
    return f"{EMOJI_RARIDADE[raridade]} {RARIDADES[raridade]['nome']}"


def texto_elemento(elemento):
    """Ex.: "🔥 Fogo"."""
    dados = ELEMENTOS[elemento]
    return f"{dados['emoji']} {dados['nome']}"


def ordenar_por_raridade(bichinhos):
    """Mais raro primeiro; dentro da mesma raridade, em ordem alfabética."""
    return sorted(bichinhos, key=lambda b: (-RARIDADES[b["raridade"]]["ordem"], b["nome"]))


def formatar_tempo(segundos):
    """Ex.: 75 -> "1 min 15 s"."""
    segundos = max(1, round(segundos))
    minutos, segundos = divmod(segundos, 60)
    if minutos == 0:
        return f"{segundos} s"
    if segundos == 0:
        return f"{minutos} min"
    return f"{minutos} min {segundos} s"


def embed_mensagem(titulo, descricao, cor=COR_PADRAO):
    """Embed simples com título e texto."""
    return discord.Embed(title=titulo, description=descricao, color=cor)


# ---------- captura e ficha ----------

def embed_captura(bichinho, novo, titulo="Você encontrou um bichinho!", deteccao=None,
                  com_bonus=False, nome_sprite=None, nome_foto=None):
    """Embed do bichinho que acabou de ser sorteado (capturar, roll, comprar...).

    nome_sprite / nome_foto são os nomes dos arquivos anexados na mensagem.
    """
    nome = f"{bichinho['nome']}  ✨ NOVO!" if novo else bichinho["nome"]
    embed = discord.Embed(title=titulo, description=f"## {nome}\n*{bichinho['descricao']}*",
                          color=cor_raridade(bichinho["raridade"]))
    embed.add_field(name="Raridade", value=texto_raridade(bichinho["raridade"]))
    embed.add_field(name="Elemento", value=texto_elemento(bichinho["elemento"]))

    if deteccao is not None:
        embed.add_field(name="Detectei", value=f"{deteccao.classe} ({deteccao.confianca:.0%})")
    if com_bonus:
        embed.add_field(name="Bônus de foto nítida! 🎯",
                        value="Chances maiores de Épico, Lendário e Mítico.", inline=False)

    # "attachment://arquivo" faz o embed usar a imagem anexada na mesma mensagem.
    if nome_sprite:
        embed.set_image(url=f"attachment://{nome_sprite}")
    if nome_foto:
        embed.set_thumbnail(url=f"attachment://{nome_foto}")
    return embed


def embed_ficha(bichinho, quantidade, descoberto, nome_sprite=None):
    """Ficha de um bichinho para o comando ver."""
    embed = discord.Embed(title=bichinho["nome"], description=f"*{bichinho['descricao']}*",
                          color=cor_raridade(bichinho["raridade"]))
    embed.add_field(name="Raridade", value=texto_raridade(bichinho["raridade"]))
    embed.add_field(name="Elemento", value=texto_elemento(bichinho["elemento"]))
    embed.add_field(name="Você tem", value=str(quantidade))
    if not descoberto:
        embed.set_footer(text="Você ainda não encontrou este bichinho.")
    if nome_sprite:
        embed.set_image(url=f"attachment://{nome_sprite}")
    return embed


def embed_nada_detectado():
    """Explica que nenhum objeto útil apareceu na foto e dá exemplos."""
    embed = embed_mensagem(
        "Nenhum bichinho por aqui... 🔍",
        "Não reconheci nenhum objeto que tenha elemento nessa foto.\n"
        "Tente fotografar um destes objetos (bem iluminado e centralizado):",
        COR_AVISO,
    )
    for elemento in ELEMENTOS:
        exemplos = [classe for classe, e in ELEMENTO_POR_CLASSE.items() if e == elemento]
        embed.add_field(name=texto_elemento(elemento), value=", ".join(exemplos[:5]), inline=False)
    return embed


# ---------- inventário ----------

def linhas_inventario(inventario):
    """Transforma {id: quantidade} em linhas de texto, da mais rara para a mais comum."""
    bichinhos = [por_id(bichinho_id) for bichinho_id in inventario]
    bichinhos = [b for b in bichinhos if b is not None]  # ignora ids que sumiram do JSON

    linhas = []
    for b in ordenar_por_raridade(bichinhos):
        emoji_elemento = ELEMENTOS[b["elemento"]]["emoji"]
        linhas.append(f"{EMOJI_RARIDADE[b['raridade']]} **{b['nome']}** x{inventario[b['id']]} {emoji_elemento}")
    return linhas


def paginas_inventario(nome_dono, inventario, por_pagina=15):
    """Lista de embeds (uma por página) com o inventário."""
    linhas = linhas_inventario(inventario)
    if not linhas:
        return [embed_mensagem(f"Inventário de {nome_dono}",
                               "Nenhum bichinho ainda. Use `!capturar` com uma foto ou `!roll`!")]

    total_bichinhos = sum(inventario.values())
    paginas = []
    for inicio in range(0, len(linhas), por_pagina):
        embed = embed_mensagem(f"Inventário de {nome_dono}", "\n".join(linhas[inicio:inicio + por_pagina]))
        paginas.append(embed)
    for numero, embed in enumerate(paginas, start=1):
        embed.set_footer(text=f"Página {numero} de {len(paginas)} | "
                              f"{len(linhas)} espécies | {total_bichinhos} bichinhos")
    return paginas


# ---------- index, ranking, moedas, missão ----------

def _contagem(descobertos, raridade=None, elemento=None):
    """Texto "descobertos/total" para um filtro de raridade e/ou elemento."""
    todos = filtrar(raridade=raridade, elemento=elemento)
    achados = sum(1 for b in todos if b["id"] in descobertos)
    return f"{achados}/{len(todos)}"


def embed_index(nome_dono, descobertos, elemento=None):
    """Progresso da coleção por raridade e por elemento."""
    titulo = f"Index de {nome_dono}"
    if elemento:
        titulo += f" - {texto_elemento(elemento)}"
    embed = embed_mensagem(titulo, f"Total descoberto: **{_contagem(descobertos, elemento=elemento)}**")

    por_raridade = [f"{texto_raridade(r)}: {_contagem(descobertos, r, elemento)}" for r in RARIDADES]
    embed.add_field(name="Por raridade", value="\n".join(por_raridade))

    if elemento is None:
        por_elemento = [f"{texto_elemento(e)}: {_contagem(descobertos, elemento=e)}" for e in ELEMENTOS]
        embed.add_field(name="Por elemento", value="\n".join(por_elemento))
    return embed


def embed_ranking(linhas):
    """linhas = [(nome, pontos)] já em ordem."""
    if not linhas:
        return embed_mensagem("🏆 Ranking", "Ninguém tem bichinhos ainda. Seja o primeiro!")
    medalhas = ["🥇", "🥈", "🥉"]
    texto = []
    for posicao, (nome, pontos) in enumerate(linhas):
        marcador = medalhas[posicao] if posicao < len(medalhas) else f"{posicao + 1}."
        texto.append(f"{marcador} **{nome}** - {pontos} pontos")
    return embed_mensagem("🏆 Ranking de colecionadores", "\n".join(texto))


def embed_missao(elemento, concluida):
    """Mostra a missão do dia e se o usuário já completou."""
    if concluida:
        situacao = "✅ Você já completou a missão de hoje. Volte amanhã!"
    else:
        situacao = ("Capture (`!capturar`) um objeto desse elemento hoje e ganhe um **roll grátis** extra!\n"
                    "Exemplos: " + ", ".join(c for c, e in ELEMENTO_POR_CLASSE.items() if e == elemento))
    return embed_mensagem(f"📜 Missão do dia: {texto_elemento(elemento)}", situacao)


# ---------- troca ----------

def _texto_oferta(itens, moedas):
    """Ex.: "Sapo Musgoso x2\n50 moedas"."""
    linhas = []
    for bichinho_id, qtd in itens.items():
        bichinho = por_id(bichinho_id)
        nome = bichinho["nome"] if bichinho else bichinho_id
        emoji = EMOJI_RARIDADE[bichinho["raridade"]] if bichinho else ""
        linhas.append(f"{emoji} {nome} x{qtd}")
    if moedas:
        linhas.append(f"🪙 {moedas} moedas")
    return "\n".join(linhas) or "*(nada ainda)*"


def embed_troca(lados, aviso=None, cor=COR_PADRAO):
    """lados = [(nome, itens, moedas, confirmou), (nome, itens, moedas, confirmou)]."""
    embed = embed_mensagem(
        "🔄 Troca de bichinhos",
        aviso or "Adicionem bichinhos ou moedas e depois cliquem em **Confirmar**.\n"
                 "Qualquer mudança desfaz as confirmações.",
        cor,
    )
    for nome, itens, moedas, confirmou in lados:
        marca = "✅" if confirmou else "⏳"
        embed.add_field(name=f"{marca} {nome} oferece", value=_texto_oferta(itens, moedas)[:1024])
    return embed


# ---------- status e HUD ----------

# Nomes que aparecem na contagem de rolls por tipo.
NOMES_TIPO_ROLL = {
    "roll": "🎲 Rolls normais",
    "autoroll": "🤖 Autorolls",
    "comprar": "🪙 Comprados",
    "capturar": "📸 Capturas",
}

# Textos das opções de auto-venda (os ids vêm de banco.VALORES_CONFIGURACAO).
NOMES_AUTO_VENDER = {
    "nada": "Não vender nada",
    "comum": "Vender comuns",
    "incomum": "Vender comuns e incomuns",
}


def _texto_rolls(stats):
    """Total de rolls e a divisão por tipo."""
    linhas = [f"**Total: {stats['total']}**"]
    for tipo, nome in NOMES_TIPO_ROLL.items():
        linhas.append(f"{nome}: {stats['por_tipo'].get(tipo, 0)}")
    return "\n".join(linhas)


def _texto_por_raridade(stats):
    """Quantos bichinhos de cada raridade já saíram nos rolls."""
    return "\n".join(f"{texto_raridade(r)}: {stats['por_raridade'].get(r, 0)}" for r in RARIDADES)


def _texto_melhor(melhor):
    if melhor is None:
        return "Nenhum ainda"
    return f"{EMOJI_RARIDADE[melhor['raridade']]} **{melhor['nome']}** ({RARIDADES[melhor['raridade']]['nome']})"


def _texto_descobertos(qtd_descobertos):
    return f"{qtd_descobertos}/{len(carregar())}"


def _texto_espera(segundos):
    """Devolve "Pronto!" ou o tempo que falta."""
    return "✅ Pronto!" if segundos <= 0 else f"⏳ {formatar_tempo(segundos)}"


def texto_titulo_equipado(titulo, qtd_titulos, total_titulos):
    """Ex.: "👑 **Coroa Dourada** (5/41 títulos)"."""
    nome = f"{titulo['emoji']} **{titulo['nome']}**" if titulo else "Nenhum"
    return f"{nome} ({qtd_titulos}/{total_titulos} títulos)"


def embed_status(nome, stats, melhor, qtd_descobertos, pontos, autoroll_ligado,
                 titulo=None, qtd_titulos=0, total_titulos=0):
    """Status público de um jogador (sem as configurações dele)."""
    descricao = f"Melhor bichinho: {_texto_melhor(melhor)}"
    if total_titulos:
        descricao = f"🏅 Título: {texto_titulo_equipado(titulo, qtd_titulos, total_titulos)}\n" + descricao
    embed = embed_mensagem(f"📊 Status de {nome}", descricao)
    if titulo:
        embed.color = cor_titulo(titulo)  # o status fica com a cor do título
    embed.add_field(name="Rolls", value=_texto_rolls(stats))
    embed.add_field(name="Por raridade", value=_texto_por_raridade(stats))
    embed.add_field(name="Coleção", value=f"Descobertos: **{_texto_descobertos(qtd_descobertos)}**\n"
                                          f"Pontos no ranking: **{pontos}**", inline=False)
    embed.add_field(name="Autoroll", value="🟢 Ligado" if autoroll_ligado else "⚫ Desligado")
    return embed


def embed_hud(nome, stats, melhor, moedas, qtd_inventario, qtd_descobertos,
              autoroll_ligado, proximo_autoroll, espera_roll, espera_capturar, config,
              titulo=None, qtd_titulos=0, total_titulos=0, titulo_no_apelido=True):
    """HUD pessoal: estatísticas, esperas e configurações do autoroll."""
    descricao = f"Melhor bichinho: {_texto_melhor(melhor)}"
    if total_titulos:
        apelido = "ligado" if titulo_no_apelido else "desligado"
        descricao = (f"🏅 Título: {texto_titulo_equipado(titulo, qtd_titulos, total_titulos)}"
                     f" · no apelido: {apelido}\n" + descricao)
    embed = embed_mensagem(f"🎮 HUD de {nome}", descricao)
    embed.add_field(name="Rolls", value=_texto_rolls(stats))
    embed.add_field(name="Por raridade", value=_texto_por_raridade(stats))
    embed.add_field(name="Coleção", value=f"🪙 Moedas: **{moedas}**\n"
                                          f"🎒 No inventário: **{qtd_inventario}**\n"
                                          f"📖 Descobertos: **{_texto_descobertos(qtd_descobertos)}**",
                    inline=False)

    if not autoroll_ligado:
        texto_autoroll = "⚫ Desligado"
    elif proximo_autoroll is None:
        texto_autoroll = "🟢 Ligado (próximo: já já)"
    else:
        texto_autoroll = f"🟢 Ligado (próximo em {formatar_tempo(proximo_autoroll)})"
    embed.add_field(name="Autoroll", value=texto_autoroll)
    embed.add_field(name="Esperas", value=f"!roll: {_texto_espera(espera_roll)}\n"
                                          f"!capturar: {_texto_espera(espera_capturar)}")
    embed.add_field(name="Configurações",
                    value=f"Avisar a partir de: {texto_raridade(config['aviso_minimo'])}\n"
                          f"Auto-venda: {NOMES_AUTO_VENDER[config['auto_vender']]}", inline=False)
    embed.set_footer(text="Só você vê este HUD. Use os controles abaixo ou clique em Atualizar.")
    return embed


# ---------- títulos ----------

def cor_titulo(titulo):
    return discord.Color(titulos.cor_int(titulo))


def campo_titulo(titulo, desbloqueados, equipado_id, dados, numero=None):
    """(nome, valor) do campo de um título numa lista. Secretos bloqueados viram "❓ ???"."""
    prefixo = f"{numero}. " if numero is not None else ""
    if titulos.oculto(titulo, desbloqueados):
        return f"{prefixo}🔒 ❓ ???", "*Título secreto.* Continue jogando para descobrir!"
    if titulo["id"] in desbloqueados:
        marca = " · **equipado**" if titulo["id"] == equipado_id else ""
        return f"{prefixo}✅ {titulos.texto(titulo)}", f"{titulo['descricao']}{marca}\nCor: `{titulo['cor']}`"
    atual, meta = titulos.progresso(titulo, dados)
    return f"{prefixo}🔒 {titulos.texto(titulo)}", f"{titulo['descricao']} (progresso: {min(atual, meta)}/{meta})"


def _rodape_titulos(desbloqueados, pagina, total_paginas):
    return (f"Desbloqueados: {len(desbloqueados)}/{len(titulos.TITULOS)} · "
            f"Página {pagina} de {total_paginas} · Equipe com !titulo <nome>")


def embed_lista_titulos(nome_dono, lista, inicio, desbloqueados, equipado_id, dados, pagina, total_paginas):
    """Uma página de títulos. inicio = número do primeiro título da página."""
    equipado = titulos.por_id(equipado_id) if equipado_id else None
    texto_equipado = titulos.texto(equipado) if equipado else "nenhum"
    embed = embed_mensagem(f"🏅 Títulos de {nome_dono}", f"Equipado: **{texto_equipado}**",
                           cor_titulo(equipado) if equipado else COR_PADRAO)
    for numero, titulo in enumerate(lista, start=inicio):
        nome, valor = campo_titulo(titulo, desbloqueados, equipado_id, dados, numero)
        embed.add_field(name=nome, value=valor, inline=False)
    embed.set_footer(text=_rodape_titulos(desbloqueados, pagina, total_paginas))
    return embed


def paginas_titulos(nome_dono, desbloqueados, equipado_id, dados, por_pagina=8):
    """Todas as páginas do !titulos."""
    todos = titulos.TITULOS
    total_paginas = (len(todos) + por_pagina - 1) // por_pagina
    paginas = []
    for indice in range(total_paginas):
        inicio = indice * por_pagina
        paginas.append(embed_lista_titulos(nome_dono, todos[inicio:inicio + por_pagina], inicio + 1,
                                           desbloqueados, equipado_id, dados, indice + 1, total_paginas))
    return paginas


def embed_titulo_novo(titulo, usuario_id):
    """Anúncio de título desbloqueado. Secretos ganham um anúncio mais chamativo."""
    if titulo["secreto"]:
        cabecalho = "🌟 TÍTULO SECRETO DESBLOQUEADO! 🌟"
        texto = (f"<@{usuario_id}> descobriu um segredo que quase ninguém vê:\n"
                 f"# {titulos.texto(titulo)}\n*{titulo['descricao']}*")
    else:
        cabecalho = "🏅 Novo título desbloqueado!"
        texto = f"<@{usuario_id}> conquistou **{titulos.texto(titulo)}**\n*{titulo['descricao']}*"
    embed = embed_mensagem(cabecalho, texto, cor_titulo(titulo))
    embed.set_footer(text=f"Use !titulo {titulo['nome']} para equipar (ou veja todos em !titulos).")
    return embed