"""Acha um membro do servidor pelo que a pessoa digitou no !status.

Aceita menção (@fulano), id e nome/apelido sem diferenciar maiúsculas e acentos.
A busca tenta, nesta ordem: nome igual, começa com, contém e parecido (difflib).
"""
import difflib
import re

import discord
from discord import app_commands
from discord.ext import commands

from catalogo import normalizar

MAX_CANDIDATOS = 5      # quantos nomes mostrar quando a busca fica ambígua
NOTA_MINIMA = 0.6       # parecido o bastante para o difflib (0 a 1)
FOLGA_DIFFLIB = 0.1     # o primeiro precisa ganhar do segundo por essa diferença

# <@123>, <@!123> ou só o número do id
_PADRAO_ID = re.compile(r"^(?:<@!?(\d+)>|(\d{15,20}))$")


class MembroAmbiguo(commands.BadArgument):
    """Mais de uma pessoa combina com o texto; o main lista os candidatos."""

    def __init__(self, texto, candidatos):
        super().__init__(f"Mais de um membro combina com {texto!r}")
        self.texto = texto
        self.candidatos = candidatos[:MAX_CANDIDATOS]


def nomes_do_membro(membro):
    """Todos os nomes pelos quais a pessoa pode ser chamada, já normalizados."""
    nomes = [membro.name, membro.nick, membro.display_name, membro.global_name]
    return {normalizar(nome) for nome in nomes if nome}


def _unicos(membros):
    """Tira repetidos mantendo a ordem."""
    vistos, resultado = set(), []
    for membro in membros:
        if membro.id not in vistos:
            vistos.add(membro.id)
            resultado.append(membro)
    return resultado


def _por_regra(membros, regra):
    """Membros com algum nome que satisfaz a regra (uma função nome -> bool)."""
    return _unicos(m for m in membros if any(regra(nome) for nome in nomes_do_membro(m)))


def _por_semelhanca(membros, procurado):
    """Membros com nome parecido, do mais parecido para o menos."""
    notas = []
    for membro in membros:
        nota = max((difflib.SequenceMatcher(None, procurado, nome).ratio()
                    for nome in nomes_do_membro(membro)), default=0)
        if nota >= NOTA_MINIMA:
            notas.append((nota, membro))
    notas.sort(key=lambda item: -item[0])
    # Um vencedor claro conta como achado; notas muito próximas viram ambiguidade.
    if len(notas) >= 2 and notas[0][0] - notas[1][0] < FOLGA_DIFFLIB:
        return [membro for _, membro in notas]
    return [membro for _, membro in notas[:1]]


def procurar_membros(membros, texto):
    """Lista de candidatos da primeira etapa que achar alguém (vazia se ninguém).

    Uma lista com 1 membro = achou; com mais = ambíguo.
    """
    procurado = normalizar(texto)
    if not procurado:
        return []
    etapas = [
        lambda nome: nome == procurado,
        lambda nome: nome.startswith(procurado),
        lambda nome: procurado in nome,
    ]
    for regra in etapas:
        achados = _por_regra(membros, regra)
        if achados:
            return achados
    return _por_semelhanca(membros, procurado)


async def _membro_pelo_id(guild, membro_id):
    """Procura no cache e, se não estiver lá, pergunta ao Discord."""
    membro = guild.get_member(membro_id)
    if membro is not None:
        return membro
    try:
        return await guild.fetch_member(membro_id)
    except discord.HTTPException:
        return None


async def achar_membro(guild, texto):
    """Devolve o membro do servidor que combina com o texto.

    Lança commands.MemberNotFound se ninguém combinar e MembroAmbiguo se
    houver empate entre várias pessoas.
    """
    texto = texto.strip()
    combinou_id = _PADRAO_ID.match(texto)
    if combinou_id:
        membro = await _membro_pelo_id(guild, int(combinou_id.group(1) or combinou_id.group(2)))
        if membro is None:
            raise commands.MemberNotFound(texto)
        return membro

    # Sem o "Server Members Intent", guild.members só tem quem o bot já viu.
    candidatos = procurar_membros(guild.members, texto)
    if not candidatos:
        raise commands.MemberNotFound(texto)
    if len(candidatos) > 1:
        raise MembroAmbiguo(texto, candidatos)
    return candidatos[0]


class MembroFlexivel(commands.Converter, app_commands.Transformer):
    """Conversor do parâmetro "membro" do status.

    É as duas coisas ao mesmo tempo:
    - no !status (Converter) usa a nossa busca flexível com achar_membro;
    - no /status (Transformer do tipo "usuário") o Discord já mostra a lista
      de membros com autocomplete, então só devolvemos quem foi escolhido.
    """

    @property
    def type(self):
        return discord.AppCommandOptionType.user

    async def convert(self, ctx, argumento):
        if ctx.guild is None:
            raise commands.MemberNotFound(argumento)  # na DM não há membros
        return await achar_membro(ctx.guild, argumento)

    async def transform(self, interaction, valor):
        return valor
