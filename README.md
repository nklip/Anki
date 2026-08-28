# Anki Flashcards

This repository contains Anki-ready study materials and teaching diagrams for Java, artificial intelligence, and system design.

## Artificial intelligence

The [`ai`](ai/) folder contains Markdown cards about artificial-intelligence concepts and reusable SVG teaching diagrams in [`ai/svg`](ai/svg/).

Current material includes the [Cosine Similarity](ai/Cosine%20similarity.md) card, with diagrams covering its geometry, calculation, and role in retrieval-augmented generation (RAG). The SVG folder also contains visuals for embeddings, vector search, lexical and semantic retrieval, reciprocal rank fusion, large language model processing, Model Context Protocol (MCP), streaming, temperature, and related topics.

## Java

The [`java`](java/) folder contains Java learning materials:

- Markdown (`.md`) files with Anki-ready flashcard content.
- SVG (`.svg`) diagrams and schemas in [`java/svg`](java/svg/) that illustrate concepts covered by the cards.

The cards cover modern Java syntax, collections, concurrency, the Java Memory Model, JVM internals, garbage collection, JPA, Hibernate, and related development topics.

## System design

The [`system design`](system%20design/) folder contains chapter-based notes and diagrams for system-design interview preparation. Start with the [system-design index](system%20design/Readme.md), which links to all 28 chapters.

Each chapter keeps its notes in `Readme.md` and, where applicable, its diagrams in a sibling `images/` directory. Topics progress from scaling fundamentals and estimation through distributed storage, messaging, monitoring, location-based systems, payments, and a stock exchange.

## Structure

```text
.
├── ai/
│   ├── svg/
│   │   └── *.svg       # AI, retrieval, LLM, and MCP teaching diagrams
│   └── *.md            # AI flashcards
├── java/
│   ├── svg/
│   │   └── *.svg       # Java teaching diagrams
│   └── *.md            # Java flashcards
└── system design/
    ├── 01. Scaling/
    │   ├── images/     # Chapter diagrams
    │   └── Readme.md   # Chapter notes
    ├── ...
    ├── 28. Stock Exchange/
    │   ├── images/
    │   └── Readme.md
    └── Readme.md       # Index of all system-design chapters
```
