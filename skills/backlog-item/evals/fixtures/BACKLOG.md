# Backlog — registro único de manutenção do ecossistema Theo

> **Fixture de eval.** Registry sintético usado pelas baterias de eval das skills do Squad.
> Não é o registry real do umbrella. Os itens são coerentes entre si para que um eval possa
> exercitar dedup, roteamento e transições de status sem depender do estado de produção.

Ids são monotônicos e **nunca renumerados** — um item morto guarda o número para sempre.

## Como um item chega aqui

Dois produtores, um schema: `/backlog-item` (porta humana, hipótese sem evidência) e
`/discover --sweep` (achado medido, com evidência já anexada). O contrato do schema vive em
`rules/cycle-backlog.md`; este arquivo é dado.

## Roteamento de domínio

| Domain | Repos | Specialist |
|---|---|---|
| `engine-go` | `theo` | `agents/engine-go.md` |
| `control-plane` | `theo-cloud`, `theo-traefik-mcp` | `agents/control-plane.md` |
| `data-plane-ts` | `theo-memory`, `theo-rag`, `theo-lens`, `theo-trust`, `theo-skills`, `theo-promptly` | `agents/data-plane-ts.md` |
| `theo-db` | `theo-db` | `agents/theo-db.md` |
| `infra-terraform` | `theo-infra-modules`, `theo-infra-live` | `agents/infra-terraform.md` |
| `contracts-auth` | `theo-contracts` | `agents/contracts-auth.md` |
| `frontend-dashboard` | `theo-cloud/dashboard` | `agents/frontend-dashboard.md` |
| `platform-cli` | `theo-cli`, `theo-storage` | `agents/platform-cli.md` |

## Itens

## B-007 — Suspeita de N+1 no ingest do theo-rag   [ ]

> Registrado 2026-05-20 por `/backlog-item` (slug: `theo-rag-ingest-n-plus-one`).

domain: data-plane-ts
repo: theo-rag
suggested_mode: evolve
source: human
evidence: none-yet
why_now: ingest de lote grande parecia lento em maio
status: killed
kill_reason: medido em 2026-05-28 — o ingest faz uma query em lote independente do número de documentos (`theo-rag/src/ingest/batch.ts:142`). A hipótese não se sustentou.
dod:
  - o ingest faz um número de queries independente da contagem de documentos
## B-009 — Cache de sessão sobrevive à troca de tenant   [x]

> Registrado 2026-06-11 por `/backlog-item` (slug: `dashboard-tenant-cache-leak`).

domain: frontend-dashboard
repo: theo-cloud/dashboard
suggested_mode: bug
source: human
evidence: `dashboard/src/state/session.ts:88`
why_now: um usuário viu dados do tenant anterior após trocar de conta
status: shipped
dod:
  - trocar de tenant limpa o cache de sessão
  - teste de regressão cobre a troca

## B-014 — Reduzir round-trips do endpoint de listagem de traces   [ ]

> Registrado 2026-07-30 por `/backlog-item` (slug: `theo-lens-listing-round-trips`).

domain: data-plane-ts
repo: theo-lens
suggested_mode: review
source: human
evidence: none-yet
why_now: o dashboard passou a carregar 30d por padrão em 2026-07 e a listagem ficou visivelmente mais lenta
status: raw
dod:
  - a listagem faz um número de queries independente da contagem de spans
  - teste de regressão falha no estado atual

## B-018 — Listagem de traces devolve 500 na janela de 30 dias   [ ]

> Registrado 2026-08-01 por `/backlog-item` (slug: `theo-lens-listing-500`).

domain: frontend-dashboard
repo: theo-cloud/dashboard
suggested_mode: live-test
source: human
evidence: none-yet
why_now: relatado por dois usuários internos depois do deploy de 2026-07-28
status: raw
dod:
  - a listagem responde 200 com janela de 30d
  - a causa está atribuída a ambiente ou a produto, com evidência

## B-021 — Lógica de auth duplicada em três lugares no theo-cloud   [ ]

> Registrado 2026-08-02 por `/backlog-item` (slug: `theo-cloud-auth-duplication`).

domain: control-plane
repo: theo-cloud
suggested_mode: review
source: human
evidence: none-yet
why_now: as três cópias divergiram uma vez em 2026-06 e o bug levou dois dias para ser achado
status: raw
dod:
  - a resolução de tenant tem um único ponto de verdade
  - teste cobre o caminho que divergiu

## B-022 — `theo deploy` retorna exit 0 quando um passo falha   [ ]

> Registrado 2026-08-03 por `/backlog-item` (slug: `theo-cli-exit-code`).

domain: platform-cli
repo: theo-cli
suggested_mode: bug
source: human
evidence: none-yet
why_now: um pipeline de CI deu verde com deploy parcial em 2026-08-02
status: raw
dod:
  - `theo deploy` retorna exit != 0 quando qualquer passo falha
  - teste de regressão falha no estado atual

## B-025 — Navegação do trace explorer   [ ]

> Registrado 2026-08-04 por `/backlog-item` (slug: `theo-lens-explorer-navigation`).
> Item deliberadamente vago — usado para exercitar a detecção de hipótese infalsificável.

domain: data-plane-ts
repo: theo-lens
suggested_mode: evolve
source: human
evidence: none-yet
why_now: reclamação recorrente em conversas de time, sem medição
status: raw
dod:
  - navegar entre spans aninhados custa menos passos que hoje

## B-030 — Latência do dashboard sob carga   [ ]

> Registrado 2026-08-04 por `/backlog-item` (slug: `dashboard-latency-under-load`).

domain: frontend-dashboard
repo: theo-cloud/dashboard
suggested_mode: live-test
source: human
evidence: none-yet
why_now: pico de reclamações após o deploy de 2026-08-03
status: raw
dod:
  - p95 de carregamento medido, com janela e condições declaradas

## B-031 — Função aparentemente não usada em theo-contracts   [ ]

> Registrado 2026-08-05 por `/backlog-item` (slug: `theo-contracts-unused-helper`).

domain: contracts-auth
repo: theo-contracts
suggested_mode: review
source: human
evidence: none-yet
why_now: apareceu num grep durante outra investigação; nenhum chamador local
status: raw
dod:
  - a função tem chamador confirmado, ou é removida com os consumidores verificados

