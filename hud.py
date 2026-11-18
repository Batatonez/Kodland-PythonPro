"""HUD pessoal: um painel com estatísticas e controles que só o dono vê.

Mensagens efêmeras ("só você pode ver") só existem como resposta a uma
interação (comando de barra, botão, menu). Por isso:
- /hud responde direto com o HUD efêmero;
- !hud manda uma mensagem normal com o botão "Abrir meu HUD", e quem clica
  recebe o PRÓPRIO HUD efêmero (cada pessoa vê o seu).

O HUD tem duas abas (botões no topo):
- 📊 Status: estatísticas, autoroll, avisos, auto-venda e título rápido;
- 🏅 Títulos: todos os títulos, 5 por página, com botão para equipar.

O Discord aceita no máximo 5 linhas de componentes (5 botões por linha,
ou 1 menu por linha). Layout de cada aba:
  Status:  0 abas + autoroll + atualizar | 1 avisos | 2 auto-venda | 3 título | 4 título no apelido
  Títulos: 0 abas + atualizar | 1 um botão por título da página | 2 remover + apelido | 3 ◀ ▶
"""
import discord

import autoroll
import banco
import cargos
import catalogo
import embeds
import titulos

TEMPO_LIMITE = 5 * 60         # o HUD para de responder depois de 5 min
TEMPO_LIMITE_BOTAO = 15 * 60  # o botão "Abrir meu HUD" dura 15 min
TITULOS_POR_PAGINA = 5        # um botão por título: cabe numa linha só
ABA_STATUS, ABA_TITULOS = "status", "titulos"


def montar_embed(usuario, esperas):
    """Junta os dados do usuário e monta o embed da aba Status.

    esperas = {"roll": segundos, "capturar": segundos} (as constantes do main).
    """
    uid = usuario.id
    return embeds.embed_hud(
        nome=usuario.display_name,
        stats=banco.estatisticas(uid),
        melhor=banco.melhor_bichinho(uid),
        moedas=banco.moedas(uid),
        qtd_inventario=sum(banco.inventario(uid).values()),
        qtd_descobertos=len(banco.descobertos(uid)),
        autoroll_ligado=autoroll.esta_ligado(uid),
        proximo_autoroll=autoroll.segundos_para_proximo(uid),
        espera_roll=banco.tempo_restante(uid, "roll", esperas["roll"]),
        espera_capturar=banco.tempo_restante(uid, "capturar", esperas["capturar"]),
        config=banco.configuracao(uid),
        titulo=titulos.equipado(uid),
        qtd_titulos=len(banco.titulos_desbloqueados(uid)),
        total_titulos=len(titulos.TITULOS),
        titulo_no_apelido=banco.titulo_no_apelido(uid),
    )


def total_paginas_titulos():
    return (len(titulos.TITULOS) + TITULOS_POR_PAGINA - 1) // TITULOS_POR_PAGINA


def titulos_da_pagina(pagina):
    """Os títulos de uma página da aba Títulos (pagina começa em 0)."""
    inicio = pagina * TITULOS_POR_PAGINA
    return titulos.TITULOS[inicio:inicio + TITULOS_POR_PAGINA]


# ---------- menus da aba Status ----------

class SelectAviso(discord.ui.Select):
    """Escolhe a partir de qual raridade o autoroll avisa no canal."""

    def __init__(self, view_hud):
        opcoes = [
            discord.SelectOption(label=f"Avisar a partir de: {dados['nome']}", value=raridade,
                                 emoji=embeds.EMOJI_RARIDADE[raridade])
            for raridade, dados in catalogo.RARIDADES.items()
        ]
        super().__init__(placeholder="Avisar a partir de...", options=opcoes, row=1)
        self.view_hud = view_hud

    async def callback(self, interaction):
        banco.salvar_configuracao(self.view_hud.dono.id, "aviso_minimo", self.values[0])
        await self.view_hud.redesenhar(interaction)


class SelectAutoVender(discord.ui.Select):
    """Escolhe quais raridades o autoroll vende na hora."""

    def __init__(self, view_hud):
        opcoes = [
            discord.SelectOption(label=f"Autoroll: {nome}", value=valor)
            for valor, nome in embeds.NOMES_AUTO_VENDER.items()
        ]
        super().__init__(placeholder="Vender automaticamente no autoroll...", options=opcoes, row=2)
        self.view_hud = view_hud

    async def callback(self, interaction):
        banco.salvar_configuracao(self.view_hud.dono.id, "auto_vender", self.values[0])
        await self.view_hud.redesenhar(interaction)


NENHUM = "nenhum"  # valor da opção "sem título" no menu


class SelectTitulo(discord.ui.Select):
    """Atalho para equipar um título desbloqueado (até 24 + "Nenhum": limite de 25 opções)."""

    def __init__(self, view_hud):
        self.view_hud = view_hud
        super().__init__(placeholder="Título equipado...", options=self._opcoes(), row=3)

    def _opcoes(self):
        uid = self.view_hud.dono.id
        equipado_id = banco.titulo_equipado(uid)
        # Os mais difíceis ficam no fim da lista: se passar de 24, mostra os 24 últimos.
        meus = titulos.desbloqueados(uid)[-24:]
        opcoes = [discord.SelectOption(label="Nenhum título", value=NENHUM, emoji="➖",
                                       default=equipado_id is None)]
        for titulo in meus:
            opcoes.append(discord.SelectOption(label=titulo["nome"], value=titulo["id"], emoji=titulo["emoji"],
                                               default=titulo["id"] == equipado_id))
        return opcoes

    def atualizar(self):
        self.options = self._opcoes()

    async def callback(self, interaction):
        escolhido = None if self.values[0] == NENHUM else titulos.por_id(self.values[0])
        await self.view_hud.equipar(interaction, escolhido)


# ---------- botões da aba Títulos ----------

class BotaoTitulo(discord.ui.Button):
    """Botão de um título na aba Títulos: Equipar, Equipado ✓ ou 🔒 (bloqueado)."""

    def __init__(self, view_hud, titulo, numero, desbloqueado, equipado):
        self.view_hud = view_hud
        self.titulo = titulo
        if not desbloqueado:
            # Só o cadeado e o número (secretos não podem revelar o emoji).
            super().__init__(label=str(numero), emoji="🔒", style=discord.ButtonStyle.secondary,
                             disabled=True, row=1)
        elif equipado:
            super().__init__(label=f"{numero}. Equipado ✓", emoji=titulo["emoji"],
                             style=discord.ButtonStyle.success, disabled=True, row=1)
        else:
            super().__init__(label=f"{numero}. Equipar", emoji=titulo["emoji"],
                             style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction):
        await self.view_hud.equipar(interaction, self.titulo)


# ---------- o HUD ----------

class ViewHUD(discord.ui.View):
    def __init__(self, dono, esperas):
        super().__init__(timeout=TEMPO_LIMITE)
        self.dono = dono
        self.esperas = esperas
        self.interacao = None  # interação que abriu o HUD (para desativar no timeout)
        self.aba = ABA_STATUS
        self.pagina = 0        # página da aba Títulos (começa em 0)
        titulos.verificar_titulos(dono.id)  # pega conquistas antigas (jogadores de antes dos títulos)
        self.select_aviso = SelectAviso(self)
        self.select_vender = SelectAutoVender(self)
        self.select_titulo = SelectTitulo(self)
        self.botoes_titulos = []
        self.atualizar_controles()

    # ----- montagem -----

    def embed_atual(self):
        if self.aba == ABA_TITULOS:
            return self.embed_titulos()
        return montar_embed(self.dono, self.esperas)

    def embed_titulos(self):
        uid = self.dono.id
        lista = titulos_da_pagina(self.pagina)
        return embeds.embed_lista_titulos(
            self.dono.display_name, lista, self.pagina * TITULOS_POR_PAGINA + 1,
            banco.titulos_desbloqueados(uid), banco.titulo_equipado(uid), titulos.coletar_dados(uid),
            self.pagina + 1, total_paginas_titulos())

    def _por(self, item, linha):
        """Adiciona um componente na linha escolhida."""
        item.row = linha
        self.add_item(item)

    def _montar_aba_status(self):
        self._por(self.botao_autoroll, 0)
        self._por(self.botao_atualizar, 0)
        self._por(self.select_aviso, 1)
        self._por(self.select_vender, 2)
        self._por(self.select_titulo, 3)
        self._por(self.botao_apelido, 4)

    def _montar_aba_titulos(self):
        self._por(self.botao_atualizar, 0)
        uid = self.dono.id
        meus = banco.titulos_desbloqueados(uid)
        equipado_id = banco.titulo_equipado(uid)
        inicio = self.pagina * TITULOS_POR_PAGINA + 1
        self.botoes_titulos = [
            BotaoTitulo(self, t, numero, t["id"] in meus, t["id"] == equipado_id)
            for numero, t in enumerate(titulos_da_pagina(self.pagina), start=inicio)
        ]
        for botao in self.botoes_titulos:
            self._por(botao, 1)
        self.botao_remover.disabled = equipado_id is None
        self._por(self.botao_remover, 2)
        self._por(self.botao_apelido, 2)
        self.botao_anterior.disabled = self.pagina == 0
        self.botao_proxima.disabled = self.pagina >= total_paginas_titulos() - 1
        self._por(self.botao_anterior, 3)
        self._por(self.botao_proxima, 3)

    def _atualizar_abas(self):
        """A aba aberta fica azul e desabilitada; a outra fica cinza e clicável."""
        for botao, aba in ((self.botao_aba_status, ABA_STATUS), (self.botao_aba_titulos, ABA_TITULOS)):
            ativa = self.aba == aba
            botao.disabled = ativa
            botao.style = discord.ButtonStyle.primary if ativa else discord.ButtonStyle.secondary

    def atualizar_controles(self):
        """Refaz os componentes da aba atual mostrando o estado de agora."""
        uid = self.dono.id
        ligado = autoroll.esta_ligado(uid)
        self.botao_autoroll.label = "Autoroll: ligado" if ligado else "Autoroll: desligado"
        self.botao_autoroll.style = discord.ButtonStyle.success if ligado else discord.ButtonStyle.secondary

        config = banco.configuracao(uid)
        for opcao in self.select_aviso.options:
            opcao.default = opcao.value == config["aviso_minimo"]
        for opcao in self.select_vender.options:
            opcao.default = opcao.value == config["auto_vender"]
        self.select_titulo.atualizar()

        no_apelido = banco.titulo_no_apelido(uid)
        self.botao_apelido.label = f"Título no apelido: {'ligado' if no_apelido else 'desligado'}"
        self.botao_apelido.style = discord.ButtonStyle.success if no_apelido else discord.ButtonStyle.secondary

        self._atualizar_abas()
        self.clear_items()
        self._por(self.botao_aba_status, 0)
        self._por(self.botao_aba_titulos, 0)
        if self.aba == ABA_TITULOS:
            self._montar_aba_titulos()
        else:
            self._montar_aba_status()

    # ----- respostas -----

    async def redesenhar(self, interaction):
        """Atualiza o próprio HUD efêmero depois de um clique."""
        self.atualizar_controles()
        await interaction.response.edit_message(embed=self.embed_atual(), view=self)

    async def redesenhar_adiado(self, interaction, avisos):
        """Igual ao redesenhar, mas para quando já respondemos com defer() (ação demorada)."""
        self.atualizar_controles()
        await interaction.edit_original_response(embed=self.embed_atual(), view=self)
        if avisos:
            texto = "\n".join(f"⚠️ {aviso}" for aviso in avisos)
            await interaction.followup.send(texto, ephemeral=True)

    async def equipar(self, interaction, titulo):
        """Equipa (ou tira, se titulo=None) e aplica cargo/apelido no servidor."""
        if titulo is not None and titulo["id"] not in banco.titulos_desbloqueados(self.dono.id):
            await interaction.response.send_message("Você ainda não desbloqueou esse título.", ephemeral=True)
            return
        # Criar cargo e mudar apelido pode passar dos 3 s que o Discord espera: defer() avisa que vamos demorar.
        await interaction.response.defer()
        # interaction.user (e não self.dono) porque é ele o membro do servidor onde o clique aconteceu.
        avisos = await cargos.equipar(interaction.user, titulo)
        await self.redesenhar_adiado(interaction, avisos)

    async def interaction_check(self, interaction):
        # Mensagem efêmera já é só do dono, mas conferir não custa nada.
        if interaction.user.id != self.dono.id:
            await interaction.response.send_message("Este HUD não é seu. Use `/hud`.", ephemeral=True)
            return False
        return True

    # ----- botões (as linhas são definidas em atualizar_controles) -----

    @discord.ui.button(label="Status", emoji="📊", style=discord.ButtonStyle.primary)
    async def botao_aba_status(self, interaction, button):
        self.aba = ABA_STATUS
        await self.redesenhar(interaction)

    @discord.ui.button(label="Títulos", emoji="🏅", style=discord.ButtonStyle.secondary)
    async def botao_aba_titulos(self, interaction, button):
        self.aba = ABA_TITULOS
        await self.redesenhar(interaction)

    @discord.ui.button(label="Autoroll: desligado", style=discord.ButtonStyle.secondary)
    async def botao_autoroll(self, interaction, button):
        # Liga no canal onde o HUD foi aberto (é lá que chegam os avisos).
        autoroll.alternar(self.dono.id, interaction.channel)
        await self.redesenhar(interaction)

    @discord.ui.button(label="Atualizar", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def botao_atualizar(self, interaction, button):
        await self.redesenhar(interaction)

    @discord.ui.button(label="Título no apelido: ligado", style=discord.ButtonStyle.success)
    async def botao_apelido(self, interaction, button):
        await interaction.response.defer()
        _, avisos = await cargos.alternar_titulo_no_apelido(interaction.user)
        await self.redesenhar_adiado(interaction, avisos)

    @discord.ui.button(label="Remover título", emoji="✖️", style=discord.ButtonStyle.danger)
    async def botao_remover(self, interaction, button):
        await self.equipar(interaction, None)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def botao_anterior(self, interaction, button):
        self.pagina = max(0, self.pagina - 1)
        await self.redesenhar(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def botao_proxima(self, interaction, button):
        self.pagina = min(total_paginas_titulos() - 1, self.pagina + 1)
        await self.redesenhar(interaction)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.interacao:
            try:
                await self.interacao.edit_original_response(view=self)
            except discord.HTTPException:
                pass


class ViewAbrirHUD(discord.ui.View):
    """Botão público do !hud: cada um que clica recebe o seu HUD efêmero."""

    def __init__(self, esperas):
        super().__init__(timeout=TEMPO_LIMITE_BOTAO)
        self.esperas = esperas
        self.mensagem = None

    @discord.ui.button(label="Abrir meu HUD", emoji="🎮", style=discord.ButtonStyle.primary)
    async def abrir(self, interaction, button):
        view = ViewHUD(interaction.user, self.esperas)
        await interaction.response.send_message(embed=view.embed_atual(), view=view, ephemeral=True)
        view.interacao = interaction

    async def on_timeout(self):
        self.abrir.disabled = True
        if self.mensagem:
            try:
                await self.mensagem.edit(view=self)
            except discord.HTTPException:
                pass
