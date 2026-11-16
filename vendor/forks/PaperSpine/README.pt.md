<p align="right"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-mark.svg" width="24" alt="PaperSpine"></a></p>

<p align="center"><a href="https://wubing2023.github.io/PaperSpine/v5/"><img src="website/assets/brand/paperspine-hero.webp" alt="PaperSpine5 · do zero a um artigo completo, com texto e figuras"></a></p>

# PaperSpine5

> Release note: alpha.3 provides full Windows, Linux, and macOS suites only. The historical 0.70 MB Skill-only ZIP has no Web core or runtime and is not a current install option.

[中文](README.md) · [English](README.en.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Português](README.pt.md)

[Página do produto](https://wubing2023.github.io/PaperSpine/v5/) · [GitHub Release](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.4.0-alpha.3)

**PaperSpine5: do zero a um artigo completo, com texto e figuras.**

O PaperSpine5 é um AI Skill que cobre todo o percurso de um artigo. Você traz uma direção de pesquisa, materiais que já tem ou dados experimentais; ele pesquisa a literatura, organiza a argumentação, monta o roteiro, escreve o texto completo, gera as figuras científicas, confere as citações, conduz a revisão e as correções e cuida da diagramação, entregando no fim fontes editáveis em Word / LaTeX e um PDF.

Do corpo do texto às figuras de dados, esquemas de mecanismo e diagramas de método, tudo é produzido dentro da mesma tarefa. Inicia-se com `paper-spine`, escolhe-se o caminho na página web, pré-visualiza-se texto e figuras, deixam-se pedidos de alteração e baixam-se os resultados. Os materiais de pesquisa ficam por padrão na sua máquina, e cada afirmação, citação e figura se apoia em fontes e evidências reais.

## Downloads

- Suíte para Windows x64: cerca de 26,4 MB.
- Suíte para Linux glibc x86_64: cerca de 56,2 MB.
- Suíte para macOS Apple Silicon: cerca de 40,5 MB.
- Suíte para macOS Intel x86_64: cerca de 40,5 MB.

Todos os downloads estão na lista pública de lançamentos e são verificados por SHA-256. A versão atual é o pré-lançamento `v0.4.0-alpha.3`.

## Instalação e migração de versões anteriores

Windows x64:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex -CleanLegacy
```

macOS / Linux:

```sh
sh ./install.sh --target codex --clean-legacy
```

O `-CleanLegacy` apenas arquiva as pastas conhecidas de descoberta de Skills V3/V4. Não apaga dados de tarefas, configurações do host nem arquivos desconhecidos. Os dois instaladores verificam a contagem de bytes, o SHA-256, a integridade interna da suíte e o estado na primeira execução.

## Verificar e aplicar atualizações

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File .\install.ps1 -CheckOnly
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Target codex
```

```sh
# macOS / Linux
sh ./install.sh --check-only
sh ./install.sh --target codex
```

Executar o instalador novamente verifica a versão. Se houver uma nova, ele aplica uma atualização reversível e verifica a inicialização, preservando os dados. Uma instalação completa e atual não é baixada nem sobrescrita novamente. Cada chamada da Skill verifica atualizações e atualiza a suíte e o atualizador quando necessário; uma desativação explícita é respeitada.

## Limites

- As suítes autocontidas foram verificadas em Windows x64, Linux glibc x86_64, macOS arm64 e macOS x86_64. Linux arm64 e musl/Alpine não são declarados como suportados.
- Os pacotes de macOS não são assinados nem notarizados; a primeira execução pode exigir autorização explícita do usuário.
- É um pré-lançamento alpha, sem assinatura criptográfica independente.
- Publicar o produto não autoriza submissão de manuscrito, envio de material privado, pagamento ou contato externo.
- O canal de apoio é voluntário, não libera funcionalidades e não lê estado de pagamento.

## Estrutura do repositório público

- `dist/codex/skills/paper-spine`, `dist/claude/skills/paper-spine`, `dist/openclaw/skills/paper-spine`: projeções por host.
- `dist/claude/commands/paperspine.md`: entrada de comando do Claude.
- `install.ps1`, `install.sh`: limites de instalação.
- Métodos e ferramentas principais: `writing_rationale_matrix`, `citation_support_bank`, `translation_package`, `artifact_check.py`, `reference_inventory.py`, `citation_bank_check.py`, `latex_guard.py`, `word_guard.py`.

## Desenvolvimento

`src/` contém o código-fonte do Skill e `dist/` reúne as projeções públicas por host. O repositório público mantém código-fonte e testes, e não tarefas locais, dados clínicos, caches ou registros de execução de desenvolvimento.

MIT License.
