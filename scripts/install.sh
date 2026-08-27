#!/usr/bin/env bash
# Installs the Squad maintenance ecosystem into a target project as a plugin install
# (target/.claude/ layout). Hooks auto-detect the layout, so target/.claude/* is
# picked up identically to the standalone repo.
#
# Usage:
#   bash scripts/install.sh <target-project-dir> [--force]
#
# What it does:
#   1. Validates target is a directory.
#   2. Refuses to overwrite an existing target/.claude/ unless --force.
#   3. Copies skills/, rules/, hooks/, commands/, scripts/, plugin.json,
#      HOW-TO-USE.md into target/.claude/.
#   4. Writes settings.plugin.json as target/.claude/settings.json.
#   5. Creates empty scaffold under target/.claude/knowledge-base/
#      (plans, implementations, reviews, audits, discoveries/{plans,opportunities,snapshots},
#      adrs, grills, dogfood, judge-codex, backlog, maintenance-runs, tools).
#      agents/ receives ONLY README.md (the routing mechanism). Specialists are
#      derived per project — the kit ships none. agents/ is never deleted.
#   6. Skips the source repo's history: caches, artifact dirs, audit trails,
#      CHANGELOG.md, .git/, .compaction-snapshots/, .attestations/.
#   7. Prints next steps.
#
# What it does NOT do:
#   - Modify the consumer's CLAUDE.md (write your own pointer to .claude/).
#   - Add anything to .gitignore (consumer decides whether to track .claude/).
#   - Install dependencies (python3, jq, ast-grep, ralph-loop plugin) — see HOW-TO-USE.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- args ---
if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/install.sh <target-project-dir> [--force|--merge]" >&2
  exit 2
fi

TARGET="$1"
FORCE=0
MERGE=0
for arg in "${@:2}"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --merge) MERGE=1 ;;
    "") ;;
    *) echo "ERROR: unknown flag ${arg}. Expected --force or --merge." >&2; exit 2 ;;
  esac
done

if [ ! -d "$TARGET" ]; then
  echo "ERROR: target is not a directory: $TARGET" >&2
  exit 2
fi

TARGET="$(cd "$TARGET" && pwd)"
ECO="$TARGET/.claude"

if [ "$TARGET" = "$SRC_DIR" ]; then
  echo "ERROR: target is the source repo itself. install.sh is for installing the ecosystem INTO another project." >&2
  exit 2
fi

if [ -d "$ECO" ] && [ "$FORCE" -ne 1 ] && [ "$MERGE" -ne 1 ]; then
  echo "ERROR: $ECO already exists." >&2
  echo "  --merge  add the kit's files, delete nothing. Use this when the target has a .claude/ of" >&2
  echo "           its own (project skills, project agents) that must survive." >&2
  echo "  --force  replace skills/rules/hooks/commands/scripts/agents wholesale. Snapshots first" >&2
  echo "           and names what it overwrote, but anything the source does not have is DELETED." >&2
  exit 2
fi

echo "==> Installing Squad ecosystem"
echo "    source: $SRC_DIR"
echo "    target: $ECO"

# --- snapshot what the project owns, before overwriting it ---
# `rules/` and `agents/` are exactly where a project's own configuration lives: the routing
# table, its domain specialists, and every gate the "Next steps" below tells you to edit
# (code-quality-languages.txt, live-target.txt, acceptance-target.txt, the allow-lists).
# `--force` overwrote all of it silently. Measured: a `typescript | ... | ENABLED` line and a
# live-target block added to a fresh install were both gone after one re-run, with no message.
#
# In a repo that versions `.claude/` that is recoverable with `git restore`. TheoCode does not
# version it — the kit is a maintainer's tool, not product code — so silent was also permanent.
# The fix is not to merge (guessing which side of a config wins is how you get it wrong): it is
# to make the overwrite recoverable and loud. For an upgrade that must NOT clobber, use
# `patch_install.sh`, which copies a manifest and leaves agents/ and settings.json alone.
BACKUP_DIR=""
if [ -d "$ECO" ]; then
  BACKUP_DIR="$ECO/.install-backups/$(date +%Y%m%dT%H%M%S)"
  mkdir -p "$BACKUP_DIR"
  for item in rules agents; do
    [ -d "$ECO/$item" ] && cp -r "$ECO/$item" "$BACKUP_DIR/$item"
  done
  echo "==> Snapshot of the previous rules/ and agents/: $BACKUP_DIR"
fi

# --- cópia sem cache de ferramenta ------------------------------------------
# O cabeçalho deste script promete pular caches. `cp -r` não lê `.gitignore`, e
# os caches vivem DENTRO de `skills/` — então a promessa nunca foi cumprida:
# medido em 2026-08-26, uma instalação levava 342 `.pyc` e 51 diretórios de
# cache (3,9 MB) ao consumidor, 887 arquivos contra 496 versionados. Quase
# metade do que chegava não era o sistema, e auditores próprios do consumidor
# passavam a medir arquivos que não são do projeto.
#
# `tar` em pipe, não `rsync`: rsync não é garantido em toda máquina; tar é. As
# exclusões são de CACHE apenas — nada aqui decide o que é conteúdo do kit,
# essa continua sendo a árvore de origem.
KIT_EXCLUDES=(
  --exclude=__pycache__
  --exclude=.pytest_cache
  --exclude=.ruff_cache
  --exclude=.mypy_cache
  --exclude=.hypothesis
  --exclude=*.pyc
  --exclude=*.pyo
  --exclude=.DS_Store
)

# copy_tree <src> <dest> — copia o CONTEÚDO de src para dentro de dest.
copy_tree() {
  local src="$1" dest="$2"
  mkdir -p "$dest"
  tar -cf - -C "$src" "${KIT_EXCLUDES[@]}" . | tar -xf - -C "$dest"
}

# Remove cache que tenha sido gerado DEPOIS da cópia. A validação no fim deste
# script executa Python dentro do alvo, e o interpretador escreve `__pycache__`
# ao importar — sem esta limpeza o passo de verificação reintroduz exatamente o
# lixo que a cópia acabou de evitar.
prune_caches() {
  find "$1" -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \
       -o -name .mypy_cache \) -prune -exec rm -rf {} + 2>/dev/null || true
  find "$1" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
}

# --- tabela de roteamento: entregue VAZIA ------------------------------------
# `rules/cycle-backlog.md` é contrato do kit e vem inteiro, com uma exceção: a
# seção `## Domain routing` descreve QUAIS REPOSITÓRIOS EXISTEM, e a deste
# repositório é a do ecossistema em que o kit foi escrito. Entregá-la faz o
# consumidor herdar um mapa de repos que ele não tem — medido em 2026-08-18 num
# adotante: 88 itens com evidência `file:line` real, todos recusados por G1 como
# `unroutable_repo`. O gate estava certo; a configuração é que era de outro.
#
# `rules/templates/domain-routing.md` é um template de SEÇÃO, não de arquivo:
# por isso é excluído do loop que copia `templates/*` sobre `rules/*`.
apply_routing_template() {
  local target="$ECO/rules/cycle-backlog.md"
  local tpl="$SRC_DIR/rules/templates/domain-routing.md"
  [ -f "$target" ] && [ -f "$tpl" ] || return 0
  python3 - "$target" "$tpl" <<'PYEOF'
import re, sys
target, tpl = sys.argv[1], sys.argv[2]
body = open(target, encoding="utf-8-sig").read()
section = open(tpl, encoding="utf-8").read().rstrip("\n") + "\n\n"
patched, n = re.subn(r"^##\s+Domain routing\b.*?(?=^##\s|\Z)", lambda _: section,
                     body, count=1, flags=re.MULTILINE | re.DOTALL)
if n:
    open(target, "w", encoding="utf-8").write(patched)
PYEOF
  echo "    rules/cycle-backlog.md § Domain routing: entregue vazia (derive com detect_domains.py)"
}

# --- copy ecosystem code ---
# Two modes, because a target with a `.claude/` of its own has no correct answer in one of them.
# Measured on `theo-data-cells`: 598 files under `skills/` — 5 of the kit's, 10 the project wrote
# (`architecture-debate-table`, `placement-algorithms`, `quota-isolation`, …) — plus 13 named
# architect agents and their memory. The `rm -rf` below would have deleted every one of them, and
# a snapshot in `.install-backups/` is a consolation prize, not a correct install.
mkdir -p "$ECO"
# Vira 1 quando a tabela DERIVADA do consumidor foi preservada — nesse caso o
# template vazio não pode ser aplicado por cima dela.
ROUTING_PRESERVED=0
for item in skills rules hooks commands scripts; do
  if [ "$MERGE" -eq 1 ]; then
    echo "==> Merging $item/ (adding, deleting nothing)"
    mkdir -p "$ECO/$item"
    if [ "$item" = "rules" ]; then
      # A tabela de roteamento é configuração do projeto e mora num `.md` do kit.
      # Guardá-la antes de copiar e reinjetá-la depois: medido no `speculative`, a
      # reinstalação restaurou a tabela do ecossistema de origem por cima da derivada
      # e `route_domain <projeto>` foi de exit 0 para exit 1 — o projeto deixou de
      # rotear itens sobre si mesmo. O resto de cycle-backlog.md é contrato do kit.
      ROUTING_KEEP=""
      if [ -f "$ECO/rules/cycle-backlog.md" ]; then
        ROUTING_KEEP="$(mktemp)"
        python3 - "$ECO/rules/cycle-backlog.md" "$ROUTING_KEEP" <<'PYEOF'
import re, sys
src, out = sys.argv[1], sys.argv[2]
body = open(src, encoding="utf-8-sig").read()
m = re.search(r"^##\s+Domain routing\b.*?(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
open(out, "w", encoding="utf-8").write(m.group(0) if m else "")
PYEOF
      fi
      # `rules/*.txt` é a CONFIGURAÇÃO do projeto — linguagens habilitadas, alvo
      # vivo, allowlists, skills auxiliares declaradas. Copiar o template por cima
      # apaga ajuste local em silêncio: medido no `speculative`, onde a declaração
      # das 9 skills do projeto morreu na reinstalação seguinte. Os `.md` continuam
      # sendo atualizados — são o contrato normativo, e o kit é dono deles.
      for f in "$SRC_DIR/rules"/*; do
        [ -f "$f" ] || continue
        base="$(basename "$f")"
        case "$base" in
          *.txt)
            if [ -f "$ECO/rules/$base" ]; then
              echo "    kept (yours): rules/$base"
              continue
            fi
            ;;
        esac
        # Config específica do projeto nasce em branco: o kit distribuía a SUA
        # (Python habilitado, alvo vivo do ecossistema de origem) como se fosse do
        # consumidor. Os thresholds NÃO têm template — são defaults universais, e
        # esvaziá-los deixaria o gate sem banda nenhuma.
        if [ "$base" = "domain-routing.md" ]; then
          continue  # template de SEÇÃO, aplicado por apply_routing_template
        fi
        if [ -f "$SRC_DIR/rules/templates/$base" ]; then
          cp "$SRC_DIR/rules/templates/$base" "$ECO/rules/$base"
        else
          cp "$f" "$ECO/rules/$base"
        fi
      done
      if [ -n "$ROUTING_KEEP" ] && [ -s "$ROUTING_KEEP" ]; then
        python3 - "$ECO/rules/cycle-backlog.md" "$ROUTING_KEEP" <<'PYEOF'
import re, sys
target, keep = sys.argv[1], sys.argv[2]
body = open(target, encoding="utf-8-sig").read()
section = open(keep, encoding="utf-8").read()
patched = re.sub(r"^##\s+Domain routing\b.*?(?=^##\s|\Z)", lambda _: section,
                 body, count=1, flags=re.MULTILINE | re.DOTALL)
open(target, "w", encoding="utf-8").write(patched)
PYEOF
        echo "    kept (yours): rules/cycle-backlog.md § Domain routing"
        ROUTING_PRESERVED=1
        rm -f "$ROUTING_KEEP"
      fi
    else
      copy_tree "$SRC_DIR/$item" "$ECO/$item"
    fi
  else
    echo "==> Copying $item/"
    rm -rf "${ECO:?}/$item"
    copy_tree "$SRC_DIR/$item" "$ECO/$item"
    if [ "$item" = "rules" ]; then
      # Mesmo numa instalação limpa: a config específica do projeto nasce em branco.
      # Sem isto, o ramo não-merge copiava a configuração do kit (Python habilitado,
      # alvo vivo do ecossistema de origem) e o consumidor nascia com ela.
      for tpl in "$SRC_DIR"/rules/templates/*; do
        [ -f "$tpl" ] || continue
        [ "$(basename "$tpl")" = "domain-routing.md" ] && continue
        cp "$tpl" "$ECO/rules/$(basename "$tpl")"
      done
    fi
  fi
done

# A tabela de roteamento só nasce vazia quando não há uma derivada a preservar.
# Sobrescrever a do consumidor seria trocar um mapa correto por um vazio — o
# oposto exato do defeito que este template corrige.
if [ "$ROUTING_PRESERVED" -eq 0 ]; then
  apply_routing_template
fi

# `rules/templates/` é insumo do instalador, não regra. Deixá-lo no consumidor faria
# o check_xrefs varrer arquivos que não governam nada.
rm -rf "$ECO/rules/templates"

# `hooks/quality/` é o gate de smells DESTE repositório, gerado por `/quality-init`
# com limiares calibrados no p90 do código daqui (max_file_lines = 367, e assim por
# diante). Entregá-lo repetiria o defeito que o kit passou meses corrigindo em
# `rules/*.txt` e na tabela de roteamento: distribuir a configuração de quem escreveu
# como se fosse a de quem instala. O consumidor gera a dele com o mesmo comando,
# contra os números dele — o passo 3 das instruções finais o nomeia.
rm -rf "$ECO/hooks/quality"

# agents/ is copied FILE BY FILE, not wholesale. This repo dogfoods its own cycles, and
# `/implement` and `/review` write their per-run agent definitions into subdirectories here
# (`implement-slice-*/`, `review-*/`). Those are THIS repo's audit trail, not template content —
# and `cp -r` shipped two of them, dated May 2026, into every consumer install. The header above
# already promises to skip audit trails; this is what keeping that promise looks like.
# O kit NÃO tem especialistas para copiar. Os oito que ele carregava descreviam os
# repos de um ecossistema só; num consumidor que não é aquele, eram arquivos sobre
# repositórios inexistentes. Medido em 2026-08-20 sobre 41 instalações: 19 já viviam
# sem eles e nada quebrou, 11 escrevem os seus, e a tabela de roteamento passou a ser
# DERIVADA do projeto — o acoplamento que os justificava deixou de existir. Foram
# removidos da fonte em 2026-08-26; nunca estiveram versionados (`.gitignore`
# `agents/**`), então a flag `--with-domain-agents` copiava arquivos que só existiam
# na máquina de quem os escreveu.
#
# O README continua vindo sempre: ele descreve o MECANISMO de roteamento, não um
# domínio.
# `agents/` NUNCA é apagado, em modo nenhum. Aqui moram os especialistas que o projeto
# escreveu — e `rm -rf` no modo não-merge levava todos junto. Nada no kit justifica
# destruir o especialista de domínio de um consumidor: ele descreve o repositório dele,
# não é cópia de nada nosso, e não existe em lugar nenhum além dali.
mkdir -p "$ECO/agents"
if [ -f "$ECO/agents/README.md" ]; then
  # Depois que alguém o adapta, este README lista os agentes DO PROJETO.
  echo "    kept (yours): agents/README.md"
elif [ -f "$SRC_DIR/agents/README.md" ]; then
  echo "==> Copying agents/README.md (the routing mechanism)"
  cp "$SRC_DIR/agents/README.md" "$ECO/agents/README.md"
fi
# Top-level docs and manifest
for f in HOW-TO-USE.md README.md .active_plan.example; do
  [ -f "$SRC_DIR/$f" ] && cp "$SRC_DIR/$f" "$ECO/$f"
done
# O manifesto tem UM lugar canônico — `.claude-plugin/plugin.json`, onde o
# Claude Code o procura. Havia uma segunda cópia na raiz, e duas cópias de um
# manifesto divergem: a da raiz era a que o README apontava e a que este script
# instalava, enquanto o mecanismo nativo lia a outra.
[ -f "$SRC_DIR/.claude-plugin/plugin.json" ] && cp "$SRC_DIR/.claude-plugin/plugin.json" "$ECO/plugin.json"

# --- settings.json (plugin install variant) ---
if [ ! -f "$SRC_DIR/settings.plugin.json" ]; then
  echo "ERROR: $SRC_DIR/settings.plugin.json missing — required for plugin install layout." >&2
  exit 1
fi
if [ "$MERGE" -eq 1 ] && [ -f "$ECO/settings.json" ]; then
  # It wires this project's hooks. Replacing it is the one thing a merge must never do — a
  # settings.json is the most project-specific file in the tree, and losing it costs more than
  # every skill combined.
  cp "$SRC_DIR/settings.plugin.json" "$ECO/settings.json.kit-reference"
  echo "==> settings.json KEPT (yours). The kit's is at settings.json.kit-reference — diff it in."
else
  cp "$SRC_DIR/settings.plugin.json" "$ECO/settings.json"
  echo "==> settings.json written (plugin install variant)"
fi

# --- knowledge-base scaffold (empty, idempotent) ---
# Mirrors the SEMANTIC structure of the source's knowledge-base/ — every
# category folder that a cycle writes to. Slug-keyed subdirs that exist in
# the source (e.g. implementations/slice-X/, tools/argo-cd/, discoveries/
# snapshots/slice-X/) are NOT mirrored — those are historical artefacts of
# the plan repo's own dogfood, not part of the template.
echo "==> Scaffolding knowledge-base/ subdirs (semantic structure)"
KB_DIRS=(
  "plans"                       # /to-plan outputs
  "implementations"             # /implement halt-loop logs
  "reviews"                     # /review reports
  "audits"                      # /code-quality + /deps-audit reports
  "acceptance"                  # /acceptance records (end-user validation of a release)
  "acceptance/evidence"         # screenshots, console/network dumps, transcripts
  "maintenance-runs"            # per-item macro-loop audit trail
  "backlog"                     # /backlog-item intake logs
  "adrs"                        # MADR 3.0 ADRs
  "grills"                      # /grill-me Q&A logs
  "dogfood"                     # /dogfood anchor manifest
  "dogfood/evidence"            # /dogfood evidence files
  "judge-codex"                 # orthogonal LLM jury outputs (optional plugin)
  "tools"                       # read-only docs of tools the project depends on (consumer populates)
  "discoveries"                 # /discover-* root
  "discoveries/plans"           # /discover-plan outputs
  "discoveries/opportunities"   # /discover-execute outputs
  "discoveries/snapshots"       # hash-verified snapshots cited by opportunities
  "progress"                    # per-slug progress.md (read by hooks + session-catchup)
)
for d in "${KB_DIRS[@]}"; do
  mkdir -p "$ECO/knowledge-base/$d"
done

# Optional: bring over the project-agnostic backlog template
if [ -f "$SRC_DIR/knowledge-base/backlog.md" ]; then
  if [ ! -f "$ECO/knowledge-base/backlog.md" ]; then
    cp "$SRC_DIR/knowledge-base/backlog.md" "$ECO/knowledge-base/backlog.md"
  fi
fi

# agents/ holds only the README above. The routing table ships empty alongside it,
# so route_domain.py has nothing to resolve until the project derives both — a table
# with rows and no specialist on disk is what exit 3 (BROKEN ROUTE) exists to catch.


# --- What the overwrite actually took ---
# A snapshot nobody is told about is a snapshot nobody uses. Naming the files that CHANGED (not
# every file, which would be noise) is what turns a silent clobber into a diff someone can act on.
if [ -n "$BACKUP_DIR" ]; then
  CLOBBERED=$(
    cd "$BACKUP_DIR" && find . -type f | while read -r f; do
      cmp -s "$f" "$ECO/${f#./}" || echo "  ${f#./}"
    done
  )
  if [ -n "$CLOBBERED" ]; then
    echo ""
    # "or REMOVED" is not hedging: a specialist the source repo does not have — which is every
    # specialist a consumer writes for its own domains — is not overwritten, it is deleted by the
    # `rm -rf` above. Calling that "overwritten" would understate what just happened.
    echo "==> These files were OVERWRITTEN or REMOVED (they differed from the source):"
    echo "$CLOBBERED"
    echo ""
    echo "    Your previous copies: $BACKUP_DIR"
    echo "    Nothing was merged — diff them and re-apply what is yours. Project config lives in"
    echo "    rules/*.txt, the routing table in rules/cycle-backlog.md, and agents/*.md."
    echo "    To upgrade WITHOUT clobbering next time, use patch_install.sh instead."
  fi
fi

# --- Validation ---
# Run FROM THE TARGET. test_e2e_smoke.py resolves the ecosystem from the CWD, and the normal way
# to invoke this script is `cd squad && bash scripts/install.sh <target>` — so it was validating
# the source repo and printing OK for the installation it never opened. Measured: with a routed
# specialist and a cycle rule deleted from a fresh install, it answered
# `ecosystem: <workspace>/squad` / `ALL CHECKS PASSED` / exit 0. A check that cannot
# fail is worse than no check: it puts a green line next to a broken install.
#
# check_xrefs.py resolves from its own path and caught the same corruption (exit 1). Two lines
# printed the same word for two different amounts of verification.
# --- manifesto: o que veio do kit ------------------------------------------
# Um consumidor com auditor próprio precisa distinguir o que ele escreveu do que
# foi instalado. Medido no `speculative`: seu `scripts/audit.py` percorre
# `.claude/skills/*/SKILL.md` exigindo a spec Agent Skills; com o kit instalado
# ele passou de APROVADO a REPROVADO, auditando 37 skills que não são do projeto
# contra o padrão das 9 que são. Sem manifesto, a única saída seria adivinhar por
# nome. As skills do PROJETO nunca entram aqui — a lista sai da árvore do kit.
MANIFEST="$ECO/.kit-manifest.txt"
{
  echo "# Escrito por scripts/install.sh — o que ESTE kit trouxe para .claude/."
  echo "# Um caminho por linha, relativo a .claude/. Tudo que não está aqui é do projeto."
  echo "# Regenerado a cada instalação; não edite à mão."
  for d in "$SRC_DIR"/skills/*/; do
    [ -f "$d/SKILL.md" ] && echo "skills/$(basename "$d")"
  done
  for f in "$SRC_DIR"/rules/*; do
    [ -f "$f" ] && echo "rules/$(basename "$f")"
  done
  [ -f "$SRC_DIR/agents/README.md" ] && echo "agents/README.md"
} > "$MANIFEST"
echo "==> Manifest written: $(grep -vc '^#' "$MANIFEST") paths from the kit"

echo "==> Validating install (from the target, not from here)"
if (cd "$TARGET" && python3 .claude/scripts/check_xrefs.py --strict > /dev/null 2>&1); then
  echo "    check_xrefs.py: OK"
else
  echo "    check_xrefs.py: FAIL (re-run manually)"
fi

if (cd "$TARGET" && python3 .claude/scripts/test_e2e_smoke.py > /dev/null 2>&1); then
  echo "    test_e2e_smoke.py: OK"
else
  echo "    test_e2e_smoke.py: FAIL (re-run manually)"
fi

# Os dois validadores acima importam módulos do alvo, e o interpretador escreve
# `__pycache__` ao fazê-lo. Sem isto, o passo que confirma a instalação é o que
# volta a sujá-la.
prune_caches "$ECO"

cat <<EOF

==> Installation complete.

Next steps for the target project:

  1. (optional) Add a CLAUDE.md at the project root pointing to .claude/ and
     listing project-specific stack/conventions. Hooks read it on SessionStart.

  2. Derive the domain routing table FOR THIS PROJECT (it ships EMPTY, and gate
     G1 refuses every item until this runs):
       python3 .claude/skills/backlog-init/scripts/detect_domains.py --root . \
         --write .claude/rules/cycle-backlog.md
     Then write the specialist file(s) it names under .claude/agents/.

  3. Configure project-specific gates (defaults are no-op until set):
       .claude/rules/code-quality-languages.txt    # uncomment languages you ship
       .claude/rules/discover-web-allowlist.txt    # domains for /discover-execute
       .claude/rules/code-quality-thresholds.txt   # per-project overrides
       .claude/rules/deps-audit-allowlist.txt      # CVE exemptions (with sunset)

  4. Verify ralph-loop plugin is installed (required by /implement, /discover-execute,
     /plan-improve):
       jq '.enabledPlugins' ~/.claude/settings.json | grep ralph-loop

  5. Open the project in Claude Code. The settings.json wires hooks; skills/
     and commands/ are auto-discovered.

  6. First run: /to-plan "{one-sentence feature}"  OR  /grill-me {topic}
EOF
