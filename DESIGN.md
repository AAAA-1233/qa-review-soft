# Design

<!-- impeccable:design-schema 1 -->

## Surface

Primary surface: a local QA dataset review workbench for long-running human + AI audit sessions.

## Visual World

The interface is a dataset quality control room: dense zinc workbench panels, status lamps, queue rails, tabular metrics, and tactile command buttons. It refuses a marketing dashboard shape and keeps the first screen on the real job: inspect a sample, make a decision, see AI state, and move through the queue.

## Mode

Operate. Scanability, keyboard speed, recovery, and clear state outrank decoration.

## Color

Restrained long-session palette:

- `#f4f3ee` paper background
- `#22231f` dark navigation rail
- `#fbfaf6` workbench panels
- `#1c1c19` primary ink
- `#13854b` PASS
- `#b9312d` FAIL
- `#b77a00` SKIP
- `#245ca8` AI and active focus
- `#d99519` progress and brand lamp

Status color is always paired with text labels, never color alone.

## Typography

Use the Windows-native UI stack: `Segoe UI`, `Microsoft YaHei UI`, `system-ui`, `sans-serif`. Data-heavy numerals and keyboard labels use tabular settings or Cascadia/Consolas only where they represent paths, logs, metrics, or shortcuts.

## Components

- Left rail navigation with icon + label on desktop, icon-only on narrow screens.
- Project cards are used only for repeated project entries.
- Manual review mode uses one sample stage plus an instrument stack; AI review mode is named separately for provider and task control.
- Status badges use fixed semantic colors for PASS, FAIL, SKIP, and UNREVIEWED.
- Primary review buttons are large, fixed-format controls with visible shortcut keys.
- Segmented controls filter review queues.
- Terminal-style rows are reserved for paths, logs, and export previews.

## Interaction

Keyboard review is first-class:

- `A` marks PASS
- `D` marks FAIL
- `S` also marks PASS
- `ArrowLeft` and `ArrowRight` move between samples
- `Space` moves forward
- `Ctrl + Z` undoes the last review action

Autosave is visible in the rail footer and backed by local storage in the frontend prototype.

Question and answer fields render LaTeX automatically with KaTeX for `\( ... \)`, `\[ ... \]`, `$...$`, and `$$...$$` delimiters. Invalid formulas fall back to their source text.

Image QA projects show a media viewer with zoom controls and an expanded viewing mode. Non-image datasets do not show media resource inputs or image frames.

Dataset inspection uses flexible field inference across exact names, aliases, and content structure, including multi-turn `messages`, `conversations`, `history`, `turns`, and related dialogue formats.

Multi-turn datasets are rendered as structured conversation turns with system prompts separated from user and assistant messages, rather than flattened into a single question/answer block.

## Responsive Rules

Desktop uses a fixed navigation rail, central sample stage, and right instrument stack. Tablet/narrow desktop collapses to a compact rail. Mobile stacks the rail, project header, sample stage, instruments, queue, and history vertically without horizontal scrolling.

## Current Boundaries

This implementation is a full-stack runnable workbench with React, FastAPI, SQLite, SQLAlchemy, provider presets, dataset inspection, review persistence, AI task records, statistics, and export. Remaining boundaries are WebSocket live progress, native file pickers, Tauri packaging, and production-grade provider credential storage.
