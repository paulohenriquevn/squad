## Domain routing

`domain` é o que atribui um item a um especialista. **Esta tabela é DERIVADA do
projeto em que vive** — nada aqui pode ser copiado de outro ecossistema, porque
descreve quais repositórios existem neste.

**Ela nasce vazia, e isso é deliberado.** O kit distribuía a tabela do
ecossistema em que foi escrito: oito domínios apontando para vinte repositórios
que o consumidor não tem. O efeito foi medido em 2026-08-18, num adotante — 88
itens filados com evidência `file:line` real, todos recusados pelo gate G1 como
`BLOCKER/unroutable_repo`. O gate estava certo: ele genuinamente não conseguia
dizer quem era dono do trabalho. Herdar um mapa errado é pior que não ter mapa,
porque a recusa parece um problema do item e não da configuração.

### Derive a sua

```bash
python3 .claude/skills/backlog-init/scripts/detect_domains.py --root . \
  --write .claude/rules/cycle-backlog.md
```

O script lê a topologia do disco — não de um inventário, não de um `CLAUDE.md` —
e emite a tabela abaixo preenchida. Depois escreva o arquivo de especialista que
ele nomear, sob `.claude/agents/`.

Enquanto esta seção estiver vazia, `/backlog-item` recusa todo item. Essa recusa
é o comportamento correto: sem tabela, o roteamento seria um palpite.

| Domain | Repos (present on disk) | Specialist |
|---|---|---|
| _(vazio — rode `detect_domains.py --write`)_ | | |

**Um repo, um domínio.** `scripts/route_domain.py` cobra essa invariante: listar
o mesmo repositório sob dois domínios faz o roteamento depender da ordem de
iteração, e o mesmo item passa a rotear diferente entre execuções. Quando um
repositório abriga duas coisas de fato distintas — um serviço e o painel que o
consome, no mesmo checkout — separe pelo caminho (`repo` e `repo/subdir`), nunca
repetindo o nome nu nos dois.

**Registre a divergência em vez de apagá-la.** Um repositório que o inventário
nomeia e o disco não tem deve permanecer listado, marcado como sem checkout: um
item filado contra ele não roteia para lugar nenhum, e ver isso escrito é mais
barato que descobrir pela recusa.
