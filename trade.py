"""Troca de bichinhos e moedas entre dois usuários.

Dividido em duas partes:
- Troca: só a lógica (quem oferece o quê, quem confirmou). Dá para testar sem Discord.
- ViewTroca e companhia: os botões, menus e formulários que aparecem no Discord.
"""
import discord

import banco
import catalogo
import titulos
from embeds import COR_AVISO, COR_ERRO, COR_PADRAO, COR_SUCESSO, EMOJI_RARIDADE, embed_troca, ordenar_por_raridade

TEMPO_LIMITE = 180  # segundos até a troca expirar (3 min)


# ---------- lógica da troca ----------

class Troca:
    def __init__(self, usuario_a, usuario_b):
        self.usuarios = [usuario_a, usuario_b]
        self.itens = {usuario_a: {}, usuario_b: {}}   # usuario -> {bichinho_id: qtd}
        self.moedas = {usuario_a: 0, usuario_b: 0}
        self.confirmados = set()

    def _mudou(self):
        # Regra de segurança: se a oferta muda, ninguém fica confirmado sem ver.
        self.confirmados.clear()

    def adicionar_item(self, usuario, bichinho_id, quantidade=1):
        """Põe bichinhos na oferta. Devolve uma mensagem de erro, ou None se deu certo."""
        if quantidade <= 0:
            return "A quantidade precisa ser maior que zero."
        ja_oferecido = self.itens[usuario].get(bichinho_id, 0)
        if banco.quantidade(usuario, bichinho_id) < ja_oferecido + quantidade:
            return "Você não tem bichinhos suficientes para oferecer."
        self.itens[usuario][bichinho_id] = ja_oferecido + quantidade
        self._mudou()
        return None

    def definir_moedas(self, usuario, valor):
        """Define quantas moedas o usuário oferece. Erro em texto, ou None."""
        if valor < 0:
            return "O valor não pode ser negativo."
        if banco.moedas(usuario) < valor:
            return "Você não tem moedas suficientes."
        self.moedas[usuario] = valor
        self._mudou()
        return None

    def confirmar(self, usuario):
        """Marca a confirmação. Devolve True quando os dois já confirmaram."""
        self.confirmados.add(usuario)
        return len(self.confirmados) == 2

    def executar(self):
        """Faz a troca no banco (tudo ou nada). True se deu certo."""
        a, b = self.usuarios
        return banco.trocar(a, self.itens[a], self.moedas[a], b, self.itens[b], self.moedas[b])

    def vazia(self):
        """True se ninguém ofereceu nada."""
        return not any(self.itens.values()) and not any(self.moedas.values())


# ---------- interface no Discord ----------

def _numero(texto):
    """Converte texto em inteiro; None se não for um número inteiro."""
    try:
        return int(texto.strip())
    except ValueError:
        return None


class ModalBichinho(discord.ui.Modal, title="Adicionar bichinho"):
    nome = discord.ui.TextInput(label="Nome do bichinho", placeholder="Ex.: Sapo Musgoso")
    quantidade = discord.ui.TextInput(label="Quantidade", default="1", max_length=4)

    def __init__(self, view_troca):
        super().__init__()
        self.view_troca = view_troca

    async def on_submit(self, interaction):
        bichinho = catalogo.buscar(self.nome.value)
        qtd = _numero(self.quantidade.value)
        if bichinho is None:
            await interaction.response.send_message("Não encontrei esse bichinho.", ephemeral=True)
            return
        if qtd is None:
            await interaction.response.send_message("A quantidade precisa ser um número.", ephemeral=True)
            return
        erro = self.view_troca.troca.adicionar_item(interaction.user.id, bichinho["id"], qtd)
        await self.view_troca.responder_mudanca(interaction, erro)


class ModalMoedas(discord.ui.Modal, title="Oferecer moedas"):
    valor = discord.ui.TextInput(label="Quantas moedas você oferece?", placeholder="Ex.: 50", max_length=9)

    def __init__(self, view_troca):
        super().__init__()
        self.view_troca = view_troca

    async def on_submit(self, interaction):
        valor = _numero(self.valor.value)
        if valor is None:
            await interaction.response.send_message("Digite um número inteiro.", ephemeral=True)
            return
        erro = self.view_troca.troca.definir_moedas(interaction.user.id, valor)
        await self.view_troca.responder_mudanca(interaction, erro)


class SelectBichinho(discord.ui.Select):
    """Menu com até 25 bichinhos do inventário de quem clicou."""

    def __init__(self, view_troca, usuario_id):
        self.view_troca = view_troca
        inventario = banco.inventario(usuario_id)
        bichinhos = [catalogo.por_id(i) for i in inventario]
        bichinhos = ordenar_por_raridade([b for b in bichinhos if b is not None])[:25]  # limite do Discord

        opcoes = [
            discord.SelectOption(
                label=b["nome"][:100],
                value=b["id"],
                emoji=EMOJI_RARIDADE[b["raridade"]],
                description=f"Você tem {inventario[b['id']]}",
            )
            for b in bichinhos
        ]
        super().__init__(placeholder="Escolha bichinhos (1 de cada)", options=opcoes,
                         min_values=1, max_values=len(opcoes))

    async def callback(self, interaction):
        erros = []
        for bichinho_id in self.values:
            erro = self.view_troca.troca.adicionar_item(interaction.user.id, bichinho_id, 1)
            if erro:
                erros.append(f"{catalogo.por_id(bichinho_id)['nome']}: {erro}")
        await self.view_troca.responder_mudanca(interaction, "\n".join(erros) or None)


class ViewTroca(discord.ui.View):
    def __init__(self, usuario_a, usuario_b):
        super().__init__(timeout=TEMPO_LIMITE)
        self.usuario_a = usuario_a        # objetos discord.User (para mostrar o nome)
        self.usuario_b = usuario_b
        self.troca = Troca(usuario_a.id, usuario_b.id)
        self.mensagem = None              # mensagem da troca (preenchida pelo main)
        self.finalizada = False

    def embed_atual(self, aviso=None, cor=COR_PADRAO):
        lados = []
        for usuario in (self.usuario_a, self.usuario_b):
            lados.append((usuario.display_name, self.troca.itens[usuario.id],
                          self.troca.moedas[usuario.id], usuario.id in self.troca.confirmados))
        return embed_troca(lados, aviso, cor)

    async def interaction_check(self, interaction):
        # Só os dois participantes podem mexer na troca.
        if interaction.user.id in self.troca.usuarios:
            return True
        await interaction.response.send_message("Essa troca não é sua! 🙅", ephemeral=True)
        return False

    async def atualizar_mensagem(self):
        """Redesenha o embed da troca com as ofertas atuais."""
        if self.mensagem is not None:
            await self.mensagem.edit(embed=self.embed_atual(), view=self)

    async def responder_mudanca(self, interaction, erro):
        """Usado pelos menus e formulários: avisa o erro ou atualiza a troca."""
        if self.finalizada:
            await interaction.response.send_message("Essa troca já terminou.", ephemeral=True)
            return
        if erro:
            await interaction.response.send_message(erro, ephemeral=True)
            return
        await interaction.response.send_message("Oferta atualizada! ✅", ephemeral=True)
        await self.atualizar_mensagem()

    def _desativar_tudo(self):
        for item in self.children:
            item.disabled = True
        self.finalizada = True
        self.stop()

    @discord.ui.button(label="Escolher bichinho", emoji="📦", style=discord.ButtonStyle.secondary)
    async def escolher(self, interaction, button):
        menu = SelectBichinho(self, interaction.user.id)
        if not menu.options:
            await interaction.response.send_message("Você não tem bichinhos para oferecer.", ephemeral=True)
            return
        view = discord.ui.View(timeout=TEMPO_LIMITE)
        view.add_item(menu)
        # Mensagem "ephemeral": só quem clicou vê o próprio inventário.
        await interaction.response.send_message(view=view, ephemeral=True)

    @discord.ui.button(label="Digitar bichinho", emoji="⌨️", style=discord.ButtonStyle.secondary)
    async def digitar(self, interaction, button):
        await interaction.response.send_modal(ModalBichinho(self))

    @discord.ui.button(label="Moedas", emoji="🪙", style=discord.ButtonStyle.secondary)
    async def moedas(self, interaction, button):
        await interaction.response.send_modal(ModalMoedas(self))

    @discord.ui.button(label="Confirmar", emoji="✅", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction, button):
        if self.troca.vazia():
            await interaction.response.send_message("Adicione algo antes de confirmar.", ephemeral=True)
            return
        if not self.troca.confirmar(interaction.user.id):
            await interaction.response.edit_message(embed=self.embed_atual(), view=self)
            return

        # Os dois confirmaram: a troca acontece de verdade (banco.trocar é tudo ou nada).
        self._desativar_tudo()
        deu_certo = self.troca.executar()
        if deu_certo:
            embed = self.embed_atual("🎉 Troca concluída com sucesso!", COR_SUCESSO)
        else:
            embed = self.embed_atual("❌ A troca falhou: alguém não tem mais o que ofereceu. Nada mudou.",
                                     COR_ERRO)
        await interaction.response.edit_message(embed=embed, view=self)
        if deu_certo:
            # Trocas contam para títulos (e o bichinho recebido pode completar a coleção).
            for usuario_id in self.troca.usuarios:
                await titulos.verificar_e_anunciar(interaction.channel, usuario_id)

    @discord.ui.button(label="Cancelar", emoji="✖️", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction, button):
        self._desativar_tudo()
        embed = self.embed_atual(f"Troca cancelada por {interaction.user.display_name}.", COR_ERRO)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.finalizada:
            return
        self._desativar_tudo()
        if self.mensagem is not None:
            try:
                await self.mensagem.edit(embed=self.embed_atual("⌛ A troca expirou.", COR_AVISO), view=self)
            except discord.HTTPException:
                pass  # a mensagem pode ter sido apagada
