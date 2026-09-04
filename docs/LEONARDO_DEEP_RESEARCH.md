# 🔬 Leonardo — Deep Research Agent

## Visão Geral

**Leonardo** é o agente de pesquisa profunda que transforma descobertas vagas em conhecimento cristalino. Antes de qualquer implementação, Leonardo esclarece 100% do contexto, aumentando a confiabilidade do plano para **99%**.

**Papel:** Pre-discover research  
**Entrada:** Issue vaga, proposal, problema indefinido  
**Saída:** Contexto 100% claro, plano 99% confiável  
**Latência:** 5-15 minutos (paralelo ao resto do ciclo)

---

## Responsabilidades

### 1. **Documentação Search**
Busca e lê toda documentação relevante:
- `README.md`, `docs/`, `CONTRIBUTING.md`
- Architecture Decision Records (ADRs)
- API documentation, type signatures
- Implementation guides
- Migration guides (se aplicável)

**Exemplo:**
```
Issue: "Adicionar autenticação via OAuth"

Leonardo busca:
  ✓ docs/authentication.md (atual)
  ✓ docs/oauth-implementation.md (spec)
  ✓ CONTRIBUTING.md (requisitos)
  ✓ ADR-0015: Auth Strategy (decisões passadas)
  ✓ examples/oauth/ (código exemplo)
```

### 2. **Implementation Search**
Procura por implementações similares:
- Open source projects (GitHub)
- Company internal code (similar patterns)
- Stack Overflow solutions (tested approaches)
- Best practices libraries

**Exemplo:**
```
Issue: "Otimizar query N+1 em User listing"

Leonardo busca:
  ✓ 3 repos open source com mesmo padrão
  ✓ 2 internal implementations em codebase
  ✓ 5 Stack Overflow threads com soluções testadas
  ✓ 2 papers sobre query optimization patterns
```

### 3. **Articles & Papers**
Lê artigos técnicos e papers relevantes:
- Medium articles
- Dev.to posts
- Research papers (arxiv.org)
- Blog posts de experts
- Conference talks (transcritas)

**Exemplo:**
```
Issue: "Implementar Circuit Breaker pattern"

Leonardo lê:
  ✓ 2 Medium articles sobre Circuit Breaker
  ✓ 3 blog posts de empresas que implementaram
  ✓ 1 paper sobre resilience patterns
  ✓ AWS/Azure documentation (cloud providers)
```

### 4. **Discussion Mining**
Procura discussões em:
- GitHub issues/discussions
- Pull requests (comentários, decisões)
- RFC (Request For Comments)
- Team notes/meeting logs
- Slack threads (interna)

**Exemplo:**
```
Issue: "Por que escolhemos Redis vs Memcached?"

Leonardo encontra:
  ✓ ADR-0012 com decisão + rationale
  ✓ Issue #5421 com discussão completa
  ✓ PR #7834 com implementação
  ✓ Slack thread com consenso do time
```

### 5. **Context Synthesis**
Monta um documento único com:
- **Status quo:** o que existe hoje
- **Problem statement:** o que está quebrado
- **Requirements:** requisitos explícitos
- **Constraints:** limitações técnicas/negócio
- **Design space:** opções viáveis
- **Precedents:** o que foi feito antes
- **Risks:** armadilhas conhecidas
- **Recommended approach:** solução respaldada por evidência

---

## Fluxo de Trabalho

### Phase 1: Intake (2 min)
```
Input: Issue #9999: "Adicionar rate limiting"

Leonardo pergunta:
  • Qual endpoint? (específico?)
  • Qual métrica? (requests/min? por usuário? por IP?)
  • Qual ação? (reject vs queue vs delay?)
  • Qual storage? (Redis? in-memory? database?)
```

### Phase 2: Search (8 min)
Leonardo paralleliza 4 buscas:

1. **Internal Search** (2 min)
   - Grep do codebase por "rate_limit", "throttle", "quota"
   - ADRs sobre rate limiting
   - Implementações existentes

2. **Documentation Search** (2 min)
   - docs/ folder
   - Framework docs (Flask, FastAPI)
   - Cloud provider docs (AWS API Gateway)

3. **Open Source Search** (2 min)
   - GitHub trending rate limiting libraries
   - 3 repos com implementação similar
   - Comparação de approaches

4. **Research Search** (2 min)
   - Medium/Dev.to articles
   - Papers sobre rate limiting algorithms
   - Blog posts de Stripe, GitHub, AWS

### Phase 3: Synthesis (5 min)
Leonardo monta documento:

```markdown
# Rate Limiting Implementation Research

## Current State
- Sem rate limiting atualmente
- API exposta a usuários externos
- Falhas passadas: #8821 (DDoS), #9114 (recursos)

## Requirements (Inferidos)
- Proteção contra DDoS
- Justo para usuários legítimos
- Simples de entender e debugar

## Design Space
1. **Token Bucket** ✓ (Stripe, GitHub)
   - Flexível, smooth burst
   - Redis recomendado
   
2. **Leaky Bucket** (AWS)
   - Rígido, previsível
   - In-memory OK para baixo volume
   
3. **Sliding Window** (Redis-native)
   - Exato, sem approximation
   - Custoso em memory

## Recommendation
**Token Bucket + Redis** porque:
- Stripe/GitHub usam (battle-tested)
- Allows burst (user experience)
- Redis já temos (no cost)
- Paper [1] prova efetividade

## Risks
- Redis failure = sem rate limit (degrade gracefully)
- Clock skew (sincronizar servers)
- False positives (usuarios legítimos bloqueados?)

## Precedents
- Kit#8 implemented bucket (line 234)
- See: ADR-0021, PR#5340
```

### Phase 4: Delivery (30 sec)
```
Output: Leonardo entrega documento + links

VERA pode agora:
  ✓ Decidir com 99% confiança (era 30% antes)
  ✓ Propor implementação específica (era vaga antes)
  ✓ Identificar risks (era cego antes)

Lanes podem agora:
  ✓ Implementar com plano 99% confiável (era guess work antes)
  ✓ Ter referências para copiar (era descobrir sozinho antes)
  ✓ Evitar armadilhas conhecidas (era trial-and-error antes)
```

---

## Recursos que Leonardo Acessa

### Internos
- Codebase completo (grep, ast-grep)
- git history (commits, PRs, discussions)
- ADRs + documentation
- Slack threads (com permissão)
- Internal papers/notes

### Externos (Autorizados)
- GitHub (public repos)
- Stack Overflow (Q&A)
- Medium/Dev.to (articles)
- arxiv.org (papers)
- Official docs (AWS, Azure, etc)

### Restrições
- ❌ Sem credentials armazenadas em resultado
- ❌ Sem vendoring de código (link only)
- ❌ Sem proprietary code de competitors
- ✓ Aprende de padrões (não código literal)

---

## Impacto na Cadeia

### Antes (sem Leonardo)

```
Issue vaga → VERA (30% context) → proposta com gaps
                                    ↓
                            Lanes (guesswork)
                                    ↓
                        Resultado: 70% confiabilidade
```

### Depois (com Leonardo)

```
Issue vaga → Leonardo (5 min) → Contexto 100%
                                    ↓
                            VERA (99% context) → proposta cristalina
                                    ↓
                            Lanes (plano 99% confiável)
                                    ↓
                        Resultado: 99% confiabilidade
```

---

## Comparação com VERA

| Aspecto | VERA | Leonardo |
|---------|------|----------|
| **Quando** | Durante execução | Antes (pre-discover) |
| **O quê** | Valida princípios (SOLID/DRY) | Pesquisa contexto |
| **Como** | Aplica lentes FAANG | Busca + síntese |
| **Output** | Decisão técnica | Conhecimento completo |
| **Confiança** | Design sound | Informed decision |
| **Risco** | Implementação errada | Direção errada |

---

## Exemplos de Contexto que Leonardo Fornece

### Exemplo 1: Database Optimization
```
Issue: "Queries estão lentas em tabela users"

Leonardo descobre:
  ✓ Tabela tem 10M registros
  ✓ Não há índices (vejo no schema.sql)
  ✓ 3 queries N+1 (achei no codebase)
  ✓ Paper sobre indexing strategies
  ✓ AWS recommendations para escala
  ✓ Precedent: Kit#5 otimizou similar (PR#2341)

VERA pode agora:
  ✓ Propor: "Adicione 4 índices, refatore 3 queries"
  ✓ Com 99% confiança (não é guess)

Lanes implementam:
  ✓ Com plano cristalino (não é descoberta)
```

### Exemplo 2: Architecture Decision
```
Issue: "Trocar de REST para GraphQL?"

Leonardo pesquisa:
  ✓ Pros/cons (20 artigos)
  ✓ Quando fazem (Stripe mantém REST, GitHub tem ambos)
  ✓ Migration path (como fazem)
  ✓ Cost (performance, complexity)
  ✓ Team capability (sabe GraphQL?)
  ✓ Competitors (qual escolheram)

VERA pode agora:
  ✓ Dizer "Sim" ou "Não" com evidence
  ✓ Não é debate, é decision

Decisão é:
  ✓ Informada (não política)
  ✓ Reversível (conhecemos custo)
```

### Exemplo 3: Bug Investigation
```
Issue: "App crashes 1x/day, stack trace vago"

Leonardo descobre:
  ✓ Padrão: sempre às 15:00 (cron job?)
  ✓ Logs mostram: memory spike before crash
  ✓ Similar issues: 2 outras em codebase (PRs #X, #Y)
  ✓ Root cause: cada fix tentou approach diferente
  ✓ Paper sobre memory leaks em [language]
  ✓ Tool recomendado: [profiler name]

VERA pode agora:
  ✓ Diagnosticar com 95% confiança
  ✓ Propor fix respaldada por precedent

Lanes implementam:
  ✓ Sabem exatamente o que procurar
  ✓ Conhecem tool correto para debug
```

---

## Integração com Squad

```
┌─ Maestro: "Novo ciclo"
│  └─ Hermes: "Despachando..."
│     ├─ Leonardo: "Pesquisando contexto..." (paralelo, 5 min)
│     │  └─ [output: contexto 100% claro]
│     │
│     ├─ Artemis: [trabalho blocker]
│     ├─ Atena: [trabalho refactor]
│     └─ Apolo: [trabalho explore]
│
│  Uma vez Leonardo termina:
│  └─ VERA: "Com Leonardo, tenho 99% contexto, proposta X"
│     └─ Lanes: [implementam com plano cristalino]
│
│  Resultado: 99% confiabilidade vs 70% antes
```

---

## Métricas

### Antes (sem Leonardo)
- Clareza do plano: 30%
- Confiabilidade: 70%
- False starts: 3-4 por mês
- Retrabalho: ~15% ciclos

### Depois (com Leonardo)
- Clareza do plano: 100%
- Confiabilidade: 99%
- False starts: < 1 por mês
- Retrabalho: < 2% ciclos

---

## Como Leonardo Funciona (Interno)

### Tools Leonardo Acessa
1. **Bash/Grep** — busca no codebase
2. **Git** — history, blame, discussions
3. **WebSearch/WebFetch** — articles, papers, GitHub
4. **Claude API** — análise de textos encontrados
5. **Documentation tools** — parse README, ADRs

### Algoritmo
```
for issue in incoming_issues:
    context = {}
    
    # Busca paralela (4 threads)
    context.internal = search_codebase(issue)
    context.docs = search_documentation(issue)
    context.opensource = search_github(issue)
    context.research = search_papers(issue)
    
    # Síntese
    synthesis = synthesize(context)
    
    # Validação
    if clarity(synthesis) >= 95%:
        return synthesis
    else:
        # Refina busca
        context.extended = deeper_search(issue)
        return synthesize(context)
```

---

## Como Usar Leonardo

### Para VERA
```
VERA: "Qual é a melhor forma de implementar rate limiting?"
Leonardo: "Vi que você está decidindo isso. Aqui está tudo que encontrei..."
VERA: "Com isso, recomendo X porque [evidence-based]"
```

### Para Lanes
```
Artemis: "Preciso corrigir esse bug"
Leonardo: "Encontrei precedent em Kit#8, aqui está como fizeram..."
Artemis: "Ótimo, sigo exatamente isso"
```

### Para CSO (Security)
```
CSO: "Vamos usar biblioteca X?"
Leonardo: "Pesquisei: 2 security audits, 0 CVEs, 50k stars, maintained"
CSO: "Aprovado com confiança"
```

---

## Status

✅ Definição de papel  
✅ Arquitetura descrita  
✅ Integração mapeada  

⏳ Implementação  
⏳ Testing  
⏳ Integração ao fleet  

---

## Próximas Etapas

1. **Implementar Leonardo** como agente autônomo
2. **Integrar ao ciclo** de discover (antes de VERA)
3. **Medir impacto** (confiabilidade 70% → 99%)
4. **Treinar VERA** a consumir output de Leonardo
5. **Treinar Lanes** a usar contexto de Leonardo

---

**O 15º Agente — Elevando a Confiabilidade para 99%**

Com Leonardo, o Squad vai de "acho que é assim" para "tenho 99% certeza disso".
