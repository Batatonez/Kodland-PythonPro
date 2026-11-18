"""Cargos e apelidos dos títulos no servidor do Discord.

Quando alguém equipa um título, o bot:
1. cria (se ainda não existir) um cargo "👑 Coroa Dourada" com a cor do título;
2. dá esse cargo para a pessoa e tira os cargos de outros títulos;
3. (opcional) muda o apelido para "Nome 「Coroa Dourada」".

Nada aqui pode derrubar um comando: quando falta permissão ou o Discord
recusa, as funções devolvem avisos em texto para o bot mostrar à pessoa.
"""
import discord

import banco
import titulos

LIMITE_APELIDO = 32       # limite do Discord para apelidos
MOTIVO = "Título do SpriteRNG"  # aparece no registro de auditoria do servidor
ABRE, FECHA = " 「", "」"   # marcam o título no apelido

AVISO_SEM_CARGOS = ("Não tenho a permissão **Gerenciar Cargos**, então não consigo dar a cor do título. "
                    "Peça para um admin ativar essa permissão no meu cargo.")
AVISO_SEM_APELIDOS = ("Não tenho a permissão **Gerenciar Apelidos**, então não consigo pôr o título ao lado "
                      "do seu nome. Peça para um admin ativar essa permissão no meu cargo.")
AVISO_DONO = ("O Discord não deixa nenhum bot mudar o apelido do **dono do servidor**, "
              "então o título não aparece no seu nome (a cor do cargo funciona normalmente).")
AVISO_HIERARQUIA = ("Seu cargo mais alto está acima do meu, então o Discord não me deixa mudar seu apelido. "
                    "Um admin pode subir o meu cargo na lista de cargos do servidor.")
AVISO_CARGO_RECUSADO = ("O Discord recusou mexer no cargo do título. Confira se o meu cargo está acima "
                        "dos cargos de título na lista de cargos do servidor.")
AVISO_SEM_SERVIDOR = "Fora de um servidor não há cargos nem apelidos: o título foi salvo e vale no servidor."


# ---------- apelido ----------

def _tamanho(texto):
    """Tamanho como o Discord conta (UTF-16: alguns emojis valem 2 ou mais)."""
    return len(texto.encode("utf-16-le")) // 2


def _cortar(texto, limite):
    """Corta o texto até caber no limite (contando como o Discord)."""
    while texto and _tamanho(texto) > limite:
        texto = texto[:-1]
    return texto.rstrip()


def montar_apelido(nome, titulo):
    """Ex.: ("Ana", Coroa Dourada) -> "Ana 「Coroa Dourada」" (no máximo 32 caracteres).

    Se não couber, corta o NOME e não o título. Se nem o título couber, usa só o emoji.
    """
    sufixo = f"{ABRE}{titulo['nome']}{FECHA}"
    if _tamanho(sufixo) + 1 > LIMITE_APELIDO:  # +1: sobra pelo menos uma letra do nome
        sufixo = f" {titulo['emoji']}"
    nome = _cortar(nome, LIMITE_APELIDO - _tamanho(sufixo)) or "?"
    return nome + sufixo


def _tem_titulo_no_apelido(apelido):
    """True se o apelido parece ter sido feito pelo bot (tem 「...」 no fim)."""
    return bool(apelido) and apelido.endswith(FECHA) and ABRE in apelido


def _verificar_apelido(membro):
    """Aviso explicando por que não dá para mudar o apelido, ou None se dá."""
    guild = membro.guild
    if not guild.me.guild_permissions.manage_nicknames:
        return AVISO_SEM_APELIDOS
    if membro.id == guild.owner_id:
        return AVISO_DONO
    if membro.top_role >= guild.me.top_role:
        return AVISO_HIERARQUIA
    return None


async def _mudar_apelido(membro, apelido):
    """Muda o apelido. Devolve um aviso se o Discord recusar, ou None."""
    try:
        await membro.edit(nick=apelido, reason=MOTIVO)
        return None
    except discord.Forbidden:
        return AVISO_HIERARQUIA
    except discord.HTTPException as erro:
        return f"Não consegui mudar o apelido ({erro.status})."


async def por_titulo_no_apelido(membro, titulo):
    """Põe "Nome 「Título」" no apelido, guardando o apelido de antes."""
    aviso = _verificar_apelido(membro)
    if aviso:
        return aviso
    guild_id = membro.guild.id
    guardado, original = banco.apelido_original(guild_id, membro.id)
    # Se a pessoa trocou o apelido na mão depois, o novo vira o "original".
    if not guardado or not _tem_titulo_no_apelido(membro.nick):
        original = membro.nick
        banco.guardar_apelido_original(guild_id, membro.id, original)
    nome = original or membro.global_name or membro.name
    aviso = await _mudar_apelido(membro, montar_apelido(nome, titulo))
    if aviso and not _tem_titulo_no_apelido(membro.nick):
        banco.esquecer_apelido_original(guild_id, membro.id)  # nada mudou: nada a restaurar
    return aviso


async def restaurar_apelido(membro):
    """Volta o apelido de antes do título (se o bot tinha mudado)."""
    guild_id = membro.guild.id
    guardado, original = banco.apelido_original(guild_id, membro.id)
    if not guardado:
        return None
    aviso = _verificar_apelido(membro)
    if aviso is None:
        aviso = await _mudar_apelido(membro, original)
    if aviso is None:
        banco.esquecer_apelido_original(guild_id, membro.id)
    return aviso


async def atualizar_apelido(membro, titulo):
    """Deixa o apelido de acordo com o título equipado e a opção "título no apelido"."""
    if titulo is not None and banco.titulo_no_apelido(membro.id):
        return await por_titulo_no_apelido(membro, titulo)
    return await restaurar_apelido(membro)


# ---------- cargos ----------

def nome_do_cargo(titulo):
    return titulos.texto(titulo)  # ex.: "👑 Coroa Dourada"


async def _criar_cargo(guild, titulo):
    """Cria o cargo do título (com ícone, se o servidor permitir ícones de cargo)."""
    dados = {"name": nome_do_cargo(titulo), "colour": discord.Colour(titulos.cor_int(titulo)),
             "hoist": False, "mentionable": False, "reason": MOTIVO}
    if "ROLE_ICONS" in guild.features:
        try:
            return await guild.create_role(display_icon=titulo["emoji"], **dados)
        except discord.HTTPException:
            pass  # alguns emojis não servem de ícone: cria sem ícone mesmo
    return await guild.create_role(**dados)


async def obter_cargo(guild, titulo):
    """Cargo do título neste servidor: reaproveita o salvo, ou cria de novo se foi apagado."""
    cargo = guild.get_role(banco.cargo_do_titulo(guild.id, titulo["id"]) or 0)
    if cargo is None:
        # O banco pode ter se perdido: procura um cargo com o mesmo nome antes de criar.
        cargo = discord.utils.get(guild.roles, name=nome_do_cargo(titulo))
    if cargo is None:
        cargo = await _criar_cargo(guild, titulo)
    banco.salvar_cargo_do_titulo(guild.id, titulo["id"], cargo.id)
    return cargo


async def posicionar(guild, cargo):
    """Sobe o cargo para logo abaixo do cargo do bot (assim a cor dele aparece por cima)."""
    alvo = guild.me.top_role.position - 1
    if alvo < 1 or cargo.position >= alvo:
        return
    try:
        await cargo.edit(position=alvo, reason=MOTIVO)
    except discord.HTTPException:
        pass  # sem posição ideal a cor pode ficar escondida, mas tudo continua funcionando


def _cargos_de_titulo(guild):
    """Cargos de título do bot que ainda existem neste servidor."""
    cargos = [guild.get_role(cargo_id) for cargo_id in banco.cargos_de_titulo(guild.id).values()]
    return [cargo for cargo in cargos if cargo is not None]


async def limpar_cargos_vazios(guild, saiu, manter=None):
    """Apaga cargos de título que ficaram sem ninguém (para não poluir o servidor).

    saiu = membro que acabou de perder cargos (o cache do Discord ainda pode listá-lo).
    """
    if not guild.chunked:
        return  # sem a lista completa de membros não dá para saber se o cargo está vazio
    for titulo_id, cargo_id in banco.cargos_de_titulo(guild.id).items():
        cargo = guild.get_role(cargo_id)
        if cargo is None:
            banco.esquecer_cargo_do_titulo(guild.id, titulo_id)  # já foi apagado por alguém
            continue
        if cargo == manter or any(m.id != saiu.id for m in cargo.members):
            continue
        try:
            await cargo.delete(reason="Cargo de título sem ninguém")
            banco.esquecer_cargo_do_titulo(guild.id, titulo_id)
        except discord.HTTPException:
            pass


async def trocar_cargo(membro, titulo):
    """Dá o cargo do título (None = nenhum) e tira os de outros títulos. Devolve aviso ou None."""
    guild = membro.guild
    if not guild.me.guild_permissions.manage_roles:
        return AVISO_SEM_CARGOS
    try:
        cargo = None
        if titulo is not None:
            cargo = await obter_cargo(guild, titulo)
            await posicionar(guild, cargo)
            if cargo not in membro.roles:
                await membro.add_roles(cargo, reason=MOTIVO)
        outros = [c for c in _cargos_de_titulo(guild) if c != cargo and c in membro.roles]
        if outros:
            await membro.remove_roles(*outros, reason=MOTIVO)
        await limpar_cargos_vazios(guild, membro, manter=cargo)
    except discord.Forbidden:
        return AVISO_CARGO_RECUSADO
    except discord.HTTPException as erro:
        return f"O Discord deu erro ao mexer nos cargos ({erro.status}). Tente de novo daqui a pouco."
    return None


# ---------- o que os comandos e o HUD chamam ----------

def _e_membro_de_servidor(usuario):
    return getattr(usuario, "guild", None) is not None


async def aplicar_titulo(membro, titulo):
    """Aplica cargo e apelido do título (None = tirar). Devolve a lista de avisos."""
    if not _e_membro_de_servidor(membro):
        return [AVISO_SEM_SERVIDOR]
    avisos = [await trocar_cargo(membro, titulo), await atualizar_apelido(membro, titulo)]
    return [aviso for aviso in avisos if aviso]


async def equipar(membro, titulo):
    """Salva o título equipado (None = desequipar) e aplica no servidor. Devolve avisos.

    Quem chama precisa conferir antes se o título está desbloqueado.
    """
    banco.equipar_titulo(membro.id, titulo["id"] if titulo else None)
    return await aplicar_titulo(membro, titulo)


async def alternar_titulo_no_apelido(membro):
    """Liga/desliga o título no apelido. Devolve (novo estado, avisos)."""
    ligado = not banco.titulo_no_apelido(membro.id)
    banco.definir_titulo_no_apelido(membro.id, ligado)
    if not _e_membro_de_servidor(membro):
        return ligado, []
    aviso = await atualizar_apelido(membro, titulos.equipado(membro.id))
    return ligado, [aviso] if aviso else []
