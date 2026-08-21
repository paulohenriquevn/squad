"""A condição de término nomeia comandos, e nada garantia que eles existem.

`compose_goal_condition.py` embute `/grill-me`, `/discover-plan`,
`/plan-confidence`, `/implement`, `/code-quality`, `/review` e `/acceptance`
como strings literais no texto da condição, cada um ao lado do artefato que deve
produzir. Renomeie ou aposente qualquer um deles e a condição continua
compondo, continua armando o Stop hook e continua se lendo como autoritativa —
enquanto manda o agente rodar um comando que não existe mais.

O `check_xrefs.py` não cobre este caso: o Check 7 varre `skills/**/*.py` atrás de
referências a `rules/*.md`, nunca a `/skill-name`. E o histórico mostra que a
aposentadoria de skills é real, não hipotética — a retirada das skills de roadmap
deixou 15 referências mecanicamente substituídas, uma delas apontando para a
skill errada.

O modo de falha é silencioso e tardio: quem descobre é o agente, no meio de uma
sessão já vinculada, ao tentar satisfazer um critério impossível.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "skills" / "cycle-goal" / "scripts" / "compose_goal_condition.py"

# `/foo-bar` em prosa. Exclui caminhos (`/tmp/x`) exigindo hífen-ou-fim e
# rejeitando um `/` logo depois.
_COMMAND_RE = re.compile(r"(?<![\w/.])/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?![\w/-])")

# Tokens que casam a forma mas não são comandos de skill.
_NOT_COMMANDS = {"n", "a"}

# Primitivas de CLI do Claude Code — reais, mas nunca skills deste repositório.
# `goal` é citada porque a skill existe em boa parte para explicar por que NÃO a
# usa (`SKILL.md § Why this does not use /goal`) e de onde herdou o cap de 4000
# caracteres. Proibir a menção obrigaria a reescrever a explicação para não poder
# nomear seu próprio assunto.
#
# A distinção que importa: uma primitiva citada em prosa histórica é referência;
# um comando impresso numa mensagem de erro é instrução. Foi a segunda forma que
# mandou o usuário rodar `roadmap-init`, aposentada — por isso este allowlist é
# nominal e curto, nunca um padrão que absolva a categoria inteira.
_CLI_PRIMITIVES = {"goal"}


def _existing_skills() -> set[str]:
    return {p.parent.name for p in (_REPO / "skills").glob("*/SKILL.md")}


def test_script_exists() -> None:
    # Arrange / Act / Assert — o teste inteiro é vácuo se o alvo sumiu de lugar.
    assert _SCRIPT.is_file(), f"alvo do teste não encontrado: {_SCRIPT}"


def test_every_command_named_in_the_condition_is_a_real_skill() -> None:
    # Arrange
    source = _SCRIPT.read_text(encoding="utf-8")
    skills = _existing_skills()

    # Act — todo `/comando` citado no script, com a linha onde aparece.
    cited: dict[str, int] = {}
    for lineno, line in enumerate(source.split("\n"), 1):
        for match in _COMMAND_RE.finditer(line):
            name = match.group(1)
            if name in _NOT_COMMANDS or name in _CLI_PRIMITIVES:
                continue
            cited.setdefault(name, lineno)

    # Assert — nenhum deles pode ser um comando que não existe.
    ghosts = {n: ln for n, ln in cited.items() if n not in skills}
    assert not ghosts, (
        "compose_goal_condition.py nomeia comandos sem skill correspondente "
        f"(nome -> linha): {ghosts}. A condição comporia e armaria assim mesmo, "
        "mandando o agente rodar algo inexistente."
    )


def test_no_user_facing_message_points_at_a_command_that_does_not_exist() -> None:
    """O allowlist de primitivas vale para prosa, nunca para instrução.

    `_CLI_PRIMITIVES` isenta menções históricas em docstrings e comentários. Uma
    mensagem impressa ao usuário é outra coisa: ela diz o que fazer AGORA. Foi
    exatamente essa forma que mandou rodar `roadmap-init` depois da aposentadoria.
    Aqui nada é isento — se está num `print`, tem que existir.
    """
    # Arrange
    source = _SCRIPT.read_text(encoding="utf-8")
    skills = _existing_skills()
    tree = ast.parse(source)

    # Act — todo literal de string que chega a um `print(...)`.
    printed: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                printed.append((sub.value, node.lineno))

    # Assert
    ghosts: dict[str, int] = {}
    for text, lineno in printed:
        for match in _COMMAND_RE.finditer(text):
            name = match.group(1)
            if name in _NOT_COMMANDS or name in skills:
                continue
            ghosts.setdefault(name, lineno)

    assert not ghosts, (
        "mensagem impressa ao usuário nomeia comando inexistente "
        f"(nome -> linha do print): {ghosts}. Um remédio que não existe é pior "
        "que nenhum: manda procurar em vez de resolver."
    )


def test_the_condition_actually_names_the_pipeline() -> None:
    """Guarda contra o teste acima passar por vacuidade.

    Se um refactor trocar os literais por interpolação, o teste anterior fica
    verde sem verificar nada. Este exige que a espinha dorsal ainda esteja lá.
    """
    # Arrange
    source = _SCRIPT.read_text(encoding="utf-8")

    # Act / Assert
    for command in ("/implement", "/code-quality", "/review", "/acceptance"):
        assert command in source, (
            f"{command} sumiu do texto da condição — se foi intencional, "
            "atualize `requires` em skills/cycle-goal/SKILL.md junto"
        )
