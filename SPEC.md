# Especificação do bot de bichinhos (contrato entre módulos)

Bot de Discord (discord.py 2.7, Python 3.12, venv em `venv312/`) de colecionar bichinhos
elementais por sorte (RNG). O usuário manda a foto de um objeto real; o YOLO detecta o
objeto; o objeto define o **elemento**; o bot sorteia um bichinho daquele elemento.
Projeto de curso: código em **português** (nomes de variáveis, funções, comentários,
mensagens), simples e legível para um estudante. Sem dependências desnecessárias.

## Elementos
Ids fixos (usar exatamente estes): `natureza`, `fogo`, `agua`, `eletrico`, `mistico`, `fera`.
Nomes de exibição: Natureza 🌿, Fogo 🔥, Água 💧, Elétrico ⚡, Místico 🔮, Fera 🐾.

## Raridades
Ids e chances base (somam 100):
| id | exibição | chance | qtd. de bichinhos |
|---|---|---|---|
| `comum` | Comum | 60 | 50 |
| `incomum` | Incomum | 25 | 40 |
| `raro` | Raro | 10 | 30 |
| `epico` | Épico | 4 | 30 |
| `lendario` | Lendário | 0.9 | 30 |
| `mitico` | Mítico | 0.1 | 15 |

## Arquivo `dados/bichinhos.json`
```json
{
  "bichinhos": [
    {
      "id": "sapo_musgoso",
      "nome": "Sapo Musgoso",
      "elemento": "natureza",
      "raridade": "comum",
      "descricao": "Uma frase curta e divertida.",
      "aparencia": {
        "corpo": "blob",
        "olhos": "redondos",
        "boca": "sorriso",
        "acessorio": "folhas",
        "padrao": "manchas",
        "cor_principal": "#5fbf4a",
        "cor_secundaria": "#2e7d32"
      }
    }
  ]
}
```
Valores permitidos em `aparencia` (o gerador de sprites suporta TODOS e SOMENTE estes):
- `corpo`: `gota`, `blob`, `chama`, `cristal`, `nuvem`, `broto`, `estrela`, `fantasma`
- `olhos`: `redondos`, `sonolentos`, `bravos`, `brilhantes`, `ciclope`, `felizes`
- `boca`: `sorriso`, `aberta`, `dentes`, `neutra`, `lingua`
- `acessorio`: `nenhum`, `chifres`, `antenas`, `coroa`, `folhas`, `orelhas`, `asas`, `aureola`, `raios`
- `padrao`: `liso`, `manchas`, `listras`, `gradiente`, `estrelado`
- `cor_principal` / `cor_secundaria`: hex `#rrggbb`

Nenhuma combinação `aparencia` + cores pode se repetir entre dois bichinhos.

## Estilo visual dos sprites
Espíritos elementais pequenos, fofos e flutuantes: corpo arredondado, olhos grandes e
expressivos, contorno escuro, sombra no chão, efeito do elemento em volta. Estilo
**original** (não copiar personagens ou artes de nenhum jogo existente). Pixel art em grade
de 32x32, exportada ampliada (8x, nearest neighbor) para PNG 256x256 com fundo transparente.
Efeitos por raridade (decididos pelo gerador, não pelo JSON):
comum = simples; incomum = contorno colorido; raro = brilho nos olhos e destaque;
épico = aura; lendário = aura dourada + partículas; mítico = GIF animado (flutuando, com
partículas e brilho arco-íris).

## Módulos e interfaces (cada um em seu arquivo, na raiz do projeto)

### `catalogo.py`
- `carregar() -> list[dict]` (lê `dados/bichinhos.json` uma vez, guarda em cache)
- `por_id(id: str) -> dict | None`
- `filtrar(raridade: str | None = None, elemento: str | None = None) -> list[dict]`
- `buscar(nome: str) -> dict | None` (sem acento, sem maiúsculas, aceita nome parcial e erro de digitação com `difflib`)
- Constantes `ELEMENTOS` (id -> {"nome", "emoji"}) e `RARIDADES` (id -> {"nome", "chance", "cor" (int RGB p/ embed), "ordem"})

### `sprites.py`
- `caminho_sprite(bichinho: dict) -> str` gera (se ainda não existir) e retorna o caminho do
  arquivo em `sprites/` (`<id>.png`, ou `<id>.gif` para míticos). Determinístico: o mesmo
  bichinho sempre gera a mesma imagem.
- Rodar `python sprites.py` gera todos e monta `sprites/_galeria.png` (todos os sprites em grade, para conferir).
- Usa apenas Pillow.

### `visao.py`
- `ELEMENTO_POR_CLASSE: dict[str, str]` mapeia nomes de classe do COCO (YOLO pré-treinado) para elementos:
  - natureza: potted plant, broccoli, carrot, apple, orange, banana
  - fogo: pizza, hot dog, donut, cake, sandwich, oven, microwave, toaster
  - agua: cup, bottle, wine glass, bowl, sink, umbrella
  - eletrico: cell phone, laptop, tv, remote, keyboard, mouse, hair drier, clock
  - mistico: book, vase, teddy bear, scissors, kite
  - fera: cat, dog, bird, horse, sheep, cow, elephant, bear, zebra, giraffe
  - `person` e demais classes são ignoradas.
- `@dataclass Deteccao: classe: str, elemento: str, confianca: float`
- `detectar(caminho_imagem: str) -> list[Deteccao]` só classes mapeadas, ordenado por confiança desc. Modelo `yolo11n.pt` (ultralytics), carregado uma única vez, sob demanda.
- `melhor_deteccao(caminho_imagem: str) -> Deteccao | None`
- `desenhar_deteccoes(caminho_imagem: str, deteccoes: list[Deteccao]) -> str` salva uma cópia com as caixas e retorna o caminho.

### `banco.py` (SQLite, arquivo `dados/jogo.db`, módulo `sqlite3`)
Tabelas: `usuarios(id INTEGER PK, moedas, criado_em)`, `inventario(usuario_id, bichinho_id, quantidade, PK(usuario_id, bichinho_id))`,
`descobertos(usuario_id, bichinho_id, descoberto_em)` (para o index: nunca é apagado),
`cooldowns(usuario_id, acao, ultimo_uso)`.
- `garantir_usuario(usuario_id: int)`
- `adicionar_bichinho(usuario_id, bichinho_id, quantidade=1)` (também registra em descobertos)
- `remover_bichinho(usuario_id, bichinho_id, quantidade=1) -> bool` (False se não tiver o suficiente)
- `inventario(usuario_id) -> dict[str, int]`
- `quantidade(usuario_id, bichinho_id) -> int`
- `descobertos(usuario_id) -> set[str]`
- `moedas(usuario_id) -> int`, `alterar_moedas(usuario_id, delta) -> bool` (False se ficaria negativo)
- `tempo_restante(usuario_id, acao: str, segundos: int) -> float` (0 se pode usar) e `registrar_uso(usuario_id, acao)`
- `trocar(usuario_a, itens_a: dict[str,int], moedas_a: int, usuario_b, itens_b: dict[str,int], moedas_b: int) -> bool`
  Em UMA transação: confere que cada um tem tudo o que oferece; se não, não muda nada e retorna False.
- `ranking(limite=10) -> list[tuple[int, int]]` (usuario_id, pontuação), pontuação = soma de pontos por raridade dos bichinhos possuídos (comum 1, incomum 3, raro 10, épico 30, lendário 100, mítico 500).
- Pontos por raridade em constante `PONTOS_RARIDADE`; moedas de venda em `VALOR_VENDA`.
- `pontuacao(usuario_id) -> int` (pontos de ranking de um usuário).
- Tabela `estatisticas(usuario_id, tipo, raridade, quantidade)`; tipos em `TIPOS_ROLL` = `roll`, `autoroll`,
  `comprar`, `capturar` (o roll grátis da missão conta como `roll`).
  `registrar_roll(usuario_id, tipo, bichinho_id)`, `estatisticas(usuario_id) -> {"total", "por_tipo", "por_raridade"}`,
  `melhor_bichinho(usuario_id) -> dict | None` (o mais raro dos descobertos).
- Tabela `configuracoes(usuario_id PK, aviso_minimo DEFAULT 'raro', auto_vender DEFAULT 'nada')`;
  `configuracao(usuario_id) -> dict`, `salvar_configuracao(usuario_id, chave, valor)` (ValueError se chave/valor inválidos).
  `auto_vender`: `nada`, `comum` (vende comuns) ou `incomum` (vende comuns e incomuns).
- Todo roll passa por `sorteio.entregar(usuario_id, bichinho, tipo)`, que põe no inventário e chama `registrar_roll`.

### Fase 2 (depois das anteriores): `sorteio.py`, `trade.py`, `embeds.py`, `chatbot.py`, `main.py`
- `!capturar` + foto (e `/capturar` com anexo): YOLO -> elemento -> sorteio daquele elemento. Confiança > 0.9 aumenta as chances de épico/lendário/mítico. Espera `ESPERA_CAPTURAR` = 5 s.
- `!roll`: sorteio de qualquer elemento, sem bônus, espera `ESPERA_ROLL` = 5 s (bloqueado com autoroll ligado).
- `!inv [@usuario]` paginado, `!ver <bichinho>` (ficha com sprite), `!index`, `!rank`, `!dar @u <bichinho>`, `!vender <bichinho>`, `!moedas`, `!missao` (missão diária: foto de um elemento sorteado do dia → roll grátis), `!trade @u` com botões (adicionar item, adicionar moedas, confirmar, cancelar; qualquer mudança desconfirma os dois), `!ajuda`.
- Chatbot: nome do bot **SpriteRNG**. Responde como chatbot quando a mensagem contém, como palavra, `sprite`, `sprites`, `spriterng` ou `rng` (APELIDOS = ["sprite", "sprites", "rng"]), inclusive esticados (`spriteeeee`, `rrrnggg`, `spriterrrnnnggg`) e sem diferenciar maiúsculas/acentos; quando marcam o bot (@); e quando dão reply numa mensagem dele. Base em `chatbot.py` (já tem a detecção com letras repetidas; trocar `NOME_BOT = "SpriteRNG"` e `APELIDOS = ["sprite", "sprites", "rng"]` e adaptar as respostas para o tema dos bichinhos).
- Token em `.env` (`DISCORD_TOKEN`).

## Fase 3: autoroll, HUD e status
- `autoroll.py`: `!autoroll` / `/autoroll` liga e desliga. Ligado, faz um roll a cada `INTERVALO_AUTOROLL` = 25 s
  (mesmas chances do `!roll`) e salva no inventário. Uma `asyncio.Task` por usuário, só em memória: ao reiniciar o
  bot, todos ficam desligados. Enquanto ligado, `!roll` fica bloqueado (`!capturar` não). No canal onde foi ligado,
  só avisa (mencionando o usuário) quando a raridade for >= `aviso_minimo`; o resto é silencioso. Se configurado,
  vende na hora (`auto_vender`) usando `VALOR_VENDA` (ainda conta como descoberto e nas estatísticas). Desliga
  sozinho após `AUTOROLL_INATIVIDADE` = 600 s sem mensagens do usuário no servidor (registradas no `on_message`),
  avisando no canal. Funções: `ligar`, `desligar`, `alternar`, `esta_ligado`, `registrar_atividade`,
  `segundos_para_proximo`, `fazer_roll`.
- `hud.py`: `/hud` responde com o HUD efêmero; `!hud` (prefixo não pode ser efêmero) manda o botão
  "Abrir meu HUD", que abre o HUD efêmero de quem clicou. O HUD mostra rolls por tipo e por raridade, melhor
  bichinho, moedas, bichinhos no inventário, descobertos/195, autoroll (e tempo até o próximo) e esperas de
  `!roll`/`!capturar`. Controles: botão do autoroll (liga no canal atual), menu "Avisar a partir de", menu de
  auto-venda e botão "Atualizar". Só o dono mexe; expira em 5 min.
- `!status [membro]` / `/status [membro]`: status público (rolls, por raridade, melhor bichinho, descobertos,
  pontos do ranking, autoroll ligado ou não, título equipado), sem configurações.
  `!status` usa `membros.MembroFlexivel`: menção, id ou nome/apelido/display_name/global_name sem diferenciar
  maiúsculas e acentos (igual > começa com > contém > difflib); empate lista até 5 candidatos (`MembroAmbiguo`).
  No `/status` o parâmetro continua sendo o seletor de usuário do Discord.
- `intents.members = True` (intent privilegiado: ligar **Server Members Intent** no Developer Portal). Se estiver
  desligado no portal, o bot reinicia sozinho sem ele (`SPRITERNG_SEM_MEMBROS=1`) e só acha quem está no cache.

## Fase 4: títulos
- `titulos.py`: lista `TITULOS` (id, nome, emoji, cor hex, descricao, regra, secreto), em ordem de dificuldade.
  Regras são tuplas lidas por `progresso(titulo, dados) -> (atual, meta)`: `rolls`, `tipo`, `contador`, `moedas`,
  `descobertos`, `raridade`, `tipo_raridade`, `elemento`, `todos_raridade`, `colecao`, `copias_raridade`,
  `colecao_pura`. `verificar_titulos(uid) -> list[novos]` e `verificar_e_anunciar(canal, uid)` (embed
  "🏅 Novo título desbloqueado!", ou "🌟 TÍTULO SECRETO DESBLOQUEADO!") são chamados depois de todo roll, captura,
  missão, venda, presente, troca e autoroll. Secretos bloqueados aparecem como "❓ ???" em qualquer lista.
- `banco.py`: tabelas `titulos(usuario_id, titulo_id, desbloqueado_em)`, `contadores(usuario_id, chave, valor)`
  (trocas, presentes, missoes, sequencia_epica, maior_sequencia_epica, mitico_com_bonus, max_miticos_dia,
  miticos_vendidos...), `cargos_titulo(guild_id, titulo_id, cargo_id)`, `apelidos_originais(guild_id, usuario_id,
  apelido)`; colunas `titulo_equipado` e `titulo_no_apelido` (padrão 1) em `configuracoes`, criadas por migração
  (`PRAGMA table_info` + `ALTER TABLE`). `banco.trocar` conta troca (os dois dão algo) ou presente (só um dá).
- `cargos.py`: `equipar(membro, titulo|None) -> list[avisos]` cria/reaproveita/recria o cargo "<emoji> <Nome>"
  (cor do título, sem hoist, não mencionável, ícone se o servidor tiver `ROLE_ICONS`), sobe para logo abaixo do
  cargo do bot, tira os outros cargos de título e apaga cargos vazios (só com a lista de membros completa). Com
  `titulo_no_apelido`, o apelido vira "Nome 「Título」" (máx. 32: corta o nome; se nem o título couber, só o emoji)
  e o apelido original é restaurado ao tirar o título ou desligar a opção. Falta de permissão (Gerenciar Cargos /
  Gerenciar Apelidos), dono do servidor e cargo acima do bot viram avisos amigáveis, nunca erro.
- Comandos: `!titulos` (lista paginada), `!titulo <nome>` (parcial/sem acento; autocomplete no `/titulo` com os
  desbloqueados), `!titulo` ou `!titulo remover` (tira).
- HUD com abas "📊 Status" (menu de título rápido + botão "Título no apelido") e "🏅 Títulos" (5 por página, botão
  Equipar / Equipado ✓ / 🔒 por título, Remover, ◀ ▶). Ações que mexem em cargos usam `defer()`.
