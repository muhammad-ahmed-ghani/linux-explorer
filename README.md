# Linux Explorer

Professional enterprise file management for Linux systems with modern neutral UI, background daemon mode, and comprehensive file operations.

## Installation

```bash
pip install linux-explorer
```

## Usage

Launch the explorer in any directory:

```bash
linux-explorer
```

Alternative commands: `lexplorer`, `lex`

The interface opens automatically in your browser at `http://localhost:7701` (or the next available port in range 7701-7799). The server runs in the background as a daemon, allowing you to close the terminal window.

## Core Features

**File Operations**
Multi-select files with Ctrl/Cmd+Click. Perform batch operations including delete, move, copy, and rename. Context menu available via right-click. Drag and drop for uploads.

**View Modes**
Toggle between grid and list views. Grid supports 4-15 adjustable columns. Search and filter by file type. Sort by name, size, date, or extension.

**Media Support**
View images with zoom, pan, and crop tools. Built-in players for video and audio. Syntax highlighting for code files across 15+ languages. Rendered markdown display.

**Image Editor**
Professional cropping with aspect ratio presets (Free, 1:1, 4:3, 16:9). Mouse wheel zoom and drag to reposition. Save or create edited copies.

**System Monitoring**
Real-time CPU and RAM usage. NVIDIA GPU monitoring when available. Gradient progress indicators.

## Supported Formats

Images: JPG, PNG, GIF, WebP, BMP, SVG
Videos: MP4, WebM, OGG, MOV, MKV
Audio: MP3, WAV, OGG, M4A, FLAC
Code: JS, PY, HTML, CSS, JSON, TS, C, C++, Java, Go, Rust, PHP, Shell, YAML
Documents: TXT, Markdown

## Keyboard Shortcuts

- Delete: Remove selected items
- F2: Rename selected item
- Ctrl/Cmd+A: Select all
- Escape: Close viewer
- Arrow keys: Navigate images

## Design

Built with the Obsidian Glass design system featuring true black backgrounds, glassmorphism effects, and high-contrast violet/cyan accents. Typography combines Playfair Display for headings with Inter for interface elements.

## Technical Details

Pure Python HTTP server backend. Vanilla JavaScript frontend. No heavy frameworks. Optimized for performance even on slow connections. All operations run locally with path validation for security.

## What's New in 0.0.1

Professional neutral color scheme inspired by Windows 11 and macOS Finder. Background daemon mode for Linux systems. Immersive terminal startup with ASCII art branding. Multi-select and bulk file operations. Customizable grid columns (4-15). Context menus and keyboard shortcuts. Enterprise-grade design system.

---

Created by Muhammad Ahmed ([muhammad-ahmed-ghani](https://github.com/muhammad-ahmed-ghani))
