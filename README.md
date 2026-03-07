# tools-static-analysis

Static analysis pipeline for .NET, Java, and Python codebases. Scan → visualize → review in browser → point Claude Code at specific repos.

## Prerequisites

- **Python 3.10+** — Core pipeline uses only the standard library
- **Node.js** — Required for companion agent (IDE integration)

The companion agent enables IDE integration buttons (Claude Code, VS Code, Visual Studio). Start it once and keep it running:

### Optional: external analysis tools

For deeper security and quality coverage, install any combination of:

```bash
pip install semgrep bandit detect-secrets radon
```

These are entirely optional. The pipeline works without them and skips any that aren't installed.

## Multi-Language Support

The pipeline supports multiple languages with automatic detection:

- **C#/.NET** — Full analysis of .csproj, .sln, .cs files (dependencies, smells, security)
- **Java** — Maven/Gradle projects with 18 Java-specific detectors (Spring Boot, Jakarta EE)
- **Python** — pip/poetry projects with framework detection (Django, Flask, FastAPI)

Results are integrated into a unified viewer with language filters in Security, Code Quality, and Resilience tabs.

## Quick start

### 0. Download demo datasets (optional)

If you don't have a codebase to analyze, download sample projects:

```bash
# List available datasets (C# and Java projects)
python bootstrap-demo-datasets.py --list

# Download all demo datasets (~300MB total)
python bootstrap-demo-datasets.py --all

# Download only C# datasets (eShop, OrchardCore)
python bootstrap-demo-datasets.py --csharp

# Download only Java datasets (Spring PetClinic, Ta4j, Cassandre)
python bootstrap-demo-datasets.py --java

# Download specific datasets
python bootstrap-demo-datasets.py --csharp eshop --java spring-petclinic
```

Datasets are cloned to your home directory by default. Use `--output` to specify a different location.

**Available datasets:**
- **eShop** - Microsoft's reference .NET eCommerce application (~50MB)
- **OrchardCore** - Modular ASP.NET Core CMS framework (~100MB)
- **Spring PetClinic** - Classic Spring Boot sample application (~5MB)
- **Ta4j** - Java technical analysis library for trading (~10MB)
- **Cassandre** - Spring Boot trading bot framework (~30MB)

### 1. Start the companion agent (required for IDE integration)

**Easy way (recommended):**
```bash
./companion-cli.sh install    # Check dependencies
./companion-cli.sh start       # Start on port 3000
./companion-cli.sh status      # Verify it's running
```

**Manual way:**
```bash
node companion/server.js
```

Keep this running in a separate terminal. It handles all IDE launches (Claude Code, VS Code, Visual Studio).

**Need help?** See [COMPANION_SETUP.md](COMPANION_SETUP.md) for full setup guide.

### 2. Run the analysis pipeline

The simplest way to run everything is via `run.py`:

```bash
# Core pipeline (built-in scanners only)
python run.py --repos /path/to/repos --out output

# Core pipeline + optional external tools (semgrep, bandit, etc.)
python run.py --repos /path/to/repos --out output --tools all

# Custom port
python run.py --repos /path/to/repos --out output --port 8021

# Specific external tools only
python run.py --repos /path/to/repos --out output --tools semgrep,bandit
```

This runs all steps in order and starts a web server on port 8020 (default) with IDE integration (Claude Code, VS Code, Visual Studio, view source buttons).

### Incremental Scanning

Scan repos individually or in batches. Results are combined with folder/repo tagging:

```bash
# Scan multiple repos into one output
python run.py --repos /path/to/repo1,/path/to/repo2,/path/to/repo3 --out output-combined

# Or scan incrementally into the same output directory
python 1_scan_projects.py /path/to/repo1 output-combined
python 2_scan_smells.py /path/to/repo1 output-combined
python 1_scan_projects.py /path/to/repo2 output-combined
python 2_scan_smells.py /path/to/repo2 output-combined
# ... then generate diagrams and viewer once:
python 4_gen_diagrams.py output-combined
python 5_gen_docs.py output-combined
```

The viewer defaults to showing the first repo and remembers your last selection in localStorage.

## Running individual steps

```bash
# 1. Scan .csproj/.xaml/.config — dependencies, refs, data patterns, traceability, UX, NuGet health
python 1_scan_projects.py /path/to/repos output

# 2. Scan .cs source with built-in Python detectors — 18 code smell & security patterns
python 2_scan_smells.py /path/to/repos output --level high

# 3. (Optional) Run external tools — semgrep, bandit, detect-secrets, radon
python 3_external_tools.py /path/to/repos output --tools all

# 4. Generate Mermaid/GraphViz diagrams from graph.json
python 4_gen_diagrams.py output

# 5. Generate viewer.html, markdown docs, and AI context files
python 5_gen_docs.py output
```

**Execution order:**
- Steps 1-2 scan source and can run in parallel
- Step 2 uses **built-in Python-based detectors** (no dependencies)
- Step 3 uses **optional external tools** (requires installation)
- Step 4 needs graph.json from step 1
- Step 5 reads all outputs, so run it last

### Severity levels (`--level`)

The smell scanner supports log-level-style verbosity via `--level critical|high|medium|low` (default: `high`). Each level includes all levels above it.

| Level | What runs | Typical use |
|-------|-----------|-------------|
| `critical` | Security only (hardcoded secrets, SQL injection, insecure deserialization, command injection) | CI gate for must-fix vulnerabilities |
| `high` | Critical + high-severity security (weak crypto, open redirect, XSS, insecure random) + bugs (exception swallowing, sync-over-async) | **Default** — actionable findings without noise |
| `medium` | High + code quality (god methods, deep nesting, long parameter lists) | Sprint planning |
| `low` | All detectors including style (magic numbers, missing null checks, mutable shared state) | Full audit |

The `run.py` pipeline also accepts `--level`:

```bash
python run.py --repos /path/to/repos --out output --level medium
```

### Serve-only mode (`--serve-only`)

If you've already run the pipeline and just want the web server (with IDE integration endpoints for the Claude/VS Code/View buttons), use `--serve-only` to skip the scan steps:

```bash
python run.py --out output --port 8020 --serve-only
```

This starts the custom HTTP server immediately on existing output — no re-scanning. A plain `python -m http.server` serves the viewer but the file action buttons (open in Claude Code, VS Code, Visual Studio, view source) require `run.py`'s server.

### External tools (`--tools`)

Off by default. Pass `--tools all` to run every installed tool, or a comma-separated list for specific ones. Tools not found in PATH are skipped with a warning.

| Tool | What it checks | Category |
|------|---------------|----------|
| `semgrep` | Pattern-based security and correctness rules | security |
| `bandit` | Python security linter | security |
| `detect-secrets` | Hardcoded secrets and credentials | security |
| `radon` | Cyclomatic complexity and maintainability index | quality |

Findings appear in an **External Tools** tab in the viewer, and security-category findings are also merged into the **Security** tab. Output is written to `external-tools.json`.

## Outputs (in `output/`)

| File | Producer | Description |
|------|----------|-------------|
| `graph.json` | 1_scan_projects | Dependency graph (nodes + edges) |
| `project-meta.json` | 1_scan_projects | Per-project metadata (category, targetFramework, nugetFormat) |
| `data-sources.json` | 1_scan_projects | Data access patterns (SQL, HTTP, messaging) |
| `data-flow.json` | 1_scan_projects | Data flow graph with implied dependencies |
| `flow-paths.json` | 1_scan_projects | End-to-end flow paths (Presentation → Data) |
| `field-traceability.json` | 1_scan_projects | XAML → ViewModel → Entity → DB column chains |
| `ux-inconsistencies.json` | 1_scan_projects | MVVM binding issues (broken bindings, orphan VMs) |
| `nuget-health.json` | 1_scan_projects | Version conflicts, legacy formats, framework analysis |
| `refactoring-targets.json` | 2_scan_smells | Code smells, security findings, complexity, Claude Code prompts |
| `resilience-findings.json` | 2_scan_smells | External API calls, retry patterns, Polly policies |
| `external-tools.json` | 3_external_tools | External tool findings (semgrep, bandit, detect-secrets, radon) |
| `java-projects.json` | 1_scan_projects | Java/Maven/Gradle project metadata (if Java repos found) |
| `python-projects.json` | 1_scan_projects | Python project metadata (if Python repos found) |
| `viewer.html` | 5_gen_docs | Interactive browser viewer with all tabs (incl. Security tab) |
| `docs/ai-context/` | 5_gen_docs | Per-project markdown for AI coding agents |

### Viewer Features

The interactive `viewer.html` includes:

- **Folder/Repo Dropdown** — Filter view by individual repo or see aggregate "All Folders" view
  - Defaults to first repo on load
  - Remembers last selection in localStorage
- **Language Filters** — Security, Code Quality, and Resilience tabs include C#/Java/Python filters
- **Diagram Tabs** — Overview, Library, Landscape, Data Flow, Business Layers (per-folder versions)
- **Analysis Tabs** — Security, Resilience, Code Quality with severity/triage/language filtering
- **IDE Integration** — Click-to-open in Claude Code, VS Code, Visual Studio with context

## Tools & Libraries

### Core Dependencies

**Python Standard Library Only** — The core scanner runs without any external packages:
- `xml.etree.ElementTree` — Parse .csproj and .xaml files
- `re` — Pattern matching for code analysis
- `json` — Data serialization
- `csv` — Export tabular data
- `http.server` — Serve viewer with IDE integration endpoints
- `pathlib` / `os` — File system operations

### Visualization Libraries (Embedded)

The generated `viewer.html` embeds CDN-hosted FOSS libraries:
- **[Mermaid.js](https://mermaid.js.org/)** (v11) — Diagram rendering (MIT License)
  - Interactive dependency graphs, flow diagrams, layer diagrams
- **[Prism.js](https://prismjs.com/)** — Syntax highlighting (MIT License)
  - Code snippets in AI context files

### Optional External Tools

Install via pip for extended analysis (all optional):
- **[Semgrep](https://semgrep.dev/)** — Pattern-based security/correctness rules (LGPL 2.1)
- **[Bandit](https://github.com/PyCQA/bandit)** — Python security linter (Apache 2.0)
- **[detect-secrets](https://github.com/Yelp/detect-secrets)** — Credential scanner (Apache 2.0)
- **[Radon](https://github.com/rubik/radon)** — Complexity metrics (MIT License)

### IDE Integration

The viewer includes action buttons that communicate with locally installed tools:
- **[Claude Code](https://claude.ai/download)** — AI coding agent (via `claude-code` CLI)
- **[VS Code](https://code.visualstudio.com/)** — Code editor (via `code` CLI)
- **[Visual Studio 2022](https://visualstudio.microsoft.com/)** — IDE (via `devenv.exe`)
- **[GitHub Copilot](https://github.com/features/copilot)** — AI pair programmer (via `gh copilot` CLI)

All integrations are optional — buttons only appear if tools are installed.

### Companion Agent (Required)

The companion agent handles all IDE integration. Start it before running scans:

```bash
# Start companion on default port 19280 (keep running)
node companion/server.js

# Custom port
node companion/server.js --port 9090

# Custom config
node companion/server.js --config /path/to/config.yaml
```

**Why required:**
- Single process handles all IDE launches (VS Code, Claude Code, Visual Studio, Copilot)
- Works with both local (`run.py`) and hosted viewers
- Stays running across multiple scan runs
- No external dependencies — uses only Node.js built-ins

Both `run.py` and hosted viewers delegate all `/_open` requests to the companion. If it's not running, IDE integration buttons will show an error.

### Output Formats

- **Mermaid (.mmd)** — Text-based diagrams (renders in GitHub, Notion, Confluence)
- **GraphViz (.dot)** — Advanced graph layouts (requires `dot` for rendering)
- **CSV** — Import into Excel, database tools
- **JSON** — Programmatic consumption, CI/CD pipelines
- **Markdown** — Documentation, AI agents

## MCP Server (Model Context Protocol)

The `static_analysis_mcp/` directory contains an MCP server that exposes all static analysis functionality as tools for AI agents like Claude Code. This enables AI-powered code analysis and refactoring workflows directly from chat interfaces.

### Installation

```bash
pip install fastmcp mcp pydantic pyyaml requests python-dateutil
```

### Usage with Claude Desktop

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "static-analysis": {
      "command": "python",
      "args": ["/home/user/dependency-mapper-python/static_analysis_mcp/server.py"]
    }
  }
}
```

Restart Claude Desktop and the tools will appear in the tool palette.

### Available Tools (21 total)

**Scan Management** (5):
- `trigger_scan` - Start new analysis
- `get_scan_summary` - Get statistics
- `list_recent_scans` - List outputs
- `get_scan_status` - Check progress
- `get_viewer_url` - Get web viewer URL

**Query Tools** (7):
- `query_findings` - Search code smells with filters (severity, category, language)
- `get_finding_details` - Get full context with source code
- `query_dependencies` - Get dependency graph
- `find_circular_dependencies` - Detect cycles
- `query_data_flows` - Track data patterns
- `get_project_metrics` - Complexity metrics
- `search_code` - Full-text search

**Fix Workflow** (5):
- `start_fix` - Begin fix workflow via companion agent
- `get_fix_status` - Check progress
- `list_active_fixes` - List in-progress
- `submit_fix` - Create PR/patch
- `cancel_fix` - Abandon workflow

**Configuration** (4):
- `get_config` - Get settings
- `list_prompts` - List AI templates
- `get_prompt_for_finding` - Get tailored prompt
- `update_triage_status` - Mark findings

### Example Workflow

```python
# Claude Code can now:
summary = get_scan_summary("output-eshop-test")
# -> "Found 22 smells across 6 files"

findings = query_findings(
    output_dir="output-eshop-test",
    severity="critical",
    category="security"
)
# -> Returns security findings with file paths and context

fix = start_fix(
    smell_type="sql_injection",
    file_path="src/Api/Controllers/OrderController.cs",
    line=42,
    project="Api",
    smell_description="SQL injection vulnerability"
)
# -> Starts fix workflow with companion agent
```

See `static_analysis_mcp/README.md` for full documentation.
