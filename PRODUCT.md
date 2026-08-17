# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated from the project plan: React + TypeScript for the first runnable workbench, with a future Tauri desktop shell and FastAPI + SQLite backend boundary preserved.

## Users

Primary users are dataset reviewers, domain experts, and dataset quality managers working locally on Windows with large question-answer datasets. They need to inspect records quickly, preserve original data, record manual decisions, coordinate with AI review, and export trusted final datasets.

## Product Purpose

Question Answer Dataset Review Workbench is a local, project-based quality review platform for single-turn QA, multi-turn dialogue, and image QA datasets. Success means a reviewer can create an isolated project, inspect inferred fields, review samples efficiently, run resumable AI review, reconcile human and AI judgments, view statistics, and export final approved data.

## Positioning

The product is not a simple dataset browser: it is an offline-first human + AI review workbench where every project keeps its prompts, review database, AI task state, logs, cache, and exports isolated from every other project.

## Operating Context

The product starts in project management, then moves through import inspection, field confirmation, optional media resource indexing, manual review, AI batch review, statistics, export, and settings. Original datasets remain read-only. Large datasets are paged and must not be loaded into the frontend all at once. Image ZIP files are indexed lazily rather than fully decompressed by default.

## Capabilities and Constraints

Confirmed capabilities include project cards, a new-project wizard, automatic dataset type detection, field inference with confidence, image resource matching, high-speed manual review, configurable shortcuts, autosave, undo, notes, editable derived values without overwriting originals, prompt management, configurable AI providers, resumable AI task progress, human-AI consistency statistics, filtering, search, queue navigation, logs, backups, and export.

The first implementation is a runnable frontend workbench with realistic local state and mocked service boundaries. The backend, SQLite persistence, Tauri packaging, and real AI/provider execution are preserved as explicit integration boundaries rather than hard-coded into the UI.

## Brand Commitments

Product names: Question Answer Dataset Review Workbench and 问答数据集智能审核平台. The interface should be professional, concise, information-dense, comfortable for long review sessions, and should avoid meaningless animation.

## Evidence on Hand

Primary evidence is the project plan at `C:/Users/28595/Downloads/问答数据集智能审核平台完整项目计划书.md`. No real datasets, logos, customer claims, production benchmarks, or API credentials were provided; the implementation must not fabricate commercial proof.

## Product Principles

1. Preserve project isolation and original-data read-only guarantees.
2. Keep review actions fast, reversible, and automatically saved.
3. Make AI review resumable, inspectable, and subordinate to human verification.
4. Keep data and media scalable through paging, indexing, and lazy loading.
5. Keep provider, prompt, parser, and export logic extensible.

## Accessibility & Inclusion

The workbench should support keyboard-heavy operation, readable dense tables, clear status colors with text labels, and long-session visual comfort.
