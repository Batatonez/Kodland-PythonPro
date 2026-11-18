"""Banco de dados do jogo (SQLite).

Guarda moedas, inventário, bichinhos descobertos, cooldowns, estatísticas de
rolls e configurações de cada usuário.
"""
import os
import sqlite3
import time

PASTA = os.path.dirname(os.path.abspath(__file__))
CAMINHO_BANCO = os.path.join(PASTA, "dados", "jogo.db")

MOEDAS_INICIAIS = 100

# Pontos de cada raridade (usado no ranking)
PONTOS_RARIDADE = {
    "comum": 1,
    "incomum": 3,
    "raro": 10,
    "epico": 30,
    "lendario": 100,
    "mitico": 500,
}

# Moedas recebidas ao vender um bichinho de cada raridade (!vender e auto-venda)
VALOR_VENDA = {
    "comum": 5,
    "incomum": 15,
    "raro": 50,
    "epico": 150,
    "lendario": 500,
    "mitico": 2500,
}

# Tipos de roll contados nas estatísticas.
# O roll grátis da missão conta como "roll".
TIPOS_ROLL = ["roll", "autoroll", "comprar", "capturar"]

# Configurações de cada usuário: valor padrão e valores aceitos.
# auto_vender = maior raridade vendida na hora pelo autoroll ("nada" = não vende).
CONFIGURACOES_PADRAO = {"aviso_minimo": "raro", "auto_vender": "nada"}
VALORES_CONFIGURACAO = {
    "aviso_minimo": list(PONTOS_RARIDADE),
    "auto_vender": ["nada", "comum", "incomum"],
}


def configurar(caminho):
    """Troca o arquivo do banco (útil para testes)."""
    global CAMINHO_BANCO
    CAMINHO_BANCO = caminho


def conectar():
    """Abre uma conexão e cria as tabelas se ainda não existirem."""
    pasta = os.path.dirname(os.path.abspath(CAMINHO_BANCO))
    os.makedirs(pasta, exist_ok=True)
    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.execute("PRAGMA foreign_keys = ON")
    with conexao:
        conexao.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY,
                moedas INTEGER NOT NULL DEFAULT 100,
                criado_em REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inventario (
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                bichinho_id TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                PRIMARY KEY (usuario_id, bichinho_id)
            );
            CREATE TABLE IF NOT EXISTS descobertos (
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                bichinho_id TEXT NOT NULL,
                descoberto_em REAL NOT NULL,
                PRIMARY KEY (usuario_id, bichinho_id)
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                acao TEXT NOT NULL,
                ultimo_uso REAL NOT NULL,
                PRIMARY KEY (usuario_id, acao)
            );
            CREATE TABLE IF NOT EXISTS estatisticas (
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                tipo TEXT NOT NULL,
                raridade TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                PRIMARY KEY (usuario_id, tipo, raridade)
            );
            CREATE TABLE IF NOT EXISTS configuracoes (
                usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id),
                aviso_minimo TEXT NOT NULL DEFAULT 'raro',
                auto_vender TEXT NOT NULL DEFAULT 'nada',
                titulo_equipado TEXT,
                titulo_no_apelido INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS contadores (
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                chave TEXT NOT NULL,
                valor INTEGER NOT NULL,
                PRIMARY KEY (usuario_id, chave)
            );
            CREATE TABLE IF NOT EXISTS titulos (
                usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                titulo_id TEXT NOT NULL,
                desbloqueado_em REAL NOT NULL,
                PRIMARY KEY (usuario_id, titulo_id)
            );
            CREATE TABLE IF NOT EXISTS cargos_titulo (
                guild_id INTEGER NOT NULL,
                titulo_id TEXT NOT NULL,
                cargo_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, titulo_id)
            );
            CREATE TABLE IF NOT EXISTS apelidos_originais (
                guild_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                apelido TEXT,
                PRIMARY KEY (guild_id, usuario_id)
            );
        """)
        _migrar(conexao)
    return conexao


# Colunas que entraram depois em tabelas que já existiam: (tabela, coluna, definição).
COLUNAS_NOVAS = [
    ("configuracoes", "titulo_equipado", "TEXT"),
    ("configuracoes", "titulo_no_apelido", "INTEGER NOT NULL DEFAULT 1"),
]


def _migrar(con):
    """Põe as colunas novas em bancos antigos (CREATE TABLE IF NOT EXISTS não faz isso)."""
    for tabela, coluna, definicao in COLUNAS_NOVAS:
        existentes = {linha[1] for linha in con.execute(f"PRAGMA table_info({tabela})")}
        if coluna not in existentes:
            con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


# ---------- funções auxiliares (usam uma conexão já aberta) ----------

def _garantir(con, usuario_id):
    con.execute(
        "INSERT OR IGNORE INTO usuarios (id, moedas, criado_em) VALUES (?, ?, ?)",
        (usuario_id, MOEDAS_INICIAIS, time.time()),
    )


def _quantidade(con, usuario_id, bichinho_id):
    linha = con.execute(
        "SELECT quantidade FROM inventario WHERE usuario_id = ? AND bichinho_id = ?",
        (usuario_id, bichinho_id),
    ).fetchone()
    return linha[0] if linha else 0


def _moedas(con, usuario_id):
    return con.execute("SELECT moedas FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()[0]


def _adicionar(con, usuario_id, bichinho_id, quantidade):
    con.execute(
        """INSERT INTO inventario (usuario_id, bichinho_id, quantidade) VALUES (?, ?, ?)
           ON CONFLICT(usuario_id, bichinho_id) DO UPDATE SET quantidade = quantidade + ?""",
        (usuario_id, bichinho_id, quantidade, quantidade),
    )
    con.execute(
        "INSERT OR IGNORE INTO descobertos (usuario_id, bichinho_id, descoberto_em) VALUES (?, ?, ?)",
        (usuario_id, bichinho_id, time.time()),
    )


def _remover(con, usuario_id, bichinho_id, quantidade):
    """Remove sem conferir (quem chama já conferiu). Apaga a linha se zerar."""
    con.execute(
        "UPDATE inventario SET quantidade = quantidade - ? WHERE usuario_id = ? AND bichinho_id = ?",
        (quantidade, usuario_id, bichinho_id),
    )
    con.execute(
        "DELETE FROM inventario WHERE usuario_id = ? AND bichinho_id = ? AND quantidade <= 0",
        (usuario_id, bichinho_id),
    )


# ---------- interface pública ----------

def garantir_usuario(usuario_id):
    """Cria o usuário (com moedas iniciais) se ele ainda não existir."""
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
    finally:
        con.close()


def adicionar_bichinho(usuario_id, bichinho_id, quantidade=1):
    """Põe bichinhos no inventário e registra em descobertos."""
    if quantidade <= 0:
        return
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            _adicionar(con, usuario_id, bichinho_id, quantidade)
    finally:
        con.close()


def remover_bichinho(usuario_id, bichinho_id, quantidade=1):
    """Tira bichinhos do inventário. False se não tiver o suficiente."""
    if quantidade <= 0:
        return False
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            if _quantidade(con, usuario_id, bichinho_id) < quantidade:
                return False
            _remover(con, usuario_id, bichinho_id, quantidade)
            return True
    finally:
        con.close()


def inventario(usuario_id):
    """Retorna {bichinho_id: quantidade}."""
    con = conectar()
    try:
        linhas = con.execute(
            "SELECT bichinho_id, quantidade FROM inventario WHERE usuario_id = ?",
            (usuario_id,),
        ).fetchall()
        return {bichinho_id: qtd for bichinho_id, qtd in linhas}
    finally:
        con.close()


def quantidade(usuario_id, bichinho_id):
    """Quantos exemplares do bichinho o usuário tem."""
    con = conectar()
    try:
        return _quantidade(con, usuario_id, bichinho_id)
    finally:
        con.close()


def descobertos(usuario_id):
    """Conjunto de ids de bichinhos que o usuário já teve."""
    con = conectar()
    try:
        linhas = con.execute(
            "SELECT bichinho_id FROM descobertos WHERE usuario_id = ?", (usuario_id,)
        ).fetchall()
        return {linha[0] for linha in linhas}
    finally:
        con.close()


def moedas(usuario_id):
    """Saldo de moedas do usuário."""
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
        return _moedas(con, usuario_id)
    finally:
        con.close()


def alterar_moedas(usuario_id, delta):
    """Soma delta (pode ser negativo) às moedas. False se ficaria negativo."""
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            if _moedas(con, usuario_id) + delta < 0:
                return False
            con.execute("UPDATE usuarios SET moedas = moedas + ? WHERE id = ?", (delta, usuario_id))
            return True
    finally:
        con.close()


def tempo_restante(usuario_id, acao, segundos):
    """Segundos que faltam para poder usar a ação de novo (0 se já pode)."""
    con = conectar()
    try:
        linha = con.execute(
            "SELECT ultimo_uso FROM cooldowns WHERE usuario_id = ? AND acao = ?",
            (usuario_id, acao),
        ).fetchone()
    finally:
        con.close()
    if linha is None:
        return 0
    return max(0.0, linha[0] + segundos - time.time())


def registrar_uso(usuario_id, acao):
    """Marca que o usuário usou a ação agora."""
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            con.execute(
                "INSERT OR REPLACE INTO cooldowns (usuario_id, acao, ultimo_uso) VALUES (?, ?, ?)",
                (usuario_id, acao, time.time()),
            )
    finally:
        con.close()


def trocar(usuario_a, itens_a, moedas_a, usuario_b, itens_b, moedas_b):
    """Troca itens e moedas entre dois usuários, tudo ou nada.

    Retorna False (sem alterar nada) se algum lado não tiver o que oferece.
    """
    if usuario_a == usuario_b:
        return False
    # limpa itens com quantidade zero e recusa valores inválidos
    itens_a = {k: v for k, v in itens_a.items() if v != 0}
    itens_b = {k: v for k, v in itens_b.items() if v != 0}
    if any(v < 0 for v in itens_a.values()) or any(v < 0 for v in itens_b.values()):
        return False
    if moedas_a < 0 or moedas_b < 0:
        return False

    con = conectar()
    try:
        with con:  # uma única transação
            _garantir(con, usuario_a)
            _garantir(con, usuario_b)
            # confere tudo antes de mexer em qualquer coisa
            for dono, itens, valor in ((usuario_a, itens_a, moedas_a), (usuario_b, itens_b, moedas_b)):
                if _moedas(con, dono) < valor:
                    return False
                for bichinho_id, qtd in itens.items():
                    if _quantidade(con, dono, bichinho_id) < qtd:
                        return False
            # aplica a troca
            for bichinho_id, qtd in itens_a.items():
                _remover(con, usuario_a, bichinho_id, qtd)
                _adicionar(con, usuario_b, bichinho_id, qtd)
            for bichinho_id, qtd in itens_b.items():
                _remover(con, usuario_b, bichinho_id, qtd)
                _adicionar(con, usuario_a, bichinho_id, qtd)
            con.execute("UPDATE usuarios SET moedas = moedas - ? + ? WHERE id = ?",
                        (moedas_a, moedas_b, usuario_a))
            con.execute("UPDATE usuarios SET moedas = moedas - ? + ? WHERE id = ?",
                        (moedas_b, moedas_a, usuario_b))
            _contar_troca(con, usuario_a, bool(itens_a or moedas_a), usuario_b, bool(itens_b or moedas_b))
            return True
    finally:
        con.close()


def _contar_troca(con, usuario_a, a_ofereceu, usuario_b, b_ofereceu):
    """Os dois deram algo = troca (conta para os dois); só um deu = presente (conta para quem deu)."""
    if a_ofereceu and b_ofereceu:
        _somar_contador(con, usuario_a, "trocas", 1)
        _somar_contador(con, usuario_b, "trocas", 1)
    elif a_ofereceu:
        _somar_contador(con, usuario_a, "presentes", 1)
    elif b_ofereceu:
        _somar_contador(con, usuario_b, "presentes", 1)


def _somar_pontos(linhas):
    """Recebe [(usuario_id, bichinho_id, quantidade)] e devolve {usuario_id: pontos}."""
    from catalogo import por_id  # importado aqui porque catalogo é outro módulo

    pontos = {}
    for usuario_id, bichinho_id, qtd in linhas:
        bichinho = por_id(bichinho_id)
        if bichinho is None:
            continue
        pontos[usuario_id] = pontos.get(usuario_id, 0) + PONTOS_RARIDADE.get(bichinho["raridade"], 0) * qtd
    return pontos


def ranking(limite=10):
    """Lista [(usuario_id, pontuação)] dos melhores colecionadores."""
    con = conectar()
    try:
        linhas = con.execute("SELECT usuario_id, bichinho_id, quantidade FROM inventario").fetchall()
    finally:
        con.close()

    pontos = _somar_pontos(linhas)
    ordenado = sorted(pontos.items(), key=lambda item: (-item[1], item[0]))
    return ordenado[:limite]


def pontuacao(usuario_id):
    """Pontos de ranking de um usuário só."""
    con = conectar()
    try:
        linhas = con.execute(
            "SELECT usuario_id, bichinho_id, quantidade FROM inventario WHERE usuario_id = ?",
            (usuario_id,),
        ).fetchall()
    finally:
        con.close()
    return _somar_pontos(linhas).get(usuario_id, 0)


# ---------- estatísticas de rolls ----------

def registrar_roll(usuario_id, tipo, bichinho_id):
    """Soma 1 na contagem de rolls do tipo e da raridade do bichinho."""
    from catalogo import por_id

    if tipo not in TIPOS_ROLL:
        raise ValueError(f"Tipo de roll inválido: {tipo}")
    bichinho = por_id(bichinho_id)
    raridade = bichinho["raridade"] if bichinho else "desconhecida"
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            con.execute(
                """INSERT INTO estatisticas (usuario_id, tipo, raridade, quantidade) VALUES (?, ?, ?, 1)
                   ON CONFLICT(usuario_id, tipo, raridade) DO UPDATE SET quantidade = quantidade + 1""",
                (usuario_id, tipo, raridade),
            )
    finally:
        con.close()


def estatisticas(usuario_id):
    """Contagem de rolls: {"total": n, "por_tipo": {...}, "por_raridade": {...}}."""
    con = conectar()
    try:
        linhas = con.execute(
            "SELECT tipo, raridade, quantidade FROM estatisticas WHERE usuario_id = ?", (usuario_id,)
        ).fetchall()
    finally:
        con.close()

    # Começa tudo em zero para o HUD sempre mostrar todas as linhas.
    por_tipo = {tipo: 0 for tipo in TIPOS_ROLL}
    por_raridade = {raridade: 0 for raridade in PONTOS_RARIDADE}
    for tipo, raridade, qtd in linhas:
        por_tipo[tipo] = por_tipo.get(tipo, 0) + qtd
        por_raridade[raridade] = por_raridade.get(raridade, 0) + qtd
    return {"total": sum(por_tipo.values()), "por_tipo": por_tipo, "por_raridade": por_raridade}


def melhor_bichinho(usuario_id):
    """Bichinho mais raro que o usuário já obteve (calculado pelos descobertos), ou None."""
    from catalogo import RARIDADES, por_id

    bichinhos = [por_id(bichinho_id) for bichinho_id in descobertos(usuario_id)]
    bichinhos = [b for b in bichinhos if b is not None]
    if not bichinhos:
        return None
    # Mais raro primeiro; empate decidido pelo nome para o resultado não variar.
    return min(bichinhos, key=lambda b: (-RARIDADES[b["raridade"]]["ordem"], b["nome"]))


# ---------- configurações ----------

def configuracao(usuario_id):
    """Configurações do usuário, ex.: {"aviso_minimo": "raro", "auto_vender": "nada"}."""
    con = conectar()
    try:
        linha = con.execute(
            "SELECT aviso_minimo, auto_vender FROM configuracoes WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
    finally:
        con.close()
    if linha is None:
        return dict(CONFIGURACOES_PADRAO)
    return {"aviso_minimo": linha[0], "auto_vender": linha[1]}


def salvar_configuracao(usuario_id, chave, valor):
    """Muda uma configuração. ValueError se a chave ou o valor forem inválidos."""
    if chave not in VALORES_CONFIGURACAO:
        raise ValueError(f"Configuração inválida: {chave}")
    if valor not in VALORES_CONFIGURACAO[chave]:
        raise ValueError(f"Valor inválido para {chave}: {valor}")
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            con.execute("INSERT OR IGNORE INTO configuracoes (usuario_id) VALUES (?)", (usuario_id,))
            # A chave já foi validada acima, então é seguro colocá-la no SQL.
            con.execute(f"UPDATE configuracoes SET {chave} = ? WHERE usuario_id = ?", (valor, usuario_id))
    finally:
        con.close()


# ---------- contadores (trocas, presentes, missões, sequências...) ----------

def _somar_contador(con, usuario_id, chave, delta):
    con.execute(
        """INSERT INTO contadores (usuario_id, chave, valor) VALUES (?, ?, ?)
           ON CONFLICT(usuario_id, chave) DO UPDATE SET valor = valor + ?""",
        (usuario_id, chave, delta, delta),
    )
    return con.execute("SELECT valor FROM contadores WHERE usuario_id = ? AND chave = ?",
                       (usuario_id, chave)).fetchone()[0]


def somar_contador(usuario_id, chave, delta=1):
    """Soma delta no contador e devolve o novo valor."""
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            return _somar_contador(con, usuario_id, chave, delta)
    finally:
        con.close()


def definir_contador(usuario_id, chave, valor):
    """Grava um valor fixo no contador (ex.: zerar uma sequência)."""
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            con.execute("INSERT OR REPLACE INTO contadores (usuario_id, chave, valor) VALUES (?, ?, ?)",
                        (usuario_id, chave, valor))
    finally:
        con.close()


def contadores(usuario_id):
    """Todos os contadores do usuário: {chave: valor}."""
    con = conectar()
    try:
        linhas = con.execute("SELECT chave, valor FROM contadores WHERE usuario_id = ?", (usuario_id,)).fetchall()
        return dict(linhas)
    finally:
        con.close()


def contador(usuario_id, chave):
    """Valor de um contador (0 se nunca foi usado)."""
    return contadores(usuario_id).get(chave, 0)


def rolls_por_tipo_e_raridade(usuario_id):
    """{(tipo, raridade): quantidade}, ex.: {("autoroll", "mitico"): 1}."""
    con = conectar()
    try:
        linhas = con.execute(
            "SELECT tipo, raridade, quantidade FROM estatisticas WHERE usuario_id = ?", (usuario_id,)
        ).fetchall()
    finally:
        con.close()
    return {(tipo, raridade): qtd for tipo, raridade, qtd in linhas}


# ---------- títulos ----------

def desbloquear_titulo(usuario_id, titulo_id):
    """Registra o título. Devolve True se ele é novo (False se já tinha)."""
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            cursor = con.execute(
                "INSERT OR IGNORE INTO titulos (usuario_id, titulo_id, desbloqueado_em) VALUES (?, ?, ?)",
                (usuario_id, titulo_id, time.time()),
            )
            return cursor.rowcount == 1
    finally:
        con.close()


def titulos_desbloqueados(usuario_id):
    """Conjunto de ids dos títulos que o usuário já tem."""
    con = conectar()
    try:
        linhas = con.execute("SELECT titulo_id FROM titulos WHERE usuario_id = ?", (usuario_id,)).fetchall()
        return {linha[0] for linha in linhas}
    finally:
        con.close()


def _ler_config_titulo(usuario_id):
    con = conectar()
    try:
        return con.execute(
            "SELECT titulo_equipado, titulo_no_apelido FROM configuracoes WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
    finally:
        con.close()


def _gravar_config_titulo(usuario_id, coluna, valor):
    # coluna vem só das duas funções abaixo (nunca do usuário), então é seguro no SQL.
    con = conectar()
    try:
        with con:
            _garantir(con, usuario_id)
            con.execute("INSERT OR IGNORE INTO configuracoes (usuario_id) VALUES (?)", (usuario_id,))
            con.execute(f"UPDATE configuracoes SET {coluna} = ? WHERE usuario_id = ?", (valor, usuario_id))
    finally:
        con.close()


def titulo_equipado(usuario_id):
    """Id do título equipado, ou None."""
    linha = _ler_config_titulo(usuario_id)
    return linha[0] if linha else None


def equipar_titulo(usuario_id, titulo_id):
    """Equipa um título (None desequipa). Quem chama confere se ele está desbloqueado."""
    _gravar_config_titulo(usuario_id, "titulo_equipado", titulo_id)


def titulo_no_apelido(usuario_id):
    """True se o título deve aparecer no apelido do servidor (padrão: sim)."""
    linha = _ler_config_titulo(usuario_id)
    return bool(linha[1]) if linha else True


def definir_titulo_no_apelido(usuario_id, ligado):
    _gravar_config_titulo(usuario_id, "titulo_no_apelido", 1 if ligado else 0)


# ---------- cargos de título e apelidos (por servidor) ----------

def cargo_do_titulo(guild_id, titulo_id):
    """Id do cargo criado para o título neste servidor, ou None."""
    con = conectar()
    try:
        linha = con.execute("SELECT cargo_id FROM cargos_titulo WHERE guild_id = ? AND titulo_id = ?",
                            (guild_id, titulo_id)).fetchone()
        return linha[0] if linha else None
    finally:
        con.close()


def salvar_cargo_do_titulo(guild_id, titulo_id, cargo_id):
    con = conectar()
    try:
        with con:
            con.execute("INSERT OR REPLACE INTO cargos_titulo (guild_id, titulo_id, cargo_id) VALUES (?, ?, ?)",
                        (guild_id, titulo_id, cargo_id))
    finally:
        con.close()


def esquecer_cargo_do_titulo(guild_id, titulo_id):
    con = conectar()
    try:
        with con:
            con.execute("DELETE FROM cargos_titulo WHERE guild_id = ? AND titulo_id = ?", (guild_id, titulo_id))
    finally:
        con.close()


def cargos_de_titulo(guild_id):
    """{titulo_id: cargo_id} de todos os cargos de título deste servidor."""
    con = conectar()
    try:
        linhas = con.execute("SELECT titulo_id, cargo_id FROM cargos_titulo WHERE guild_id = ?",
                             (guild_id,)).fetchall()
        return dict(linhas)
    finally:
        con.close()


def apelido_original(guild_id, usuario_id):
    """(True, apelido) se o apelido de antes do título foi guardado; (False, None) se não.

    O apelido guardado pode ser None: a pessoa não tinha apelido.
    """
    con = conectar()
    try:
        linha = con.execute("SELECT apelido FROM apelidos_originais WHERE guild_id = ? AND usuario_id = ?",
                            (guild_id, usuario_id)).fetchone()
    finally:
        con.close()
    return (True, linha[0]) if linha else (False, None)


def guardar_apelido_original(guild_id, usuario_id, apelido):
    con = conectar()
    try:
        with con:
            con.execute("INSERT OR REPLACE INTO apelidos_originais (guild_id, usuario_id, apelido) VALUES (?, ?, ?)",
                        (guild_id, usuario_id, apelido))
    finally:
        con.close()


def esquecer_apelido_original(guild_id, usuario_id):
    con = conectar()
    try:
        with con:
            con.execute("DELETE FROM apelidos_originais WHERE guild_id = ? AND usuario_id = ?",
                        (guild_id, usuario_id))
    finally:
        con.close()