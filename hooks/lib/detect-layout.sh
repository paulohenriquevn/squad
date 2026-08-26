#!/bin/bash
# Resolução de layout compartilhada pelos hooks.
#
# Uso, a partir de qualquer hook:
#   source "$(dirname "$0")/lib/detect-layout.sh"
#
# Depois de sourced, DOIS caminhos ficam definidos — e a distinção entre eles é
# o ponto deste arquivo:
#
#   KIT_DIR  o CÓDIGO do kit (skills/, rules/, hooks/). Read-only para o
#            consumidor. No modo plugin nativo vive FORA do projeto.
#   ECO      os DADOS do ciclo (knowledge-base/, .active_plan, .attestations).
#            Sempre dentro do projeto, sempre gravável.
#
# $PROJECT_DIR também é definido (default: $CLAUDE_PROJECT_DIR ou pwd).
# Sai 0 sem definir nada quando não há kit — um projeto que não o usa não deve
# ouvir nada.
#
# POR QUE DOIS CAMINHOS E NÃO UM
# ------------------------------
# Até 2026-08-26 havia só `ECO`, e ele respondia pelas duas coisas. Isso só
# funciona enquanto o kit VIVE dentro do projeto, que é o que
# `scripts/install.sh` faz ao copiá-lo para `<projeto>/.claude/`. O custo dessa
# fusão está registrado em `scripts/check_install_drift.py`: vinte e duas
# correções do kit passaram semanas dentro do `.claude/` gitignorado de um
# consumidor e em nenhum outro lugar. Enquanto o código do kit for um diretório
# gravável dentro do projeto, o agente do consumidor o edita — e a divergência
# não é um bug a corrigir, é o comportamento esperado do desenho.
#
# Separá-los é o que permite o modo nativo, em que o código fica sob
# `$CLAUDE_PLUGIN_ROOT` e o projeto guarda apenas o que é dele.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || exit 0

# Um diretório é o kit quando carrega as três árvores que o definem.
_squad_has_kit() {
  [ -d "$1/skills" ] && [ -d "$1/rules" ] && [ -d "$1/hooks" ]
}

KIT_DIR=""
ECO=""

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  # --- 1. PLUGIN NATIVO -----------------------------------------------------
  # O Claude Code exporta CLAUDE_PLUGIN_ROOT para os hooks declarados em
  # hooks/hooks.json. O código do kit está fora do projeto.
  if _squad_has_kit "$CLAUDE_PLUGIN_ROOT"; then
    KIT_DIR="$CLAUDE_PLUGIN_ROOT"
    # Os dados continuam no projeto. `.claude/` quando existe, para coincidir
    # com o layout que as instalações por cópia já usam; a raiz caso contrário.
    if [ -d ".claude" ]; then ECO=".claude"; else ECO="."; fi
  else
    # CLAUDE_PLUGIN_ROOT definido e sem o kit é instalação corrompida — não é o
    # mesmo que "ninguém instalou". Antes disto o script saía 0 sem uma linha, e
    # todo gate ficava desligado parecendo aprovado. Medido em 2026-08-26:
    # stop-validation.sh e sessionstart-context.sh saíam 0, mudos.
    echo "[squad] CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT} não contém skills/, rules/ e hooks/." >&2
    echo "[squad] Instalação incompleta — os gates NÃO estão ativos nesta sessão." >&2
    exit 0
  fi
elif _squad_has_kit ".claude"; then
  # --- 2. INSTALAÇÃO POR CÓPIA ---------------------------------------------
  # O layout que scripts/install.sh escreve. Código e dados coincidem, como
  # sempre coincidiram: nada muda para quem já instalou assim.
  KIT_DIR=".claude"
  ECO=".claude"
elif _squad_has_kit "."; then
  # --- 3. STANDALONE --------------------------------------------------------
  # O próprio repositório do kit aberto no Claude Code.
  KIT_DIR="."
  ECO="."
else
  exit 0
fi

# Diagnóstico sob demanda. `settings.json` já expõe CLAUDE_DEBUG_HOOKS, e a
# pergunta "de onde este hook acha que o kit veio?" não tinha resposta.
if [ "${CLAUDE_DEBUG_HOOKS:-0}" = "1" ]; then
  echo "[squad] KIT_DIR=${KIT_DIR} ECO=${ECO} PROJECT_DIR=${PROJECT_DIR}" >&2
fi
