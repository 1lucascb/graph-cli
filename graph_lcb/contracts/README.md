# Bundled graph contracts

This package contains the JSON Schemas copied into a graph workspace and the
optional contract templates used by `graph init`.

## Schemas

`schemas/entities.schema.json` and `schemas/edges.schema.json` describe the
shape of entity and edge contract files. `graph init` copies them into
`.graph/schemas/`; the generated contract files reference them with `$schema`.
They are editor-facing schemas. Runtime contract and graph validation is
implemented by `graph_lcb.graphs.engine`.

## Templates

Available templates are:

- **codebase** — repositories, packages, modules, files, classes, functions,
  tests, APIs, workers, data stores, queues, and external dependencies.
- **documents** — documents, concepts, decisions, people, and organizations.
- **data-pipeline** — pipelines, jobs, datasets, source systems, and
  destinations.
- **research** — questions, sources, findings, claims, and contributors.

Each template directory contains:

- `template.json`, with a short description shown by `graph init --list-templates`.
- `entities.json` and `edges.json`, which provide the corresponding example
  contracts, including `$schema` references.

Use `graph init --template=NAME` to apply a template to missing or empty
contracts. `graph init` without a template creates contracts containing only
their `$schema` keys. Templates are examples: review and adapt them to the
project's domain. Init preserves contracts that already define types.

Every entity and edge type in these templates has at least one required
property. Records using those types must provide their required properties;
an empty `properties` object fails validation.

When adding a template, keep its endpoint references consistent with the entity
types in the same template. Give every type a useful description, and verify
the contracts with `graph validate` in a temporary workspace before shipping.
