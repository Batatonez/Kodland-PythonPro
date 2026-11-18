"""Chatbot simples: responde quando chamam o SpriteRNG pelo nome, por @ ou por reply."""
import random
import re

from catalogo import normalizar

# Nome principal do bot e outros nomes pelos quais ele também atende.
NOME_BOT = "SpriteRNG"
APELIDOS = ["sprite", "sprites", "rng"]


def _colapsar(texto: str) -> str:
    """Junta letras repetidas: "spriteeeee" vira "sprite"."""
    return re.sub(r"(.)\1+", r"\1", texto)


# Os nomes são comparados já normalizados (sem acento, minúsculos) e colapsados,
# assim "SPRITE", "spriteeee", "rrrnggg" e "spriterrrnnnggg" são reconhecidos.
_NOMES = {_colapsar(normalizar(nome)) for nome in [NOME_BOT, *APELIDOS]}


def foi_chamado(texto: str) -> bool:
    """True se alguma palavra da mensagem é o nome (ou apelido) do bot."""
    palavras = normalizar(texto).split()
    return any(_colapsar(palavra) in _NOMES for palavra in palavras)


def remover_nome(texto: str) -> str:
    """Retorna a mensagem sem o nome do bot, para descobrir o que a pessoa quer."""
    palavras = normalizar(texto).split()
    return " ".join(p for p in palavras if _colapsar(p) not in _NOMES)


# Cada intenção tem palavras-chave (já sem acento) e algumas respostas possíveis.
# A PRIMEIRA intenção da lista que tiver uma palavra-chave na mensagem é usada,
# por isso os assuntos específicos vêm antes de "tchau" e "oi".
INTENCOES = [
    (
        {"obrigado", "obrigada", "valeu", "vlw", "brigado", "obg"},
        ["Por nada! 😊", "Disponha! Boa captura! 🐾", "Imagina! Os bichinhos agradecem também."],
    ),
    (
        {"titulo", "titulos", "cargo", "cargos", "cor", "apelido", "conquista", "conquistas", "medalha"},
        ["Jogando você desbloqueia títulos! Veja todos em `!titulos` e equipe com `!titulo <nome>`: "
         "seu nome ganha a cor do título e ele aparece ao lado do seu apelido. 🏅",
         "Tem títulos secretos escondidos por aí... eles aparecem como ❓ ??? até alguém conseguir. 🤫 "
         "Abra o `!hud` e vá na aba 🏅 Títulos!",
         "Não quer o título no apelido? Desligue no `!hud` (botão \"Título no apelido\"). "
         "A cor do cargo continua! 🎨"],
    ),
    (
        {"capturar", "captura", "capturas", "pegar", "foto", "camera", "achar", "encontrar"},
        ["Manda uma foto de um objeto junto com `!capturar` (ou use `/capturar` e anexe a imagem). "
         "Eu vejo o objeto e sorteio um bichinho do elemento dele! 📸",
         "Fotografe algo como um gato, uma planta ou uma xícara e use `!capturar`. "
         "Foto bem nítida (90%+ de certeza) dá bônus nas raridades altas! 🎯"],
    ),
    (
        {"autoroll", "automatico", "auto", "afk"},
        ["`!autoroll` liga o roll automático: eu rolo por você a cada 25 s e só aviso quando sair algo raro. "
         "Use de novo pra desligar! 🤖",
         "Com o autoroll ligado o `!roll` fica bloqueado, mas o `!capturar` continua liberado. "
         "Se você sumir por 10 min, eu desligo sozinho. 💤"],
    ),
    (
        {"hud", "painel", "configuracao", "configuracoes", "config"},
        ["`/hud` abre seu painel pessoal (só você vê): estatísticas, esperas e as configurações do autoroll. "
         "No `!hud` é só clicar em \"Abrir meu HUD\". 🎮"],
    ),
    (
        {"status", "estatisticas", "perfil", "stats"},
        ["`!status @amigo` (ou o nome dele) mostra os rolls, o melhor bichinho e os pontos de alguém. "
         "Sem nome, mostra os seus! 📊"],
    ),
    (
        {"roll", "girar", "sortear", "sorteio", "gacha"},
        ["`!roll` sorteia um bichinho de qualquer elemento, sem precisar de foto. Dá pra usar a cada 5 segundos! 🎲",
         "Sem paciência pra esperar o `!roll`? Use `!comprar` e gaste moedas num sorteio extra! 🪙"],
    ),
    (
        {"trocar", "troca", "trade", "negociar"},
        ["Use `!trade @amigo`: cada um adiciona bichinhos e moedas, e a troca só acontece quando os dois confirmam. 🔄",
         "Quer dar um bichinho de presente? `!dar @amigo <bichinho>`. Pra trocar, `!trade @amigo`. 🎁"],
    ),
    (
        {"moeda", "moedas", "dinheiro", "vender", "comprar", "loja", "grana"},
        ["Venda repetidos com `!vender <bichinho>` e use as moedas no `!comprar` (sorteio extra). "
         "Veja seu saldo com `!moedas`. 🪙"],
    ),
    (
        {"raro", "raros", "raridade", "chance", "chances", "mitico", "lendario", "epico", "sorte"},
        ["Chances: Comum 60%, Incomum 25%, Raro 10%, Épico 4%, Lendário 0,9% e Mítico 0,1%. "
         "Foto bem nítida dobra as chances de Épico pra cima! 🌈",
         "Míticos são lendas de verdade: 0,1% de chance. Já viu um brilhando? ✨"],
    ),
    (
        {"missao", "diaria", "desafio"},
        ["Todo dia tem um elemento sorteado. Veja em `!missao` e capture um objeto dele pra ganhar um roll grátis! 📜"],
    ),
    (
        {"elemento", "elementos", "fogo", "agua", "natureza", "eletrico", "mistico", "fera"},
        ["São 6 elementos: 🌿 Natureza, 🔥 Fogo, 💧 Água, ⚡ Elétrico, 🔮 Místico e 🐾 Fera. "
         "O objeto da foto decide o elemento!"],
    ),
    (
        {"inventario", "inv", "colecao", "index", "rank", "ranking", "bichinhos"},
        ["`!inv` mostra seus bichinhos, `!index` mostra quanto da coleção você já descobriu "
         "e `!rank` mostra os maiores colecionadores! 🏆"],
    ),
    (
        {"ajuda", "comandos", "help", "fazer", "funciona", "jogar", "como"},
        ["Eu sou o SpriteRNG: capturo bichinhos elementais nas suas fotos! Digite `!ajuda` para ver todos os comandos."],
    ),
    (
        {"tchau", "flw", "falou", "adeus", "bye"},
        ["Até mais! 👋", "Tchau! Seus bichinhos vão sentir sua falta. 🐾", "Falou! Boa sorte nos rolls! 🍀"],
    ),
    (
        {"oi", "ola", "eai", "opa", "salve", "bom", "boa", "hey", "hello", "tudo", "beleza", "suave"},
        ["Oi! Pronto pra capturar uns bichinhos? 😄", "Salve! Manda uma foto com `!capturar` que eu vejo o que aparece!",
         "Olá! Que tal um `!roll` pra testar a sorte? 🎲"],
    ),
]

# Quando só chamam o nome, sem pedir nada.
RESPOSTAS_CHAMADO = [
    "Oi, me chamou? 👀",
    "Tô aqui! Bora capturar bichinhos?",
    "Presente! Digite `!ajuda` se quiser ver o que eu sei fazer.",
]

# Quando pedem algo que o bot não entendeu.
RESPOSTAS_PADRAO = [
    "Hmm, não entendi muito bem. 🤔 Tenta `!ajuda` pra ver o que eu sei fazer!",
    "Essa eu não sei... mas sei tudo de bichinhos! Veja `!ajuda`.",
    "Não entendi, mas que tal tentar a sorte com `!roll`? 🎲",
]


def responder(texto: str) -> str:
    """Escolhe uma resposta de acordo com as palavras da mensagem."""
    pedido = remover_nome(texto)
    if not pedido:
        return random.choice(RESPOSTAS_CHAMADO)

    palavras = set(pedido.split())
    for chaves, respostas in INTENCOES:
        if palavras & chaves:
            return random.choice(respostas)
    return random.choice(RESPOSTAS_PADRAO)
