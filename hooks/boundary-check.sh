#!/bin/bash
# PreToolUse hook para Edit/Write: fronteiras de escrita (agnóstico).
#
# Fronteiras defendidas:
#   1. knowledge-base/references/ (projetos parecidos — inspiração) e
#      knowledge-base/tools/ (ferramentas das quais dependemos) são material de
#      estudo read-only. Achados vão para knowledge-base/discoveries/blueprints/.
#   2. O KIT INSTALADO é read-only quando é dependência do projeto.
#
# Fronteiras arquiteturais do projeto (p.ex. DIP entre domínio e adaptadores)
# são específicas e pertencem a rules/architecture.md, cobradas em code review.
#
# Exit 0 = permite, Exit 2 = bloqueia.

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.filePath // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# --- 1. knowledge-base/{references,tools}/ são read-only ---------------------
# Verificada ANTES de resolver o layout: `detect-layout.sh` encerra com exit 0
# quando não encontra o kit, e esta fronteira não depende de haver kit algum.
# Casa os dois layouts (knowledge-base/ e .claude/knowledge-base/).
if echo "$FILE_PATH" | grep -qE '(^|/)(\.claude/)?knowledge-base/(references|tools)/'; then
  echo '{"decision":"block","reason":"BOUNDARY VIOLATION: knowledge-base/references/ (similar projects — inspiration) and knowledge-base/tools/ (tools we depend on) are read-only. Never edit/create files there. Capture findings in knowledge-base/discoveries/blueprints/."}' >&2
  exit 2
fi

# --- 2. o kit instalado é read-only -----------------------------------------
# POR QUE ESTA FRONTEIRA EXISTE
# O kit instalado por cópia vive em `<projeto>/.claude/`, com Edit/Write/Bash(*)
# liberados, e até 2026-08-26 nenhum hook cobria esse caminho. O resultado está
# registrado em `scripts/check_install_drift.py`: vinte e duas correções do kit
# passaram semanas dentro do `.claude/` gitignorado de UM consumidor e em nenhum
# outro lugar. Uma correção escrita aqui protege exatamente uma máquina e some
# no próximo `install.sh --force`. O destino dela é o repositório do kit.
source "$(dirname "$0")/lib/detect-layout.sh"

# STANDALONE NUNCA É PROTEGIDO. Aí `KIT_DIR` é o próprio repositório do kit
# aberto para desenvolvimento — bloquear seria impedir o trabalho que este hook
# existe para preservar. A fronteira vale quando o kit é DEPENDÊNCIA.
[ "$KIT_DIR" = "." ] && exit 0

case "$KIT_DIR" in
  /*) KIT_ABS="$KIT_DIR" ;;
   *) KIT_ABS="$PROJECT_DIR/$KIT_DIR" ;;
esac
case "$FILE_PATH" in
  /*) TARGET_ABS="$FILE_PATH" ;;
   *) TARGET_ABS="$PROJECT_DIR/$FILE_PATH" ;;
esac

# Fora da árvore do kit não há nada a decidir.
case "$TARGET_ABS" in
  "$KIT_ABS"/*) REL="${TARGET_ABS#"$KIT_ABS"/}" ;;
  *) exit 0 ;;
esac

# O que é do PROJETO dentro da árvore do kit, e por quê:
#
#   rules/*.txt          configuração — linguagens habilitadas, alvo vivo,
#                        allowlists. `install.sh` já a preserva entre instalações.
#   agents/**            os especialistas que o projeto escreveu sobre os
#                        próprios repositórios. Não existem em lugar nenhum além
#                        dali.
#   knowledge-base/**    a saída do ciclo: planos, reviews, auditorias, ADRs.
#   settings.json        a fiação deste projeto.
#   .kit-manifest.txt    reescrito pelo instalador a cada instalação.
#
# Tudo o mais sob a árvore é CONTRATO do kit.
case "$REL" in
  rules/*.txt|agents/*|knowledge-base/*|settings.json|.kit-manifest.txt|.install-backups/*)
    exit 0
    ;;
esac

# Uma skill que o PROJETO escreveu continua sendo dele. É para isso que
# `.kit-manifest.txt` existe: sem consultá-lo, a única forma de separar as
# skills do kit das do projeto seria adivinhar por nome — e foi medido num
# adotante com 10 skills próprias ao lado das do kit.
case "$REL" in
  skills/*)
    SKILL_DIR="skills/$(echo "$REL" | cut -d/ -f2)"
    MANIFEST="$KIT_ABS/.kit-manifest.txt"
    if [ -f "$MANIFEST" ] && ! grep -qxF "$SKILL_DIR" "$MANIFEST"; then
      exit 0  # não veio do kit — é do projeto
    fi
    ;;
esac

REASON="BOUNDARY VIOLATION: ${REL} belongs to the installed Squad kit, which is read-only here. A fix written inside an installed kit protects exactly one machine and is erased by the next install. Send it to the kit's own repository instead. Project-owned paths under the same tree stay writable: rules/*.txt (config), agents/ (your domain specialists), knowledge-base/ (cycle output) and settings.json."
printf '{"decision":"block","reason":%s}\n' "$(printf '%s' "$REASON" | jq -Rs .)" >&2
exit 2
