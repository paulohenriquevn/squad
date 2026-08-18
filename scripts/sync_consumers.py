#!/usr/bin/env python3
"""Propaga uma delta do kit para os consumidores SEM apagar melhoria local.

POR QUE ESTE SCRIPT EXISTE
--------------------------
Ao atualizar o `theo` nesta sessão, cinco arquivos tinham divergido da versão
anterior do kit, e a divergência era **melhoria local**: a convenção
`ECO=$([ -d .claude/skills ] …)` em 9 skills (que o kit não tem), o
`_is_test_file` do `check_xrefs` (fixture que cita regra inexistente de propósito
não é referência quebrada) e a lista de especialistas do projeto. Copiar por cima
teria apagado as três. Só não apagou porque a comparação foi feita arquivo a
arquivo, à mão.

Medido depois: **42 consumidores** têm o kit instalado. Nesse volume, "comparar
antes de copiar" não sobrevive como disciplina manual — vira este classificador.

A REGRA
-------
Para cada arquivo da delta, três conteúdos entram na conta: o do kit (`source`),
o da versão base de onde o consumidor veio (`base`) e o do consumidor (`target`).

- `NEW`          — o alvo não tem o arquivo. Copiar.
- `IDENTICAL`    — o alvo já está na versão nova. Nada a fazer.
- `UPDATE`       — o alvo está exatamente na versão base. Copiar é seguro.
- `LOCAL_CHANGE` — o alvo divergiu da base. **Não tocar.** O script nomeia o
                   arquivo e para; decidir o merge é trabalho humano, e é
                   exatamente onde uma cópia cega regride uma correção.

O script não faz merge de propósito. Um merge automático sobre 42 repos é a
forma de espalhar em silêncio o erro que este classificador existe para impedir.

Uso:
    python3 scripts/sync_consumers.py --base <sha> --targets arquivo.txt
    python3 scripts/sync_consumers.py --base <sha> --targets arquivo.txt --apply

Exit codes:
    0 — nada pendente de decisão humana
    1 — pelo menos um LOCAL_CHANGE (o alvo divergiu; ninguém foi tocado ali)
    2 — erro de invocação (sha inválido, alvo inexistente)
"""
from __future__ import annotations

import argparse
import enum
import re
import shutil
import subprocess
import sys
from pathlib import Path


class Action(enum.Enum):
    IDENTICAL = "identical"
    NEW = "new"
    UPDATE = "update"
    #: O alvo carrega um conteúdo que o kit JÁ TEVE em algum commit — instalação
    #: feita de uma versão antiga. É defasagem, não modificação: copiar é seguro.
    STALE = "stale"
    LOCAL_CHANGE = "local-change"


def classify(*, source: str, base: str | None, target: str | None) -> Action:
    """Decide o que fazer com um arquivo. Ver § A REGRA."""
    if target is None:
        return Action.NEW
    if target == source:
        return Action.IDENTICAL
    if base is not None and target == base:
        return Action.UPDATE
    return Action.LOCAL_CHANGE


def historical_versions(repo: Path, rel: str) -> set[str]:
    """Todo conteúdo que este caminho já teve no histórico do kit.

    Sem isto, um consumidor instalado de uma versão antiga aparece como
    "modificado localmente" em cada arquivo que o kit evoluiu desde então —
    medido: 231 falsos LOCAL_CHANGE em 40 consumidores, `install.sh` em quase
    todos. Distinguir atrasado de modificado é o que permite atualizar sem medo.
    """
    revisions = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--all", "--", rel],
        capture_output=True, text=True,
    ).stdout.split()
    contents: set[str] = set()
    for revision in revisions:
        blob = subprocess.run(
            ["git", "-C", str(repo), "show", f"{revision}:{rel}"],
            capture_output=True, text=True,
        )
        if blob.returncode == 0:
            contents.add(blob.stdout)
    return contents


def classify_with_history(*, source: str, base: str | None, target: str | None,
                          historical: set[str]) -> Action:
    """`classify`, mais a pergunta que ela não fazia: isto já foi o kit?"""
    action = classify(source=source, base=base, target=target)
    if action is Action.LOCAL_CHANGE and target in historical:
        return Action.STALE
    return action


def _git_show(repo: Path, sha: str, rel: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}:{rel}"],
        capture_output=True, text=True,
    )
    return result.stdout if result.returncode == 0 else None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def delta_files(repo: Path, base: str) -> list[str]:
    """Arquivos alterados de `base` até HEAD que o install leva para o consumidor."""
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{base}..HEAD"],
        capture_output=True, text=True, check=True,
    )
    prefixes = ("rules/", "skills/", "scripts/", "hooks/", "commands/", "agents/")
    return sorted(
        line for line in result.stdout.splitlines()
        if line.startswith(prefixes) and (repo / line).is_file()
    )


_RULES_REF_RE = re.compile(r"(?<![A-Za-z0-9_/-])(?:\.claude/)?rules/([A-Za-z0-9._-]+\.(?:md|txt))")


def missing_rule_dependencies(kit: Path, eco: Path, files: list[str]) -> list[str]:
    """Regras que os arquivos da delta citam e o consumidor não tem.

    A delta precisa ser FECHADA: um `run_validation.py` novo cita
    `rules/knowledge-base-location.md`, e num consumidor defasado esse arquivo não
    existe — o `check_xrefs` do alvo passa a reprovar por referência quebrada.
    Medido na primeira aplicação: 13 dos 40 consumidores ficaram vermelhos assim.

    Só o que FALTA entra. Regra que o alvo já tem nunca é sobrescrita aqui: os
    `rules/*.txt` são a configuração do projeto (allowlists, live-target,
    thresholds), e copiar por cima destruiria ajuste local.
    """
    missing: list[str] = []
    for rel in files:
        content = _read(kit / rel)
        if content is None:
            continue
        for name in _RULES_REF_RE.findall(content):
            candidate = f"rules/{name}"
            if (kit / candidate).is_file() and not (eco / candidate).exists() \
                    and candidate not in missing:
                missing.append(candidate)
    return sorted(missing)


def sync_target(kit: Path, target_root: Path, files: list[str], base: str,
                *, apply: bool) -> dict[str, list[str]]:
    """Classifica (e opcionalmente aplica) a delta em UM consumidor."""
    eco = target_root / ".claude"
    outcome: dict[str, list[str]] = {action.value: [] for action in Action}

    for rel in files:
        source = _read(kit / rel)
        if source is None:
            continue
        target_content = _read(eco / rel)
        action = classify(
            source=source,
            base=_git_show(kit, f"{base}^", rel),
            target=target_content,
        )
        if action is Action.LOCAL_CHANGE:
            # Só paga o custo de varrer o histórico quando há divergência.
            if target_content in historical_versions(kit, rel):
                action = Action.STALE
        outcome[action.value].append(rel)
        if apply and action in (Action.NEW, Action.UPDATE, Action.STALE):
            destination = eco / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(kit / rel, destination)

    # Fecha a delta: as regras que ela cita e o alvo não tem.
    for rel in missing_rule_dependencies(kit, eco, files):
        outcome[Action.NEW.value].append(rel)
        if apply:
            destination = eco / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(kit / rel, destination)
    return outcome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True,
                        help="primeiro commit da delta (a base é o PAI dele)")
    parser.add_argument("--targets", type=Path, required=True,
                        help="arquivo com um caminho de consumidor por linha")
    parser.add_argument("--kit", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--apply", action="store_true",
                        help="sem isto, apenas classifica (dry-run)")
    args = parser.parse_args(argv)

    if not args.targets.is_file():
        print(f"FATAL: lista de alvos não encontrada: {args.targets}", file=sys.stderr)
        return 2
    try:
        files = delta_files(args.kit, f"{args.base}^")
    except subprocess.CalledProcessError:
        print(f"FATAL: sha inválido: {args.base}", file=sys.stderr)
        return 2

    print(f"delta: {len(files)} arquivos desde {args.base}^")
    print(f"modo : {'APLICANDO' if args.apply else 'dry-run (nada é escrito)'}\n")

    needs_human: dict[str, list[str]] = {}
    totals = {action.value: 0 for action in Action}

    for line in args.targets.read_text(encoding="utf-8").splitlines():
        target = line.strip()
        if not target or target.startswith("#"):
            continue
        root = Path(target).expanduser()
        if not (root / ".claude").is_dir():
            print(f"  {target}: sem .claude/ — ignorado")
            continue

        outcome = sync_target(args.kit, root, files, args.base, apply=args.apply)
        for key, items in outcome.items():
            totals[key] += len(items)
        if outcome[Action.LOCAL_CHANGE.value]:
            needs_human[target] = outcome[Action.LOCAL_CHANGE.value]

        print(f"  {Path(target).name:<26} "
              f"new={len(outcome['new']):<3} update={len(outcome['update']):<3} "
              f"stale={len(outcome['stale']):<3} igual={len(outcome['identical']):<3} "
              f"local={len(outcome['local-change'])}")

    print(f"\ntotais: {totals}")
    if needs_human:
        print("\nDivergiram do kit — NINGUÉM foi tocado nestes arquivos. "
              "Decidir o merge é trabalho humano:")
        for target, items in needs_human.items():
            print(f"  {target}")
            for rel in items:
                print(f"    - {rel}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
