"""Autoroll: o bot faz rolls sozinho para o usuário, de tempos em tempos.

Cada usuário com autoroll ligado tem uma tarefa (asyncio.Task) rodando em
segundo plano. As tarefas ficam só na memória: se o bot reiniciar, todos os
autorolls voltam desligados (é de propósito, para ninguém ficar rolando para
sempre sem estar por perto).
"""
import asyncio
import time
import traceback

import banco
import catalogo
import embeds
import sorteio
import titulos

# ---------- constantes ajustáveis ----------

INTERVALO_AUTOROLL = 25        # segundos entre um autoroll e outro
AUTOROLL_INATIVIDADE = 10 * 60  # desliga se o usuário ficar esse tempo sem mandar mensagem

# ---------- estado em memória ----------

_tarefas = {}            # usuario_id -> asyncio.Task do autoroll
_ultima_atividade = {}   # usuario_id -> momento (time.time()) da última mensagem
_proximo_roll = {}       # usuario_id -> momento previsto do próximo autoroll


# ---------- regras (funções simples, fáceis de testar) ----------

def _ordem(raridade):
    return catalogo.RARIDADES[raridade]["ordem"]


def deve_avisar(raridade, aviso_minimo):
    """True se a raridade é igual ou acima da escolhida para aviso."""
    return _ordem(raridade) >= _ordem(aviso_minimo)


def deve_vender(raridade, auto_vender):
    """True se a raridade deve ser vendida na hora ("nada" nunca vende)."""
    if auto_vender == "nada":
        return False
    return _ordem(raridade) <= _ordem(auto_vender)


def fazer_roll(usuario_id):
    """Faz um autoroll: sorteia, entrega e vende se estiver configurado.

    Devolve (bichinho, novo, moedas_ganhas).
    """
    bichinho = sorteio.sortear()
    # Entrega antes de vender: assim ele conta como descoberto e nas estatísticas.
    novo = sorteio.entregar(usuario_id, bichinho, "autoroll")
    ganho = 0
    if deve_vender(bichinho["raridade"], banco.configuracao(usuario_id)["auto_vender"]):
        if banco.remover_bichinho(usuario_id, bichinho["id"]):
            ganho = banco.VALOR_VENDA[bichinho["raridade"]]
            banco.alterar_moedas(usuario_id, ganho)
    return bichinho, novo, ganho


# ---------- atividade ----------

def registrar_atividade(usuario_id):
    """Marca que o usuário acabou de fazer algo (chamado no on_message)."""
    _ultima_atividade[usuario_id] = time.time()


def esta_inativo(usuario_id):
    """True se o usuário passou do limite de tempo sem atividade."""
    ultima = _ultima_atividade.get(usuario_id, 0)
    return time.time() - ultima > AUTOROLL_INATIVIDADE


# ---------- avisos no canal ----------

async def _aviso_simples(canal, usuario_id, bichinho, novo, ganho):
    """Aviso padrão (sem imagem). O main troca por um com sprite via definir_aviso."""
    embed = embeds.embed_captura(bichinho, novo, "🤖 Autoroll!")
    await canal.send(content=f"<@{usuario_id}>", embed=embed)


_funcao_aviso = _aviso_simples


def definir_aviso(funcao):
    """Troca a função que manda o aviso de bichinho raro no canal."""
    global _funcao_aviso
    _funcao_aviso = funcao


async def _mandar(canal, texto):
    """Manda um texto no canal sem deixar um erro do Discord derrubar a tarefa."""
    try:
        await canal.send(texto)
    except Exception as erro:
        print(f"Autoroll: não consegui mandar mensagem no canal: {erro!r}")


# ---------- a tarefa de cada usuário ----------

async def _um_roll(usuario_id, canal):
    """Faz um autoroll e avisa no canal se a raridade for alta o bastante."""
    bichinho, novo, ganho = fazer_roll(usuario_id)
    aviso_minimo = banco.configuracao(usuario_id)["aviso_minimo"]
    if deve_avisar(bichinho["raridade"], aviso_minimo):
        await _funcao_aviso(canal, usuario_id, bichinho, novo, ganho)
    # Título novo é sempre anunciado, mesmo quando o roll foi silencioso.
    await titulos.verificar_e_anunciar(canal, usuario_id)


async def _loop(usuario_id, canal):
    """Repete o autoroll até ser cancelado ou o usuário ficar inativo."""
    try:
        while True:
            _proximo_roll[usuario_id] = time.time() + INTERVALO_AUTOROLL
            await asyncio.sleep(INTERVALO_AUTOROLL)
            if esta_inativo(usuario_id):
                tempo = embeds.formatar_tempo(AUTOROLL_INATIVIDADE)
                await _mandar(canal, f"<@{usuario_id}> seu autoroll foi desligado: "
                                     f"{tempo} sem mensagens suas por aqui. 💤")
                return
            try:
                await _um_roll(usuario_id, canal)
            except Exception:
                # Sem isso, um erro mataria a tarefa sem ninguém perceber.
                print(f"Erro no autoroll do usuário {usuario_id}:")
                traceback.print_exc()
    finally:
        # Só limpa se a tarefa registrada ainda é esta (não apaga uma religada).
        if _tarefas.get(usuario_id) is asyncio.current_task():
            del _tarefas[usuario_id]
            _proximo_roll.pop(usuario_id, None)


# ---------- interface usada pelos comandos e pelo HUD ----------

def esta_ligado(usuario_id):
    """True se o autoroll do usuário está rodando."""
    tarefa = _tarefas.get(usuario_id)
    return tarefa is not None and not tarefa.done()


def ligar(usuario_id, canal):
    """Liga o autoroll no canal. Devolve False se já estava ligado."""
    if esta_ligado(usuario_id):
        return False
    registrar_atividade(usuario_id)  # ligar já conta como atividade
    _tarefas[usuario_id] = asyncio.create_task(_loop(usuario_id, canal))
    return True


def desligar(usuario_id):
    """Desliga o autoroll. Devolve False se já estava desligado."""
    tarefa = _tarefas.pop(usuario_id, None)
    _proximo_roll.pop(usuario_id, None)
    if tarefa is None or tarefa.done():
        return False
    tarefa.cancel()  # a tarefa para no próximo await (no sleep, normalmente)
    return True


def alternar(usuario_id, canal):
    """Liga se estiver desligado, desliga se estiver ligado. Devolve o novo estado."""
    if esta_ligado(usuario_id):
        desligar(usuario_id)
        return False
    ligar(usuario_id, canal)
    return True


def segundos_para_proximo(usuario_id):
    """Quanto falta para o próximo autoroll, ou None se estiver desligado."""
    if not esta_ligado(usuario_id) or usuario_id not in _proximo_roll:
        return None
    return max(0.0, _proximo_roll[usuario_id] - time.time())
