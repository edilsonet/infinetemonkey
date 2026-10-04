# anac-legislacao

Corpus da legislacao da ANAC para qualquer inteligencia artificial que leia arquivos.
O agente nao memoriza regulamentos inteiros. Ele consulta o indice, abre so as
subsecoes nomeadas, e cita o fragmento.

## Profile

Doctrine. Este namespace guarda a doutrina de recuperacao sobre RBAC, IS e IAC, mais o
grafo fragmentado da norma. Nao e um starter reduzido: carrega a base completa
(`INDEX.md`, `canon/`, `playbooks/`, `support/`, `synthesis/`) e as pastas aditivas
`pillars/`, `concepts/`, `decisions/`.

## Load first

1. `canon/core-doctrine.md`: regras duras de fragmentacao e recuperacao minima.
2. `canon/agent-load-order.md`: ordem por classe de pergunta.
3. `support/indexes/keyword-index.yml`: mapa assunto -> fragmentos.
4. `support/indexes/category-index.yml`: mapa categoria -> fragmentos.
5. `support/catalogs/rbac.yml`, `is.yml`, `iac.yml`: inventario de documentos.

## Query classes

- **Onde esta a regra sobre X** (manutencao, licenca, operador, aerodromo): leia o
  indice de palavras-chave, depois so os YAML em `support/fragments/`.
- **A pergunta esta em linguagem natural e o indice nao tem a chave**: use o recuperador
  semantico `tools/anac-rag` (`POST /query`). Ele devolve janelas com o `cite` exato de
  origem. Caminho de recall, nao substitui o indice. Precisa de `ANAC_RAG_TOKEN`; sem ele,
  volte ao indice por palavras-chave.
- **O que e RBAC, IS ou IAC**: `concepts/rbac.md`, `concepts/is.md`, `concepts/iac.md`.
- **Como fragmentar ou reingerir**: `pillars/fragmentacao-legislativa.md` e
  `playbooks/ingerir-legislacao-anac.md`.
- **Qual granularidade usar**: `decisions/granularidade-subsecao.md`.
- **Texto integral de um documento**: `support/extracted/<tipo>/<codigo>.md`, nunca
  como primeira leitura.
- **Fonte e proveniencia**: `support/sources/` e o catalogo YAML.

## Stable vs stateful

Estavel: doutrina de recuperacao, conceitos de tipo normativo, decisao de
granularidade. Stateful: catalogos, PDFs, extrações e indices em `support/`, porque
a ANAC emenda normas. Desconfie de um fragmento se o catalogo mostrar emenda mais
nova do que a data de ingestao.

## Open disputes

A ANAC viva nao responde neste ambiente. O ingest usa Arquivo.pt e preserva a URL
original. Lacunas de emendas posteriores ao snapshot estao em
`synthesis/lacunas-de-cobertura.md`.

## What this namespace drives

- Consultas de compliance e manutencao por agentes de arquivo.
- Respostas citadas a nivel de subsecao (exemplo: 43.1(a), nao "o RBAC 43").
- Reingestao repetivel via `tools/anac_ingest/ingest.py`.

## Archive and provenance

Nao ha `archive/` de perfil. Proveniencia vive em `support/`:

- `support/sources/html/` e `support/sources/pdf/`: capturas brutas
- `support/extracted/`: texto integral em Markdown
- `support/fragments/`: YAML por subsecao
- `support/indexes/`: indices de palavra-chave, categoria e fragmento
- `support/catalogs/`: inventario RBAC, IS, IAC

Trate `support/` como evidencia mecanica, nao como doutrina.

## Common misreadings

- Ler o PDF inteiro porque a pergunta menciona o numero do RBAC. Correcao: o numero
  escolhe o documento, o indice escolhe a subsecao.
- Tratar IS como se fosse RBAC. Correcao: IS interpreta e detalha; nao substitui o
  regulamento.
- Tratar IAC vigente como se todas ainda valessem. Correcao: muitas IAC foram
  revogadas ou substituidas por IS. Confira o catalogo.
- Citar apendice como secao numerada. Correcao: Apendice A, B, C tem cites proprios.

## Map

- `canon/`: doutrina de recuperacao
- `pillars/`: fragmentacao legislativa
- `concepts/`: RBAC, IS, IAC
- `decisions/`: granularidade de subsecao
- `playbooks/`: consultar e ingerir
- `support/`: fontes, extrações, fragmentos, indices
- `synthesis/`: lacunas e notas derivadas
