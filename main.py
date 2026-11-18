"""SpriteRNG: bot de Discord para colecionar bichinhos elementais.

Aqui ficam só a criação do bot, os eventos e os comandos.
A lógica está nos outros módulos: sorteio, banco, visao, embeds, trade, chatbot,
autoroll, hud, titulos, cargos e membros.
"""
import asyncio
import os
import re
import subprocess
import sys
import traceback
import uuid

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import autoroll
import banco
import cargos
import catalogo
import embeds
import sorteio
import titulos
import visao
from chatbot import foi_chamado, responder
from embeds import COR_AVISO, COR_ERRO, COR_SUCESSO, embed_mensagem
from hud import ViewAbrirHUD, ViewHUD
from membros import MembroAmbiguo, MembroFlexivel
from trade import ViewTroca

# sprites.py gera as imagens dos bichinhos. Se ele ainda não existir,
# o bot funciona igual, só que sem imagem.
try:
    from sprites import caminho_sprite
except ImportError:
    caminho_sprite = None

# ---------- constantes ajustáveis ----------

ESPERA_CAPTURAR = 5      # segundos entre um !capturar e outro
ESPERA_ROLL = 5          # segundos entre um !roll e outro
PRECO_ROLL_EXTRA = 100   # moedas para um !comprar

# O HUD precisa das esperas para mostrar quanto falta em cada comando.
ESPERAS = {"roll": ESPERA_ROLL, "capturar": ESPERA_CAPTURAR}

# Moedas de cada raridade na venda: ficam no banco.py porque o autoroll também usa.
VALOR_VENDA = banco.VALOR_VENDA

PASTA_TEMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "temp")

# ---------- criação do bot ----------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # necessário para ler os comandos com "!" e o chatbot
# Lista de membros do servidor: usada para achar a pessoa pelo nome no !status e para
# saber se um cargo de título ficou vazio. É um intent PRIVILEGIADO: precisa ligar
# "Server Members Intent" em https://discord.com/developers/applications > seu bot > Bot.
# Se não estiver ligado lá, o bot reinicia sozinho sem ele (veja rodar_bot no fim do arquivo).
VARIAVEL_SEM_MEMBROS = "SPRITERNG_SEM_MEMBROS"
intents.members = os.getenv(VARIAVEL_SEM_MEMBROS) != "1"

AVISO_INTENT_MEMBROS = ("Ative o **Server Members Intent** no portal do Discord (Developer Portal > "
                        "seu bot > Bot) para eu achar qualquer pessoa pelo nome. "
                        "Enquanto isso, só conheço quem já falou comigo.")

# help_command=None porque temos o nosso próprio !ajuda
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------- espera (cooldown) guardada no banco ----------

class EmEspera(commands.CommandError):
    """Erro lançado quando o usuário ainda precisa esperar para usar o comando."""

    def __init__(self, segundos):
        super().__init__(f"Espere {segundos:.0f} s")
        self.segundos = segundos


def verificar_espera(usuario_id, acao, segundos):
    """Lança EmEspera se a ação ainda não pode ser usada (o on_command_error responde)."""
    restante = banco.tempo_restante(usuario_id, acao, segundos)
    if restante > 0:
        raise EmEspera(restante)


# ---------- paginação com botões ----------

class Paginador(discord.ui.View):
    """Mostra uma lista de embeds, um por vez, com botões Anterior/Próxima."""

    def __init__(self, autor_id, paginas):
        super().__init__(timeout=180)
        self.autor_id = autor_id
        self.paginas = paginas
        self.pagina = 0
        self.mensagem = None
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        self.anterior.disabled = self.pagina == 0
        self.proxima.disabled = self.pagina >= len(self.paginas) - 1

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Só quem usou o comando pode virar as páginas.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction, button):
        self.pagina -= 1
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.paginas[self.pagina], view=self)

    @discord.ui.button(label="Próxima", style=discord.ButtonStyle.primary)
    async def proxima(self, interaction, button):
        self.pagina += 1
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.paginas[self.pagina], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.mensagem:
            try:
                await self.mensagem.edit(view=self)
            except discord.HTTPException:
                pass


async def enviar_paginas(ctx, paginas):
    """Envia uma página só, ou o paginador se houver mais de uma."""
    if len(paginas) == 1:
        await ctx.send(embed=paginas[0])
        return
    paginador = Paginador(ctx.author.id, paginas)
    paginador.mensagem = await ctx.send(embed=paginas[0], view=paginador)


# ---------- ajudantes ----------

async def arquivo_sprite(bichinho):
    """discord.File com o sprite do bichinho, ou None se não for possível gerar."""
    if caminho_sprite is None:
        return None
    try:
        # Gerar sprite pode demorar: roda em outra thread para não travar o bot.
        caminho = await asyncio.to_thread(caminho_sprite, bichinho)
        return discord.File(caminho, filename=os.path.basename(caminho))
    except Exception as erro:
        print(f"Não consegui gerar o sprite de {bichinho['id']}: {erro!r}")
        return None


async def salvar_foto(anexo):
    """Salva o anexo em dados/temp com um nome único e devolve o caminho."""
    os.makedirs(PASTA_TEMP, exist_ok=True)
    extensao = os.path.splitext(anexo.filename)[1] or ".png"
    caminho = os.path.join(PASTA_TEMP, uuid.uuid4().hex + extensao)
    await anexo.save(caminho)
    return caminho


def apagar_arquivos(*caminhos):
    """Apaga arquivos temporários, ignorando os que já não existem."""
    for caminho in caminhos:
        if caminho is None:
            continue
        try:
            os.remove(caminho)
        except OSError:
            pass


def entregar_bichinho(usuario_id, bichinho, tipo, com_bonus=False):
    """Põe o bichinho no inventário e conta o roll. True se é a primeira vez (NOVO!)."""
    return sorteio.entregar(usuario_id, bichinho, tipo, com_bonus)


async def anunciar_titulos(destino, *usuario_ids):
    """Depois de jogar: confere títulos novos e anuncia no canal."""
    for usuario_id in usuario_ids:
        await titulos.verificar_e_anunciar(destino, usuario_id)


async def enviar_captura(ctx, bichinho, novo, titulo, deteccao=None, com_bonus=False, caminho_foto=None,
                         conteudo=None):
    """Manda o embed do bichinho sorteado com o sprite e (opcional) a foto com a caixa.

    ctx pode ser um contexto de comando ou um canal: os dois têm .send().
    """
    arquivos = []
    sprite = await arquivo_sprite(bichinho)
    if sprite:
        arquivos.append(sprite)
    nome_foto = None
    if caminho_foto:
        nome_foto = "foto.png"
        arquivos.append(discord.File(caminho_foto, filename=nome_foto))

    embed = embeds.embed_captura(bichinho, novo, titulo, deteccao, com_bonus,
                                 nome_sprite=sprite.filename if sprite else None, nome_foto=nome_foto)
    try:
        await ctx.send(content=conteudo, embed=embed, files=arquivos)
    finally:
        # Fecha os arquivos para o Windows deixar apagar a foto depois.
        for arquivo in arquivos:
            arquivo.close()


def elemento_pelo_texto(texto):
    """Converte "água", "Agua", "fogo"... no id do elemento. None se não existir."""
    procurado = catalogo.normalizar(texto)
    for elemento_id, dados in catalogo.ELEMENTOS.items():
        if procurado in (elemento_id, catalogo.normalizar(dados["nome"])):
            return elemento_id
    return None


async def nome_do_usuario(ctx, usuario_id):
    """Nome de exibição de um usuário a partir do id (para o ranking)."""
    if ctx.guild:
        membro = ctx.guild.get_member(usuario_id)
        if membro:
            return membro.display_name
    usuario = bot.get_user(usuario_id)
    if usuario is None:
        try:
            usuario = await bot.fetch_user(usuario_id)
        except discord.HTTPException:
            return f"Usuário {usuario_id}"
    return usuario.display_name


def bichinho_nao_encontrado(nome):
    return embed_mensagem("Bichinho não encontrado",
                          f"Não achei nenhum bichinho parecido com \"{nome}\".", COR_AVISO)


async def tentar_missao(ctx, elemento):
    """Se o elemento capturado é o da missão do dia (e ela não foi feita), dá um roll grátis."""
    usuario_id = ctx.author.id
    if elemento != sorteio.elemento_do_dia() or sorteio.missao_concluida(usuario_id):
        return
    sorteio.concluir_missao(usuario_id)
    bichinho = sorteio.sortear()
    novo = entregar_bichinho(usuario_id, bichinho, "roll")  # roll grátis conta como roll normal
    await enviar_captura(ctx, bichinho, novo, "📜 Missão do dia completa! Roll grátis:")


async def aviso_autoroll(canal, usuario_id, bichinho, novo, ganho):
    """Aviso do autoroll no canal (com sprite), mencionando o dono."""
    titulo = "🤖 Autoroll!"
    if ganho:
        titulo += f" (vendido na hora por {ganho} moedas)"
    await enviar_captura(canal, bichinho, novo, titulo, conteudo=f"<@{usuario_id}>")

# O autoroll usa esta função para avisar (assim ele também manda o sprite).
autoroll.definir_aviso(aviso_autoroll)


async def responder_hud(ctx):
    """/hud abre o HUD efêmero direto; !hud manda o botão (veja o comentário em hud.py)."""
    if ctx.interaction is not None:
        view = ViewHUD(ctx.author, ESPERAS)
        await ctx.send(embed=view.embed_atual(), view=view, ephemeral=True)
        view.interacao = ctx.interaction
        return
    view = ViewAbrirHUD(ESPERAS)
    view.mensagem = await ctx.send("Clique no botão para abrir o **seu** HUD (só você vai ver).", view=view)


# ---------- eventos ----------

async def setup_hook():
    # Registra os comandos de barra (/) no Discord.
    try:
        sincronizados = await bot.tree.sync()
        print(f"{len(sincronizados)} comandos de barra sincronizados.")
    except discord.HTTPException as erro:
        print(f"Falha ao sincronizar os comandos de barra: {erro}")

bot.setup_hook = setup_hook


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")


def e_resposta_ao_bot(message):
    """True se a mensagem é um reply a uma mensagem do próprio bot."""
    referencia = message.reference
    return bool(
        referencia
        and isinstance(referencia.resolved, discord.Message)
        and referencia.resolved.author == bot.user
    )


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Qualquer mensagem no servidor conta como atividade (mantém o autoroll ligado).
    if message.guild is not None:
        autoroll.registrar_atividade(message.author.id)

    # Mensagens com "!" são comandos e não passam pelo chatbot.
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    marcado = bot.user in message.mentions
    if marcado or foi_chamado(message.content) or e_resposta_ao_bot(message):
        texto = re.sub(r"<@!?\d+>", " ", message.content)  # tira a menção <@id> do texto
        async with message.channel.typing():
            await asyncio.sleep(0.6)  # pausa curtinha para parecer que está digitando
        await message.reply(responder(texto), mention_author=False)
        return

    await bot.process_commands(message)


@bot.listen()
async def on_interaction(interaction):
    # Comandos de barra e cliques em botões também contam como atividade.
    if interaction.guild is not None:
        autoroll.registrar_atividade(interaction.user.id)


@bot.event
async def on_command_error(ctx, error):
    # Erros dentro do comando chegam "embrulhados"; pegamos o erro original.
    error = getattr(error, "original", error)

    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, EmEspera):
        await ctx.send(embed=embed_mensagem(
            "Calma aí! ⏳", f"Você poderá usar este comando de novo em **{embeds.formatar_tempo(error.segundos)}**.",
            COR_AVISO))
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(embed=embed_mensagem(
            "Calma aí! ⏳", f"Tente de novo em **{embeds.formatar_tempo(error.retry_after)}**.", COR_AVISO))
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=embed_mensagem(
            "Falta informação",
            f"O comando `!{ctx.command.qualified_name}` precisa de `{error.param.name}`. Veja `!ajuda`.",
            COR_AVISO))
        return
    if isinstance(error, MembroAmbiguo):
        nomes = "\n".join(f"• **{m.display_name}** (`{m.name}`)" for m in error.candidatos)
        await ctx.send(embed=embed_mensagem(
            "Quem você quis dizer? 🤔",
            f"Mais de uma pessoa combina com \"{error.texto}\":\n{nomes}\n"
            "Escreva o nome mais completo ou marque a pessoa com @.", COR_AVISO))
        return
    if isinstance(error, (commands.UserNotFound, commands.MemberNotFound)):
        texto = "Não achei esse usuário. Marque a pessoa com @ ou escreva parte do nome/apelido dela."
        if not bot.intents.members:
            texto += "\n\n" + AVISO_INTENT_MEMBROS
        await ctx.send(embed=embed_mensagem("Usuário não encontrado", texto, COR_AVISO))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=embed_mensagem("Argumento inválido", "Confira o comando em `!ajuda`.", COR_AVISO))
        return

    print(f"Erro inesperado no comando {ctx.command}:")
    traceback.print_exception(type(error), error, error.__traceback__)
    await ctx.send(embed=embed_mensagem(
        "Erro inesperado", "Algo deu errado ao executar o comando. Tente novamente.", COR_ERRO))


# ---------- comandos de sorteio ----------

@bot.hybrid_command(description="Captura um bichinho a partir da foto de um objeto.")
@app_commands.describe(foto="Foto de um objeto (gato, planta, xícara, celular...)")
async def capturar(ctx, foto: discord.Attachment | None = None):
    # No !capturar a foto vem anexada na mensagem; no /capturar, no campo "foto".
    if foto is None and ctx.interaction is None and ctx.message.attachments:
        foto = ctx.message.attachments[0]
    if foto is None or not (foto.content_type or "").startswith("image/"):
        await ctx.send(embed=embed_mensagem(
            "Cadê a foto? 📸", "Envie uma imagem junto com `!capturar` (ou no campo do `/capturar`).", COR_AVISO))
        return
    verificar_espera(ctx.author.id, "capturar", ESPERA_CAPTURAR)

    caminho = None
    caminho_caixa = None
    async with ctx.typing():  # no /capturar isso também avisa o Discord que vamos demorar
        try:
            caminho = await salvar_foto(foto)
            # O YOLO é pesado: roda em outra thread para o bot não congelar.
            deteccoes = await asyncio.to_thread(visao.detectar, caminho)
            if not deteccoes:
                await ctx.send(embed=embeds.embed_nada_detectado())
                return

            melhor = deteccoes[0]
            com_bonus = sorteio.tem_bonus(melhor.confianca)
            bichinho = sorteio.sortear(melhor.elemento, com_bonus)
            novo = entregar_bichinho(ctx.author.id, bichinho, "capturar", com_bonus)
            banco.registrar_uso(ctx.author.id, "capturar")  # só conta a espera se pegou algo

            caminho_caixa = await asyncio.to_thread(visao.desenhar_deteccoes, caminho, [melhor])
            await enviar_captura(ctx, bichinho, novo, "Você capturou um bichinho!", melhor, com_bonus, caminho_caixa)
            await tentar_missao(ctx, melhor.elemento)
            await anunciar_titulos(ctx, ctx.author.id)
        finally:
            apagar_arquivos(caminho, caminho_caixa)


@bot.hybrid_command(description=f"Sorteia um bichinho de qualquer elemento (a cada {ESPERA_ROLL} s).")
async def roll(ctx):
    # Com o autoroll ligado o bot já está rolando por você; !roll fica bloqueado.
    if autoroll.esta_ligado(ctx.author.id):
        await ctx.send(embed=embed_mensagem(
            "Autoroll ligado 🤖", "Seu autoroll já está rolando por você. "
            "Desligue com `!autoroll` (ou no `!hud`) para usar o `!roll`.", COR_AVISO))
        return
    verificar_espera(ctx.author.id, "roll", ESPERA_ROLL)
    banco.registrar_uso(ctx.author.id, "roll")
    bichinho = sorteio.sortear()
    novo = entregar_bichinho(ctx.author.id, bichinho, "roll")
    await enviar_captura(ctx, bichinho, novo, "🎲 Roll!")
    await anunciar_titulos(ctx, ctx.author.id)


@bot.hybrid_command(description=f"Compra um roll extra por {PRECO_ROLL_EXTRA} moedas.")
async def comprar(ctx):
    if not banco.alterar_moedas(ctx.author.id, -PRECO_ROLL_EXTRA):
        saldo = banco.moedas(ctx.author.id)
        await ctx.send(embed=embed_mensagem(
            "Moedas insuficientes",
            f"Um roll extra custa {PRECO_ROLL_EXTRA} moedas e você tem {saldo}.", COR_AVISO))
        return
    bichinho = sorteio.sortear()
    novo = entregar_bichinho(ctx.author.id, bichinho, "comprar")
    await enviar_captura(ctx, bichinho, novo, f"🪙 Roll comprado (-{PRECO_ROLL_EXTRA} moedas)!")
    await anunciar_titulos(ctx, ctx.author.id)


# name="autoroll" porque "autoroll" já é o nome do módulo importado lá em cima.
@bot.hybrid_command(name="autoroll",
                    description=f"Liga/desliga o roll automático (a cada {autoroll.INTERVALO_AUTOROLL} s).")
async def comando_autoroll(ctx):
    usuario_id = ctx.author.id
    if autoroll.esta_ligado(usuario_id):
        autoroll.desligar(usuario_id)
        await ctx.send(embed=embed_mensagem("Autoroll desligado ⚫", "Você já pode usar o `!roll` de novo."))
        return
    autoroll.ligar(usuario_id, ctx.channel)
    aviso = banco.configuracao(usuario_id)["aviso_minimo"]
    await ctx.send(embed=embed_mensagem(
        "Autoroll ligado 🤖",
        f"Vou rolar para você a cada **{autoroll.INTERVALO_AUTOROLL} s**.\n"
        f"Aviso aqui só quando sair **{embeds.texto_raridade(aviso)}** ou melhor (mude no `!hud`).\n"
        f"Desliga sozinho depois de {embeds.formatar_tempo(autoroll.AUTOROLL_INATIVIDADE)} sem mensagens suas. "
        "Enquanto estiver ligado, o `!roll` fica bloqueado.", COR_SUCESSO))


@bot.hybrid_command(description="Abre o seu HUD pessoal (só você vê).")
async def hud(ctx):
    await responder_hud(ctx)


@bot.hybrid_command(description="Mostra os status de um jogador.")
@app_commands.describe(membro="De quem ver os status (vazio = você)")
async def status(ctx, *, membro: MembroFlexivel | None = None):
    # MembroFlexivel: no !status aceita menção, id ou parte do nome (sem maiúsculas/acentos);
    # no /status o Discord mostra a lista de membros (veja membros.py).
    alvo = membro or ctx.author
    uid = alvo.id
    titulos.verificar_titulos(uid)  # conta conquistas antigas antes de mostrar
    embed = embeds.embed_status(
        alvo.display_name, banco.estatisticas(uid), banco.melhor_bichinho(uid),
        len(banco.descobertos(uid)), banco.pontuacao(uid), autoroll.esta_ligado(uid),
        titulo=titulos.equipado(uid), qtd_titulos=len(banco.titulos_desbloqueados(uid)),
        total_titulos=len(titulos.TITULOS))
    await ctx.send(embed=embed)


# ---------- títulos ----------

@bot.hybrid_command(name="titulos", description="Lista todos os títulos e como desbloquear cada um.")
async def comando_titulos(ctx):
    uid = ctx.author.id
    await anunciar_titulos(ctx, uid)  # pode ter conquistado algo sem perceber
    paginas = embeds.paginas_titulos(ctx.author.display_name, banco.titulos_desbloqueados(uid),
                                     banco.titulo_equipado(uid), titulos.coletar_dados(uid))
    await enviar_paginas(ctx, paginas)


PALAVRAS_REMOVER = {"remover", "nenhum", "tirar", "desequipar"}


async def responder_equipar(ctx, titulo):
    """Equipa (ou tira, com titulo=None), aplica no servidor e conta como foi."""
    await ctx.defer()  # no /titulo, mexer em cargos pode demorar mais de 3 s
    avisos = await cargos.equipar(ctx.author, titulo)
    if titulo is None:
        embed = embed_mensagem("Título removido", "Você está sem título agora. Seu apelido voltou ao normal.")
    else:
        embed = embed_mensagem("Título equipado! 🏅", f"Agora você é **{titulos.texto(titulo)}**.",
                               embeds.cor_titulo(titulo))
    if avisos:
        embed.add_field(name="⚠️ Atenção", value="\n".join(avisos)[:1024], inline=False)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="titulo", description="Equipa um título desbloqueado (vazio ou \"remover\" tira o título).")
@app_commands.describe(nome="Nome do título (pode ser parcial)")
async def comando_titulo(ctx, *, nome: str | None = None):
    uid = ctx.author.id
    titulos.verificar_titulos(uid)
    if nome is None or catalogo.normalizar(nome) in PALAVRAS_REMOVER:
        await responder_equipar(ctx, None)
        return
    meus = titulos.desbloqueados(uid)
    escolhido = titulos.buscar(nome, meus)
    if escolhido is None:
        await ctx.send(embed=titulo_indisponivel(nome))
        return
    await responder_equipar(ctx, escolhido)


def titulo_indisponivel(nome):
    """Explica por que o título não pode ser equipado (sem revelar os secretos)."""
    existente = titulos.buscar(nome)  # procura só entre os que não são secretos
    if existente is None:
        return embed_mensagem("Título não encontrado",
                              f"Não achei nenhum título seu parecido com \"{nome}\". Veja a lista em `!titulos`.",
                              COR_AVISO)
    return embed_mensagem("Ainda bloqueado 🔒",
                          f"**{titulos.texto(existente)}**: {existente['descricao']}\n"
                          "Continue jogando para desbloquear!", COR_AVISO)


@comando_titulo.autocomplete("nome")
async def autocompletar_titulo(interaction, atual):
    """No /titulo, sugere só os títulos que a pessoa já desbloqueou."""
    procurado = catalogo.normalizar(atual)
    opcoes = [app_commands.Choice(name=f"{t['emoji']} {t['nome']}", value=t["nome"])
              for t in titulos.desbloqueados(interaction.user.id)
              if procurado in catalogo.normalizar(t["nome"])]
    opcoes.append(app_commands.Choice(name="➖ Remover título", value="remover"))
    return opcoes[-25:]  # o Discord aceita no máximo 25 sugestões


@bot.hybrid_command(description="Mostra a missão diária.")
async def missao(ctx):
    elemento = sorteio.elemento_do_dia()
    concluida = sorteio.missao_concluida(ctx.author.id)
    await ctx.send(embed=embeds.embed_missao(elemento, concluida))


# ---------- comandos de coleção ----------

@bot.hybrid_command(description="Mostra o inventário (seu ou de outra pessoa).")
@app_commands.describe(usuario="De quem ver o inventário")
async def inv(ctx, usuario: discord.User | None = None):
    dono = usuario or ctx.author
    paginas = embeds.paginas_inventario(dono.display_name, banco.inventario(dono.id))
    await enviar_paginas(ctx, paginas)


@bot.hybrid_command(description="Mostra a ficha de um bichinho.")
@app_commands.describe(bichinho="Nome do bichinho (pode ser parcial)")
async def ver(ctx, *, bichinho: str):
    encontrado = catalogo.buscar(bichinho)
    if encontrado is None:
        await ctx.send(embed=bichinho_nao_encontrado(bichinho))
        return
    quantidade = banco.quantidade(ctx.author.id, encontrado["id"])
    descoberto = encontrado["id"] in banco.descobertos(ctx.author.id)
    sprite = await arquivo_sprite(encontrado)
    embed = embeds.embed_ficha(encontrado, quantidade, descoberto, sprite.filename if sprite else None)
    if sprite:
        await ctx.send(embed=embed, file=sprite)
    else:
        await ctx.send(embed=embed)


@bot.hybrid_command(description="Mostra quantos bichinhos você já descobriu.")
@app_commands.describe(elemento="Opcional: natureza, fogo, agua, eletrico, mistico ou fera")
async def index(ctx, elemento: str | None = None):
    elemento_id = None
    if elemento:
        elemento_id = elemento_pelo_texto(elemento)
        if elemento_id is None:
            nomes = ", ".join(dados["nome"] for dados in catalogo.ELEMENTOS.values())
            await ctx.send(embed=embed_mensagem("Elemento inválido", f"Elementos: {nomes}.", COR_AVISO))
            return
    descobertos = banco.descobertos(ctx.author.id)
    await ctx.send(embed=embeds.embed_index(ctx.author.display_name, descobertos, elemento_id))


@bot.hybrid_command(description="Ranking dos maiores colecionadores.")
async def rank(ctx):
    linhas = []
    for usuario_id, pontos in banco.ranking():
        linhas.append((await nome_do_usuario(ctx, usuario_id), pontos))
    await ctx.send(embed=embeds.embed_ranking(linhas))


# ---------- comandos de moedas e troca ----------

@bot.hybrid_command(description="Mostra quantas moedas você tem.")
async def moedas(ctx):
    saldo = banco.moedas(ctx.author.id)
    await ctx.send(embed=embed_mensagem("🪙 Suas moedas", f"Você tem **{saldo}** moedas."))


@bot.hybrid_command(description="Vende um bichinho por moedas.")
@app_commands.describe(bichinho="Nome do bichinho que você quer vender")
async def vender(ctx, *, bichinho: str):
    encontrado = catalogo.buscar(bichinho)
    if encontrado is None:
        await ctx.send(embed=bichinho_nao_encontrado(bichinho))
        return
    if not banco.remover_bichinho(ctx.author.id, encontrado["id"]):
        await ctx.send(embed=embed_mensagem(
            "Você não tem esse bichinho", f"Você não possui **{encontrado['nome']}**.", COR_AVISO))
        return
    valor = VALOR_VENDA[encontrado["raridade"]]
    banco.alterar_moedas(ctx.author.id, valor)
    if encontrado["raridade"] == "mitico":
        banco.somar_contador(ctx.author.id, "miticos_vendidos")  # usado por um título secreto
    await ctx.send(embed=embed_mensagem(
        "Vendido! 🪙", f"Você vendeu **{encontrado['nome']}** por **{valor}** moedas.", COR_SUCESSO))
    await anunciar_titulos(ctx, ctx.author.id)  # moedas também dão títulos


@bot.hybrid_command(description="Dá um bichinho de presente para alguém.")
@app_commands.describe(usuario="Quem vai receber", bichinho="Nome do bichinho")
async def dar(ctx, usuario: discord.User, *, bichinho: str):
    if usuario.bot or usuario.id == ctx.author.id:
        await ctx.send(embed=embed_mensagem("Não dá!", "Escolha outra pessoa (que não seja bot).", COR_AVISO))
        return
    encontrado = catalogo.buscar(bichinho)
    if encontrado is None:
        await ctx.send(embed=bichinho_nao_encontrado(bichinho))
        return
    # banco.trocar faz tudo de uma vez: ou o presente é entregue, ou nada muda.
    if not banco.trocar(ctx.author.id, {encontrado["id"]: 1}, 0, usuario.id, {}, 0):
        await ctx.send(embed=embed_mensagem(
            "Você não tem esse bichinho", f"Você não possui **{encontrado['nome']}**.", COR_AVISO))
        return
    await ctx.send(embed=embed_mensagem(
        "Presente entregue! 🎁", f"{ctx.author.mention} deu **{encontrado['nome']}** para {usuario.mention}.",
        COR_SUCESSO))
    await anunciar_titulos(ctx, ctx.author.id, usuario.id)


@bot.hybrid_command(description="Abre uma troca de bichinhos e moedas com alguém.")
@app_commands.describe(usuario="Com quem trocar")
async def trade(ctx, usuario: discord.User):
    if usuario.bot or usuario.id == ctx.author.id:
        await ctx.send(embed=embed_mensagem("Não dá!", "Você só pode trocar com outra pessoa (que não seja bot).",
                                            COR_AVISO))
        return
    view = ViewTroca(ctx.author, usuario)
    view.mensagem = await ctx.send(content=usuario.mention, embed=view.embed_atual(), view=view)


# ---------- ajuda ----------

@bot.hybrid_command(description="Explica como jogar e lista os comandos.")
async def ajuda(ctx):
    embed = embed_mensagem(
        "SpriteRNG - Ajuda",
        "Colecione bichinhos elementais! Fotografe objetos: o objeto decide o elemento e a sorte decide o bichinho.\n"
        "Todos os comandos funcionam com `!` e com `/`.\n"
        "Para conversar comigo, escreva **sprite**, **sprites**, **spriterng** ou **rng** na mensagem, "
        "me marque ou responda uma mensagem minha.",
    )
    comandos = [
        ("!capturar + foto", f"Captura um bichinho do elemento do objeto "
                             f"(espera {embeds.formatar_tempo(ESPERA_CAPTURAR)}). Foto nítida dá bônus!"),
        ("!roll", f"Sorteia um bichinho de qualquer elemento (espera {embeds.formatar_tempo(ESPERA_ROLL)})."),
        ("!autoroll", f"Liga/desliga o roll automático a cada {autoroll.INTERVALO_AUTOROLL} s. "
                      "Só avisa raridades altas; bloqueia o !roll enquanto ligado."),
        ("!hud", "Seu painel pessoal (só você vê): estatísticas, esperas, autoroll e a aba de títulos."),
        ("!status [@usuario ou nome]", "Mostra os status de alguém (ou os seus). Aceita parte do nome."),
        ("!titulos", "Lista os títulos: os seus ✅, os bloqueados 🔒 (com o que fazer) e os secretos ❓."),
        ("!titulo <nome>", "Equipa um título: seu nome ganha a cor dele e o título aparece no apelido. "
                           "`!titulo remover` tira. No `!hud` há a aba 🏅 Títulos."),
        ("!comprar", f"Roll extra por {PRECO_ROLL_EXTRA} moedas, sem espera."),
        ("!missao", "Missão diária: capture o elemento do dia e ganhe um roll grátis."),
        ("!inv [@usuario]", "Mostra o inventário."),
        ("!ver <bichinho>", "Ficha do bichinho com imagem."),
        ("!index [elemento]", "Quantos bichinhos você já descobriu."),
        ("!rank", "Maiores colecionadores."),
        ("!moedas", "Seu saldo."),
        ("!vender <bichinho>", "Vende um bichinho por moedas."),
        ("!dar @usuario <bichinho>", "Dá um bichinho de presente."),
        ("!trade @usuario", "Troca bichinhos e moedas com botões."),
    ]
    for nome, explicacao in comandos:
        embed.add_field(name=nome, value=explicacao, inline=False)
    await ctx.send(embed=embed)


def rodar_bot():
    """Liga o bot. Se o "Server Members Intent" estiver desligado no portal, reinicia sem ele."""
    try:
        bot.run(TOKEN)
    except discord.PrivilegedIntentsRequired:
        if not intents.members:
            raise  # já estava sem o intent: o problema é outro intent privilegiado
        print("AVISO: o 'Server Members Intent' está desligado no portal do Discord.\n"
              "Ligue em https://discord.com/developers/applications > seu bot > Bot > Privileged Gateway Intents.\n"
              "Reiniciando sem ele: o !status só vai achar quem já falou com o bot.")
        # Um intent não pode ser mudado com o bot já criado, então rodamos o programa de novo.
        ambiente = dict(os.environ, **{VARIAVEL_SEM_MEMBROS: "1"})
        sys.exit(subprocess.call([sys.executable, *sys.argv], env=ambiente))


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Token não encontrado. Crie o arquivo .env com DISCORD_TOKEN=...")
    rodar_bot()
