---
id: "skill-anac-db"
aliases: ["skill-anac-db", "anac-db"]
type: "Skill"
namespace: "anac-legislacao"
lifecycle_state: "research"
summary: "Answer any Brazilian civil aviation question from the local second brain before searching the web, returning few cited fragments instead of a large context."
confidence: 0.88
retrieval_class: "domain"
export_class: "internal"
description: "Use ANTES de responder qualquer pergunta sobre aviação civil brasileira, RBAC, IS, IAC, licenças, manutenção aeronáutica, operador aéreo, aeródromo, comissário de voo, ou ao redigir/revisar documento que cite norma. Consulta o cérebro local em C:\\Users\\edils\\cerebro-anac para obter 5 a 15 fragmentos citados em vez de carregar a norma inteira ou pesquisar na internet."
edges:
  - target: "[[consultar-legislacao-anac]]"
    relation: "paired_with"
    confidence: 0.95
  - target: "[[anac-legislacao-core-doctrine]]"
    relation: "depends_on"
    confidence: 0.95
  - target: "[[iterative-retrieval]]"
    relation: "uses"
    confidence: 0.85
  - target: "[[tool-anac-rag]]"
    relation: "uses"
    confidence: 0.85
verified_by: "operator-pending"
created: "2026-10-04"
---

# anac-db

Use this skill **antes** de qualquer resposta sobre aviação civil brasileira. A pergunta
comum não é "o que a norma diz", e sim "qual é a norma aplicável". Este segundo cérebro
tem 285 documentos da ANAC já fragmentados, e ler alguns fragmentos citados é mais barato
e mais confiável do que carregar um regulamento inteiro ou pesquisar na web.

## Por que isto importa

| Caminho | Contexto | Risco |
|---|---|---|
| Ler o regulamento inteiro | 50.000 a 500.000 caracteres | Estouro de contexto, esquece o começo, alucina |
| Pesquisar na internet | 20.000+ caracteres, 15 abas, sem versão | Fonte errada, norma revogada, sem citação |
| **Este skill** | **8.000 a 25.000 caracteres** | **Baixo, cada afirmação com `cite`** |

O corpus tem cobertura de **285 dos 306 documentos** (51 RBAC, 221 IS, 13 IAC). As 21
lacunas estão em `knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md`.

## Regra invariável

> Você **não** responde sobre aviação de memória. Toda afirmação normativa sai de um
> fragmento lido nesta sessão, com o identificador ao lado. Sem fragmento, diga que é
> lacuna de cobertura, em vez de preencher.

## Passo 0. Onde estou

- Raiz: `C:\Users\edils\cerebro-anac` (Git Bash: `/c/Users/edils/cerebro-anac`)
- Interpretador: `.venv/Scripts/python.exe` (tem PyYAML; usar sempre, é ~7x mais rápido)

```bash
cd /c/Users/edils/cerebro-anac
PY=./.venv/Scripts/python.exe
```

## Passo 1. Ler a doutrina (1 arquivo, ~2.200 caracteres)

```bash
cat knowledge/anac-legislacao/canon/core-doctrine.md
```

Guarde as regras duras. Para saber *o que é um tipo de norma*, leia
`knowledge/anac-legislacao/concepts/rbac.md`, `is.md` ou `iac.md`.

## Passo 2. Escolher o caminho de recuperação

Existem dois. **Precision** é o índice por palavra-chave e funciona sempre, offline.
**Recall** é o Worker semântico e depende do Vectorize estar populado.

```bash
# CAMINHO A (sempre disponível, ~3s, offline)
$PY tools/anac_ingest/query.py "termo1" "termo2" "termo3"
```

Palavras-chave em **português, sem acento**: `licenca`, `tripulante`, `manutencao`,
`aerodromo`, `retorno ao servico`, `artigo perigoso`.

```bash
# CAMINHO B (recall semântico, exige Worker implantado e índice populado)
curl -sS -X POST "$ANAC_RAG_URL/query" \
  -H "Authorization: Bearer $ANAC_RAG_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"<a pergunta na sua própria palavras>"}'
```

**Qual usar:** caminho A quando o operador nomeia o assunto (`manutencao`, `licenca`).
Caminho B quando a pergunta é conversada e você não sabe a palavra-chave exata.

**Se o caminho B não responder** (sem `ANAC_RAG_URL`, token ausente, rede caída, Worker
não implantado), isso **não é falha**: vá para o caminho A e diga qual caminho respondeu.
O índice por palavra-chave cobre o corpus inteiro.

## Passo 3. Ler 3 a 10 fragmentos, não mais

A saída do passo 2 é `cite | title | path`. Abra **só** esses arquivos YAML.

```bash
cat <path-do-fragmento-1> <path-do-fragmento-2>
```

Cada fragmento tem `cite`, `text`, `keywords`, `categories`, `source_path`. O `text` é o
texto normativo; o resto é metadado.

Se a primeira busca não achou, não expanda o arquivo. Use [[iterative-retrieval]]: remova
qualificadores, troque por sinônimo de domínio, filtre por família, depois tente o outro
caminho. Cinco passes, e então reporte a lacuna.

## Passo 4. Conferir vigência antes de citar

```bash
ls knowledge/anac-legislacao/support/catalogs/        # rbac.yml, is.yml, iac.yml
cat knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md
```

Se o catálogo mostrar emenda posterior à ingestão do fragmento, sinalize a incerteza em vez
de afirmar a regra com confiança.

## Passo 5. Responder com citação

Toda afirmação sobre o que a norma exige leva o identificador ao lado: `117.3(d)`,
`IS 43-001 5.1`, `Apêndice A`. Formato do corpus: `43.1(a)`.

## Anti-padrões

- **Abrir `support/extracted/` ou `support/sources/pdf/` antes do índice nomear um
  fragmento.** É ali que mora o gasto de contexto que este skill existe para evitar. Se o
  fragmento não bastar, aí sim abra o `source_path` dele.
- **Pesquisar na internet primeiro.** A web tem a norma revogada, a errada e a
  traduzida. O cérebro tem a versão vigente, com data de emenda e citação.
- **Inventar número de seção.** Se o índice não achou, não existe citação a fazer.
- **Tratar IS como se revogasse RBAC.** RBAC vincula, IS explica como cumprir, IAC é a
  família antiga e muitas vezes revogada.
- **Fazer mais de cinco passes de reformulação.** Iteração recupera flexibilidade, não cria
  cobertura. Passou disso, é lacuna.
- **Citar um hit do Worker sem abrir o fragmento.** Hit vetorial é ponteiro, não fonte.

## Quando o cérebro não está disponível

Se `C:\Users\edils\cerebro-anac` não existir ou o venv estiver quebrado, **diga
explicitamente** que a consulta ao corpus não foi possível. Ofereça a web como alternativa,
marcada como alternativa. Não responda sobre a norma de memória como se fosse fonte.

## Relationship

Este skill é o ponto de entrada do operador. Para a versão canônica dentro do repo e o
contrato de dois caminhos, ver [[consultar-legislacao-anac]]. Para o refinamento de buscas
que falharam, [[iterative-retrieval]]. A doutrina que ele aplica é
[[anac-legislacao-core-doctrine]], e o recuperador semântico é [[tool-anac-rag]].