"""Static Analysis MCP Server.

Exposes static analysis functionality through MCP (Model Context Protocol)
for AI-powered code analysis and refactoring workflows.
"""

import sys
import os
import subprocess
import uuid
import logging
import requests
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastmcp import FastMCP

from .config import get_config
from .scan_loader import ScanLoader
from .fix_loader import FixLoader
from .triage_loader import TriageLoader

# Initialize FastMCP server
mcp = FastMCP("static-analysis-mcp")

# Global state
config = None
scan_loader = None
fix_loader = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_companion_not_running_error() -> Dict[str, Any]:
    """Generate structured error response when companion is not running.

    Returns a rich error object with setup instructions, commands, and links.
    """
    quickstart_path = config.project_root / "COMPANION_QUICKSTART.html"
    quickstart_url = f"file://{quickstart_path}" if quickstart_path.exists() else None

    # MCP server download URLs (assumes HTTP mode on port 8080)
    mcp_download_url = "http://localhost:8080/companion/download"

    return {
        "isError": True,
        "error_type": "companion_not_running",
        "title": "Companion Server Not Running",
        "message": "The companion server is required for fix workflows but is not responding.",
        "port": config.companion_port,
        "setup_required": True,
        "download": {
            "package_url": mcp_download_url,
            "format": "zip"
        },
        "quick_fix": {
            "title": "Quick Start (3 steps)",
            "steps": [
                {
                    "number": 1,
                    "title": "Download companion server",
                    "command": mcp_download_url,
                    "note": "Save companion-server.zip to your Downloads folder"
                },
                {
                    "number": 2,
                    "title": "Extract ZIP file",
                    "command": "Right-click companion-server.zip → Extract All → Choose location (e.g., C:\\companion)",
                    "note": "Windows natively extracts .zip files, no tools needed"
                },
                {
                    "number": 3,
                    "title": "Start companion server",
                    "command": "cd C:\\companion\\companion && node server.js",
                    "note": "Or use: npm start (from companion directory)"
                }
            ],
            "verify": {
                "title": "Verify it's running",
                "command": "curl http://localhost:19280/_ping",
                "expected": '{"status":"ok"}'
            }
        },
        "resources": {
            "quickstart_html": quickstart_url,
            "setup_guide": str(config.project_root / "COMPANION_SETUP.md"),
            "download_url": mcp_download_url
        },
        "troubleshooting": [
            {
                "issue": "Port already in use",
                "solution": "node server.js --port 19281"
            },
            {
                "issue": "Can't find node command",
                "solution": "Install Node.js from https://nodejs.org"
            },
            {
                "issue": "Check if running",
                "solution": "curl http://localhost:19280/_ping"
            }
        ],
        "call_to_action": {
            "primary": {
                "text": "Open Quick Start Guide",
                "action": "open_url",
                "url": quickstart_url
            },
            "secondary": {
                "text": "Download Companion Server",
                "action": "open_url",
                "url": mcp_download_url
            }
        }
    }


# =============================================================================
# Scan Management Tools (5 tools)
# =============================================================================

@mcp.tool()
def trigger_scan(
    repos: str,
    output_dir: str,
    level: str = "high",
    tools: str = "none"
) -> Dict[str, Any]:
    """Start a new analysis scan.

    Args:
        repos: Path to repository or solution to scan
        output_dir: Output directory for scan results
        level: Analysis level (critical|high|medium|low)
        tools: External tools to run (none|semgrep|bandit|all)

    Returns:
        Scan metadata with scan_id and status
    """
    scan_id = str(uuid.uuid4())

    # Build command
    cmd = [
        sys.executable,
        str(Path(__file__).parent.parent / 'run.py'),
        '--repos', repos,
        '--out', output_dir,
        '--level', level,
        '--tools', tools
    ]

    try:
        # Start subprocess (detached)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )

        # Store scan metadata
        scan_meta = {
            'scan_id': scan_id,
            'status': 'running',
            'pid': proc.pid,
            'output_dir': output_dir,
            'repos': repos,
            'start_time': datetime.now().isoformat()
        }

        logger.info(f"Started scan {scan_id} with PID {proc.pid}")
        return scan_meta

    except Exception as e:
        logger.error(f"Failed to start scan: {e}")
        return {
            "isError": True,
            "message": f"Failed to start scan: {str(e)}"
        }


@mcp.tool()
def get_scan_summary(output_dir: str) -> Dict[str, Any]:
    """Get summary statistics for a completed scan.

    Args:
        output_dir: Path to scan output directory

    Returns:
        Summary with file counts, smell types, and severity breakdown
    """
    try:
        loader = ScanLoader(output_dir)
        if not loader.exists():
            return {
                "isError": True,
                "message": f"Output directory not found: {output_dir}"
            }

        return loader.get_summary()

    except Exception as e:
        logger.error(f"Failed to get scan summary: {e}")
        return {
            "isError": True,
            "message": f"Failed to get scan summary: {str(e)}"
        }


@mcp.tool()
def list_recent_scans(project_root: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """List recent scan output directories.

    Args:
        project_root: Project root directory (defaults to config)
        limit: Maximum number of scans to return

    Returns:
        List of scan output directories with metadata
    """
    try:
        if project_root is None:
            project_root = str(config.project_root)

        root = Path(project_root)
        output_dirs = []

        # Find all output-* directories
        for item in root.iterdir():
            if item.is_dir() and item.name.startswith('output-'):
                refactoring_file = item / 'refactoring-targets.json'
                if refactoring_file.exists():
                    mtime = refactoring_file.stat().st_mtime
                    output_dirs.append({
                        'path': str(item),
                        'name': item.name,
                        'modified': datetime.fromtimestamp(mtime).isoformat()
                    })

        # Sort by modification time (newest first)
        output_dirs.sort(key=lambda x: x['modified'], reverse=True)

        return output_dirs[:limit]

    except Exception as e:
        logger.error(f"Failed to list scans: {e}")
        return []


@mcp.tool()
def get_scan_status(scan_id: str) -> Dict[str, Any]:
    """Check status of a running scan.

    Args:
        scan_id: Scan identifier returned by trigger_scan

    Returns:
        Scan status information
    """
    # Note: In a production system, you'd persist scan metadata
    # For now, return a simple status check
    return {
        "scan_id": scan_id,
        "status": "unknown",
        "message": "Scan status tracking not yet implemented. Use get_scan_summary to check results."
    }


@mcp.tool()
def get_viewer_url(output_dir: str, port: int = 8000) -> Dict[str, Any]:
    """Get URL for web viewer of scan results.

    Args:
        output_dir: Path to scan output directory
        port: HTTP server port

    Returns:
        Viewer URL and availability info
    """
    try:
        loader = ScanLoader(output_dir)
        if not loader.exists():
            return {
                "isError": True,
                "message": f"Output directory not found: {output_dir}"
            }

        viewer_file = Path(output_dir) / "docs" / "viewer.html"
        if not viewer_file.exists():
            return {
                "url": "",
                "output_dir": output_dir,
                "available": False,
                "message": "Viewer not generated. Run 5_gen_docs.py first."
            }

        return {
            "url": f"http://localhost:{port}/{output_dir}/docs/viewer.html",
            "output_dir": output_dir,
            "available": True,
            "message": f"Start run.py to serve the viewer on port {port}"
        }

    except Exception as e:
        logger.error(f"Failed to get viewer URL: {e}")
        return {
            "isError": True,
            "message": f"Failed to get viewer URL: {str(e)}"
        }


# =============================================================================
# Query Tools (7 tools)
# =============================================================================

@mcp.tool()
def query_findings(
    output_dir: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
    project: Optional[str] = None,
    smell_type: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Search code smells and findings with filters.

    Args:
        output_dir: Path to scan output directory
        severity: Filter by severity (critical|high|medium|low)
        category: Filter by category (security|bug|quality|style)
        language: Filter by language (csharp|java|python)
        project: Filter by project name
        smell_type: Filter by smell type
        limit: Maximum results to return

    Returns:
        List of findings with context
    """
    try:
        loader = ScanLoader(output_dir)
        if not loader.exists():
            return []

        filters = {}
        if severity:
            filters['severity'] = severity
        if category:
            filters['category'] = category
        if language:
            filters['language'] = language
        if project:
            filters['project'] = project
        if smell_type:
            filters['smell_type'] = smell_type

        findings = loader.get_all_findings(filters)
        return findings[:limit]

    except Exception as e:
        logger.error(f"Failed to query findings: {e}")
        return []


@mcp.tool()
def get_finding_details(
    output_dir: str,
    project: str,
    file_path: str,
    line: int
) -> Dict[str, Any]:
    """Get full context for a specific finding.

    Args:
        output_dir: Path to scan output directory
        project: Project name
        file_path: File path
        line: Line number

    Returns:
        Finding details with source code context
    """
    try:
        loader = ScanLoader(output_dir)
        finding = loader.get_finding_at(project, file_path, line)

        if not finding:
            return {
                "isError": True,
                "message": "Finding not found"
            }

        # Add surrounding code context
        source_code = loader.get_file_content(file_path, line - 5, line + 5)
        finding['source_code'] = source_code

        return finding

    except Exception as e:
        logger.error(f"Failed to get finding details: {e}")
        return {
            "isError": True,
            "message": f"Failed to get finding details: {str(e)}"
        }


@mcp.tool()
def query_dependencies(
    output_dir: str,
    project: Optional[str] = None,
    include_transitive: bool = False
) -> Dict[str, Any]:
    """Get project dependency graph.

    Args:
        output_dir: Path to scan output directory
        project: Optional project name to filter to
        include_transitive: Include transitive dependencies

    Returns:
        Dependency graph with nodes and edges
    """
    try:
        loader = ScanLoader(output_dir)
        graph = loader.get_dependency_graph()

        if 'isError' in graph:
            return graph

        if project:
            # Filter to specific project
            graph = loader.filter_graph(graph, project, include_transitive)

        return graph

    except Exception as e:
        logger.error(f"Failed to query dependencies: {e}")
        return {
            "isError": True,
            "message": f"Failed to query dependencies: {str(e)}"
        }


@mcp.tool()
def find_circular_dependencies(output_dir: str) -> List[Dict[str, Any]]:
    """Detect circular dependencies in project graph.

    Args:
        output_dir: Path to scan output directory

    Returns:
        List of circular dependency cycles with severity
    """
    try:
        loader = ScanLoader(output_dir)
        cycles = loader.find_circular_dependencies()
        return cycles

    except Exception as e:
        logger.error(f"Failed to find circular dependencies: {e}")
        return []


@mcp.tool()
def query_data_flows(
    output_dir: str,
    project: Optional[str] = None,
    flow_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get data flow analysis results.

    Args:
        output_dir: Path to scan output directory
        project: Optional project filter
        flow_type: Optional flow type filter

    Returns:
        List of data flows
    """
    try:
        loader = ScanLoader(output_dir)
        filters = {}
        if project:
            filters['project'] = project
        if flow_type:
            filters['flow_type'] = flow_type

        flows = loader.get_data_flows(filters)
        return flows

    except Exception as e:
        logger.error(f"Failed to query data flows: {e}")
        return []


@mcp.tool()
def get_project_metrics(
    output_dir: str,
    project: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get complexity metrics for projects.

    Args:
        output_dir: Path to scan output directory
        project: Optional project name filter

    Returns:
        List of project metrics (complexity, smells, etc.)
    """
    try:
        loader = ScanLoader(output_dir)
        metrics = loader.get_project_metrics(project)
        return metrics

    except Exception as e:
        logger.error(f"Failed to get project metrics: {e}")
        return []


@mcp.tool()
def search_code(
    output_dir: str,
    query: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Full-text search across finding descriptions and context.

    Args:
        output_dir: Path to scan output directory
        query: Search query string
        limit: Maximum results to return

    Returns:
        List of matching findings
    """
    try:
        loader = ScanLoader(output_dir)
        results = loader.search_code(query, limit)
        return results

    except Exception as e:
        logger.error(f"Failed to search code: {e}")
        return []


# =============================================================================
# Fix Workflow Tools (5 tools)
# =============================================================================

@mcp.tool()
def start_fix(
    smell_type: str,
    file_path: str,
    line: int,
    project: str,
    smell_description: str,
    editor: str = "claude"
) -> Dict[str, Any]:
    """Begin fix workflow via companion agent.

    Args:
        smell_type: Type of code smell
        file_path: Path to file with smell
        line: Line number
        project: Project name
        smell_description: Description of the smell
        editor: Editor to use (claude|opencode|copilot)

    Returns:
        Fix workflow state with fix_id
    """
    try:
        # Delegate to companion agent
        params = {
            'smell_type': smell_type,
            'path': file_path,
            'line': line,
            'project': project,
            'smell': smell_description,
            'editor': editor
        }

        companion_url = f'http://localhost:{config.companion_port}/_fix/start'
        response = requests.get(companion_url, params=params, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "isError": True,
                "message": f"Companion agent error: {response.text}"
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to start fix: {e}")
        return get_companion_not_running_error()


@mcp.tool()
def get_fix_status(fix_id: str) -> Dict[str, Any]:
    """Get fix workflow status.

    Args:
        fix_id: Fix identifier from start_fix

    Returns:
        Fix state with status and progress
    """
    try:
        fix = fix_loader.get_fix(fix_id)

        if not fix:
            return {
                "isError": True,
                "message": f"Fix not found: {fix_id}"
            }

        return {
            "fix_id": fix_id,
            **fix
        }

    except Exception as e:
        logger.error(f"Failed to get fix status: {e}")
        return {
            "isError": True,
            "message": f"Failed to get fix status: {str(e)}"
        }


@mcp.tool()
def list_active_fixes(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List in-progress fix workflows.

    Args:
        status: Optional status filter (checkout|branching|fixing|review|building|testing|submitting|done)

    Returns:
        List of fix workflows
    """
    try:
        if status:
            fixes = fix_loader.get_all_fixes(status)
        else:
            fixes = fix_loader.list_active_fixes()

        return fixes

    except Exception as e:
        logger.error(f"Failed to list fixes: {e}")
        return []


@mcp.tool()
def submit_fix(fix_id: str, message: Optional[str] = None) -> Dict[str, Any]:
    """Submit fix for review (create PR or patch).

    Args:
        fix_id: Fix identifier
        message: Optional commit/PR message

    Returns:
        Submission result with PR URL or patch path
    """
    try:
        # Delegate to companion agent
        params = {'fix_id': fix_id}
        if message:
            params['message'] = message

        companion_url = f'http://localhost:{config.companion_port}/_fix/submit'
        response = requests.get(companion_url, params=params, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "isError": True,
                "message": f"Companion agent error: {response.text}"
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to submit fix: {e}")
        return get_companion_not_running_error()


@mcp.tool()
def cancel_fix(fix_id: str) -> Dict[str, Any]:
    """Cancel/abandon a fix workflow.

    Args:
        fix_id: Fix identifier

    Returns:
        Cancellation result
    """
    try:
        # Delegate to companion agent
        params = {'fix_id': fix_id}

        companion_url = f'http://localhost:{config.companion_port}/_fix/cancel'
        response = requests.get(companion_url, params=params, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "isError": True,
                "message": f"Companion agent error: {response.text}"
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to cancel fix: {e}")
        return get_companion_not_running_error()


# =============================================================================
# Configuration Tools (4 tools)
# =============================================================================

@mcp.tool()
def get_server_config() -> Dict[str, Any]:
    """Get current configuration settings.

    Returns:
        Configuration dictionary
    """
    try:
        return {
            "project_root": str(config.project_root),
            "output_dir": config.output_dir,
            "companion_port": config.companion_port,
            "server_port": config.server_port,
            "claude_code_path": config.claude_code_path,
            "copilot_enabled": config.copilot_enabled,
            "copilot_model": config.copilot_model,
            "enable_wsl_tools": config.enable_wsl_tools
        }

    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        return {
            "isError": True,
            "message": f"Failed to get config: {str(e)}"
        }


@mcp.tool()
def list_prompts() -> List[Dict[str, Any]]:
    """List available AI prompt templates.

    Returns:
        List of prompt templates with names and descriptions
    """
    try:
        prompts_dir = config.get_prompts_dir()
        default_prompts_file = prompts_dir / "default_prompts.yaml"

        if not default_prompts_file.exists():
            return []

        with open(default_prompts_file, 'r', encoding='utf-8') as f:
            prompts_data = yaml.safe_load(f) or {}

        prompts = []
        for name, data in prompts_data.items():
            if isinstance(data, dict):
                prompts.append({
                    "name": name,
                    "description": data.get('description', ''),
                    "template": data.get('template', ''),
                    "variables": data.get('variables', [])
                })

        return prompts

    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        return []


@mcp.tool()
def get_prompt_for_finding(
    smell_type: str,
    file_path: str,
    context: str
) -> Dict[str, Any]:
    """Get tailored AI prompt for a specific finding.

    Args:
        smell_type: Type of code smell
        file_path: Path to file
        context: Code context

    Returns:
        Formatted prompt for AI tool
    """
    try:
        prompts = list_prompts()

        # Find matching prompt template
        template = None
        for prompt in prompts:
            if smell_type.lower() in prompt['name'].lower():
                template = prompt['template']
                break

        if not template:
            # Use generic template
            template = config.claude_prompt

        # Format prompt with context
        prompt_text = template.format(
            smell_type=smell_type,
            file_path=file_path,
            context=context
        ) if '{' in template else template

        return {
            "prompt": prompt_text,
            "smell_type": smell_type,
            "template_used": "specific" if template != config.claude_prompt else "generic"
        }

    except Exception as e:
        logger.error(f"Failed to get prompt: {e}")
        return {
            "isError": True,
            "message": f"Failed to get prompt: {str(e)}"
        }


@mcp.tool()
def update_triage_status(
    output_dir: str,
    project: str,
    file_path: str,
    line: int,
    status: str,
    assigned_to: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Update triage status for a finding.

    Args:
        output_dir: Path to scan output directory
        project: Project name
        file_path: File path
        line: Line number
        status: Triage status (open|in_progress|resolved|wont_fix|false_positive)
        assigned_to: Optional assignee
        notes: Optional notes

    Returns:
        Update result
    """
    try:
        triage_file = config.get_triage_file(output_dir)
        triage_loader = TriageLoader(triage_file)

        success = triage_loader.update_triage(
            project, file_path, line, status, assigned_to, notes
        )

        if success:
            return {
                "success": True,
                "project": project,
                "file_path": file_path,
                "line": line,
                "status": status
            }
        else:
            return {
                "isError": True,
                "message": "Failed to update triage status"
            }

    except Exception as e:
        logger.error(f"Failed to update triage: {e}")
        return {
            "isError": True,
            "message": f"Failed to update triage: {str(e)}"
        }


# =============================================================================
# Intelligent Fix Recommendation Tools (7 tools)
# =============================================================================

@mcp.tool()
def recommend_fixes_priority(
    output_dir: str,
    project: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get prioritized list of fixes to work on first.

    Returns findings ranked by:
    - Severity (critical > high > medium > low)
    - Security issues weighted higher
    - Blast radius (dependencies affected)
    - Effort estimate (low effort = higher priority)
    - Triage status (in_progress on top, resolved filtered out)

    Quick wins: high severity + low effort
    Security first: security issues weighted 1.5x

    Args:
        output_dir: Scan output directory
        project: Optional project filter
        category: Optional category filter (security, bug, quality)
        limit: Max results

    Returns:
        List of findings with priority scores and recommendations
    """
    try:
        loader = ScanLoader(output_dir)
        if not loader.exists():
            return []

        filters = {}
        if project:
            filters['project'] = project
        if category:
            filters['category'] = category

        findings = loader.get_prioritized_findings(filters, limit)

        # Enhance with batch fix opportunities
        for f in findings:
            # Count similar smells for batch fix opportunity
            similar_results = loader.find_similar_smells(f['smell_type'], group_by="pattern", limit=100)
            if isinstance(similar_results, list) and len(similar_results) > 0:
                # If grouped by pattern, sum all instances
                total_similar = sum(p.get('count', 0) for p in similar_results if isinstance(p, dict))
            else:
                total_similar = 0

            f['similar_count'] = total_similar
            f['batch_fix_opportunity'] = total_similar > 3

            # Generate human-readable reason
            reasons = []
            if f.get('severity') == 'critical':
                reasons.append("Critical severity")
            if f.get('category') == 'security':
                reasons.append("Security vulnerability")
            if f.get('blast_radius') == 'high':
                reasons.append(f"High blast radius")
            if f.get('effort_estimate') in ['trivial', 'low']:
                reasons.append("Quick fix")
            if f.get('batch_fix_opportunity'):
                reasons.append(f"{total_similar} similar instances")

            f['reason'] = ', '.join(reasons) if reasons else "Standard priority"

        return findings

    except Exception as e:
        logger.error(f"Failed to get fix recommendations: {e}")
        return []


@mcp.tool()
def get_rich_fix_context(
    output_dir: str,
    project: str,
    file_path: str,
    line: int
) -> Dict[str, Any]:
    """Get comprehensive context for fixing a finding.

    Provides everything an AI agent needs:
    - Source code with context (±10 lines)
    - Related issues in same file
    - Similar patterns in codebase
    - Dependency/blast radius analysis
    - Complexity metrics
    - Test coverage info
    - Fix templates and guidance
    - Triage status

    This is the foundation for intelligent fix workflows.

    Args:
        output_dir: Scan output directory
        project: Project name
        file_path: File path
        line: Line number

    Returns:
        Rich context dictionary with all fix information
    """
    try:
        loader = ScanLoader(output_dir)
        context = loader.get_rich_context(project, file_path, line)
        return context

    except Exception as e:
        logger.error(f"Failed to get rich context: {e}")
        return {
            "isError": True,
            "message": f"Failed to get context: {str(e)}"
        }


@mcp.tool()
def find_similar_smells(
    output_dir: str,
    smell_type: str,
    group_by: str = "pattern",
    limit: int = 50
) -> Dict[str, Any]:
    """Find all instances of a smell type for batch fixing.

    Identifies patterns across the codebase to enable:
    - Batch fixing similar issues
    - Consistent fix approaches
    - Learning from repeated patterns

    Args:
        output_dir: Scan output directory
        smell_type: Type of smell to find
        group_by: Group by "pattern", "file", or "project"
        limit: Max results per group

    Returns:
        Grouped instances with batch fix opportunities
    """
    try:
        loader = ScanLoader(output_dir)
        results = loader.find_similar_smells(smell_type, group_by, limit)

        # Calculate totals
        if isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict):
            if 'count' in results[0]:
                # Grouped results
                total_instances = sum(r.get('count', 0) for r in results)
            else:
                # Flat list
                total_instances = len(results)
        else:
            total_instances = 0

        return {
            "smell_type": smell_type,
            "total_instances": total_instances,
            "grouped_by": group_by,
            "groups": results
        }

    except Exception as e:
        logger.error(f"Failed to find similar smells: {e}")
        return {
            "isError": True,
            "message": f"Failed to find patterns: {str(e)}"
        }


@mcp.tool()
def estimate_fix_effort(
    output_dir: str,
    project: str,
    file_path: str,
    line: int
) -> Dict[str, Any]:
    """Estimate effort required to fix a finding.

    Considers:
    - Cyclomatic complexity
    - Nesting depth
    - Number of dependencies
    - Test coverage
    - Smell type characteristics

    Returns estimates:
    - trivial: <15 min (simple changes like renaming)
    - low: 15-30 min (straightforward fixes)
    - medium: 30-60 min (requires careful changes)
    - high: 60+ min (major refactoring needed)

    Args:
        output_dir: Scan output directory
        project: Project name
        file_path: File path
        line: Line number

    Returns:
        Effort estimate with factors and recommendation
    """
    try:
        loader = ScanLoader(output_dir)
        finding = loader.get_finding_at(project, file_path, line)

        if not finding:
            return {"isError": True, "message": "Finding not found"}

        estimate = loader._estimate_effort(finding)

        # Get contextual factors
        context = loader.get_rich_context(project, file_path, line)

        factors = {
            "severity": finding.get('severity', 'low'),
            "category": finding.get('category', 'quality'),
            "smell_type": finding.get('smell_type', ''),
            "has_tests": context.get('test_coverage', {}).get('project_has_tests', False),
            "blast_radius": context.get('dependencies', {}).get('blast_radius', 'low'),
            "related_smells": len(context.get('related_findings', []))
        }

        # Generate recommendation
        recommendations = []
        if not factors['has_tests']:
            recommendations.append("Write tests first")
        if factors['blast_radius'] == 'high':
            recommendations.append("Review dependent modules")
        if factors['related_smells'] > 2:
            recommendations.append(f"Consider batch-fixing {factors['related_smells']} related issues")

        recommendation = '; '.join(recommendations) if recommendations else f"{estimate.title()} effort"

        return {
            "file_path": file_path,
            "line": line,
            "effort_estimate": estimate,
            "factors": factors,
            "recommendation": recommendation,
            "estimated_minutes": {
                'trivial': '<15',
                'low': '15-30',
                'medium': '30-60',
                'high': '60+'
            }.get(estimate, '30-60')
        }

    except Exception as e:
        logger.error(f"Failed to estimate effort: {e}")
        return {
            "isError": True,
            "message": f"Failed to estimate: {str(e)}"
        }


@mcp.tool()
def get_fix_template(
    smell_type: str,
    language: str = "csharp"
) -> Dict[str, Any]:
    """Get pre-built fix pattern for a smell type.

    Provides guidance from prompt templates.

    Args:
        smell_type: Type of smell
        language: Programming language (csharp, java, python)

    Returns:
        Fix template with guidance and explanation
    """
    try:
        prompts = list_prompts()

        # Find matching prompt template
        template = None
        for p in prompts:
            # Match smell_type to prompt name
            if smell_type.lower() in p['name'].lower() or p['name'].lower() in smell_type.lower():
                template = p
                break

        if not template:
            return {
                "isError": True,
                "message": f"No template found for {smell_type}"
            }

        return {
            "smell_type": smell_type,
            "language": language,
            "fix_template": {
                "name": template.get('name', ''),
                "explanation": template.get('description', ''),
                "guidance": template.get('template', ''),
                "variables": template.get('variables', []),
                "language_specific": language in str(template.get('variables', []))
            }
        }

    except Exception as e:
        logger.error(f"Failed to get fix template: {e}")
        return {
            "isError": True,
            "message": f"Failed to get template: {str(e)}"
        }


@mcp.tool()
def get_educational_resources(
    smell_type: str,
    language: str = "csharp"
) -> Dict[str, Any]:
    """Get educational videos and documentation for a smell type.

    Provides YouTube explainers and official docs to help developers
    understand the issue before fixing it. Curated resources include:
    - Top YouTube tutorials (100K+ views)
    - Official documentation (Microsoft, OWASP, etc.)
    - Related topics and learning paths

    Perfect for developers who:
    - Are not 100% confident about the fix
    - Want to learn the underlying concepts
    - Need examples and best practices

    Args:
        smell_type: Type of code smell
        language: Programming language for language-specific resources

    Returns:
        Educational resources with videos, docs, and related topics
    """
    try:
        from .educational_resources import get_educational_resources as get_resources

        resources = get_resources(smell_type)

        return resources

    except Exception as e:
        logger.error(f"Failed to get educational resources: {e}")
        return {
            "isError": True,
            "message": f"Failed to get resources: {str(e)}"
        }


@mcp.tool()
def start_fix_with_context(
    smell_type: str,
    file_path: str,
    line: int,
    project: str,
    output_dir: str,
    editor: str = "claude",
    include_similar: bool = True
) -> Dict[str, Any]:
    """Start fix workflow with rich context assembly.

    Enhanced version of start_fix that:
    1. Assembles rich context (dependencies, similar patterns, metrics)
    2. Gets fix template and guidance
    3. Gets educational resources for learning support
    4. Builds comprehensive system prompt WITH CONFIDENCE CHECK
    5. Updates triage to in_progress
    6. Launches editor with full context

    The confidence check prompts the AI agent to:
    - Assess if they understand the smell type
    - Review educational resources if not 100% confident
    - Learn before proposing fixes
    - Provide better, more informed solutions

    This prevents AI agents from guessing and encourages learning.

    Args:
        smell_type: Type of code smell
        file_path: Path to file
        line: Line number
        project: Project name
        output_dir: Scan output directory
        editor: Editor to use (claude|opencode|copilot)
        include_similar: Include similar patterns in context

    Returns:
        Fix workflow state with context summary and educational resources
    """
    try:
        # 1. Get rich context
        context_result = get_rich_fix_context(output_dir, project, file_path, line)

        if context_result.get('isError'):
            return context_result

        # 2. Get fix template
        language = context_result.get('fix_guidance', {}).get('language', 'csharp')
        template_result = get_fix_template(smell_type, language)

        # 3. Get educational resources
        edu_resources = get_educational_resources(smell_type, language)

        # 4. Build enhanced prompt with confidence check
        finding = context_result['finding']
        source = context_result['source_code']

        # Format educational videos section
        videos_section = ""
        if edu_resources.get('educational_videos'):
            videos_section = "\n\nRecommended Videos:\n"
            for i, video in enumerate(edu_resources['educational_videos'][:2], 1):
                videos_section += f'{i}. "{video["title"]}" - {video["channel"]} ({video.get("duration", "N/A")})\n'
                videos_section += f'   {video["url"]}\n'

        # Format documentation section
        docs_section = ""
        if edu_resources.get('documentation_links'):
            docs_section = "\n\nDocumentation:\n"
            for doc in edu_resources['documentation_links'][:2]:
                docs_section += f'- {doc}\n'

        enhanced_description = f"""You are fixing a {finding['severity']} {finding['category']} issue: {smell_type}

## Finding Details
File: {file_path}:{line}
Severity: {finding['severity']} | Category: {finding['category']}
Context: {finding.get('context', 'N/A')}

## Impact Analysis
- Complexity: {context_result['complexity'].get('cyclomatic', 0)} cyclomatic complexity
- Test Coverage: {"Yes" if context_result.get('test_coverage', {}).get('project_has_tests') else "No tests - write one first"}
- Blast Radius: {context_result['dependencies'].get('blast_radius', 'low')}

## Related Issues
{len(context_result.get('related_findings', []))} other smells in this file

## Fix Strategy
{template_result.get('fix_template', {}).get('explanation', 'Review code carefully and apply best practices')}

## Educational Resources (if you need them)
If you're not 100% confident fixing this {smell_type} issue, these resources can help:
{videos_section}
{docs_section}

## Source Code
{source.get('full', '')}

CONFIDENCE CHECK:
Before proposing a fix, please assess:
- Are you 100% confident in understanding this {smell_type} issue?
- Do you know the correct fix pattern for {language}?

If NOT 100% confident:
1. Say "I recommend reviewing the educational resources first"
2. Summarize what you learned from the videos/docs
3. Then propose the fix with that context

If 100% confident:
1. Propose the fix directly
2. Explain why this approach prevents {smell_type}

Please respond with your confidence level + analysis + proposed fix."""

        # 5. Update triage status
        update_triage_status(
            output_dir=output_dir,
            project=project,
            file_path=file_path,
            line=line,
            status="in_progress",
            notes=f"Started fix workflow with {editor}"
        )

        # 6. Call companion agent
        fix_result = start_fix(
            smell_type=smell_type,
            file_path=file_path,
            line=line,
            project=project,
            smell_description=enhanced_description,
            editor=editor
        )

        # 7. Enhance response with context summary
        if not fix_result.get('isError'):
            fix_result['context_provided'] = {
                'source_lines': len(source.get('full', '').split('\n')),
                'related_findings': len(context_result.get('related_findings', [])),
                'similar_patterns': len(context_result.get('similar_patterns', [])),
                'fix_template': not template_result.get('isError'),
                'educational_resources': len(edu_resources.get('educational_videos', [])),
                'triage_updated': True
            }

            fix_result['educational_resources'] = {
                'videos': edu_resources.get('educational_videos', [])[:2],
                'docs': edu_resources.get('documentation_links', [])[:2],
                'has_resources': edu_resources.get('has_resources', False)
            }

            fix_result['confidence_prompt'] = "Agent will assess confidence before proposing fix"

            if context_result.get('related_findings'):
                fix_result['recommendation'] = f"Consider batch-fixing {len(context_result['related_findings'])} other issues in same file"

        return fix_result

    except Exception as e:
        logger.error(f"Failed to start fix with context: {e}")
        return {
            "isError": True,
            "message": f"Failed to start fix: {str(e)}"
        }


# =============================================================================
# Health Check & Setup Tools (2 tools)
# =============================================================================

@mcp.tool()
def check_companion_health(port: Optional[int] = None) -> Dict[str, Any]:
    """Check if companion server is running and healthy.

    Proactive health check to verify companion server is accessible.
    Returns setup instructions if not running.

    Args:
        port: Optional port to check (defaults to configured port)

    Returns:
        Health status with setup instructions if needed
    """
    check_port = port or config.companion_port

    try:
        response = requests.get(
            f'http://localhost:{check_port}/_ping',
            timeout=2
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "healthy": True,
                "status": "running",
                "port": check_port,
                "response": data,
                "message": f"Companion server is healthy on port {check_port}"
            }
        else:
            return {
                "healthy": False,
                "status": "error",
                "port": check_port,
                "http_status": response.status_code,
                "message": f"Companion responded with status {response.status_code}"
            }

    except requests.exceptions.RequestException:
        # Companion not running - return setup instructions
        error_response = get_companion_not_running_error()
        error_response["healthy"] = False
        error_response["status"] = "not_running"
        return error_response


@mcp.tool()
def get_companion_setup_info() -> Dict[str, Any]:
    """Get companion server setup information.

    Returns comprehensive setup instructions, links, and commands
    for installing and starting the companion server.

    Use this to show setup instructions to users.

    Returns:
        Setup information with commands and links
    """
    quickstart_path = config.project_root / "COMPANION_QUICKSTART.html"
    setup_guide_path = config.project_root / "COMPANION_SETUP.md"

    return {
        "companion": {
            "name": "Static Analysis Companion Server",
            "version": "1.0.0",
            "default_port": 3000,
            "current_port": config.companion_port
        },
        "prerequisites": {
            "required": [
                {
                    "name": "Node.js",
                    "version": "16+",
                    "check_command": "node --version",
                    "install_instructions": {
                        "ubuntu": "sudo apt install nodejs npm",
                        "macos": "brew install node",
                        "windows": "Download from https://nodejs.org"
                    }
                }
            ]
        },
        "quick_start": {
            "steps": [
                {
                    "number": 1,
                    "title": "Check Node.js",
                    "command": "node --version",
                    "expected": "v16.x.x or higher"
                },
                {
                    "number": 2,
                    "title": "Install companion",
                    "command": f"cd {config.project_root} && ./companion-cli.sh install",
                    "expected": "✓ Installation check complete!"
                },
                {
                    "number": 3,
                    "title": "Start companion",
                    "command": "./companion-cli.sh start",
                    "expected": "✓ Companion started"
                },
                {
                    "number": 4,
                    "title": "Verify running",
                    "command": "./companion-cli.sh test",
                    "expected": "✓ Health check passed"
                }
            ]
        },
        "cli_commands": {
            "install": "./companion-cli.sh install",
            "start": "./companion-cli.sh start",
            "stop": "./companion-cli.sh stop",
            "restart": "./companion-cli.sh restart",
            "status": "./companion-cli.sh status",
            "test": "./companion-cli.sh test",
            "logs": "./companion-cli.sh logs",
            "help": "./companion-cli.sh help"
        },
        "resources": {
            "quickstart_html": {
                "path": str(quickstart_path),
                "url": f"file://{quickstart_path}" if quickstart_path.exists() else None,
                "description": "Interactive quick start guide (open in browser)",
                "exists": quickstart_path.exists()
            },
            "setup_guide": {
                "path": str(setup_guide_path),
                "description": "Comprehensive setup guide (350+ lines)",
                "exists": setup_guide_path.exists()
            },
            "cli_script": {
                "path": str(config.project_root / "companion-cli.sh"),
                "description": "Management CLI for companion server",
                "exists": (config.project_root / "companion-cli.sh").exists()
            }
        },
        "troubleshooting": {
            "port_in_use": {
                "issue": "Port 3000 already in use",
                "solution": "./companion-cli.sh start 19280",
                "description": "Start on alternate port"
            },
            "check_status": {
                "issue": "Not sure if running",
                "solution": "./companion-cli.sh status",
                "description": "Check current status"
            },
            "view_logs": {
                "issue": "Companion not working",
                "solution": "./companion-cli.sh logs",
                "description": "View recent logs for errors"
            },
            "restart": {
                "issue": "Companion not responding",
                "solution": "./companion-cli.sh restart",
                "description": "Restart the companion server"
            }
        },
        "next_steps": [
            "Open quick start guide in browser",
            "Run install check command",
            "Start companion server",
            "Verify with health check"
        ]
    }


# =============================================================================
# Server Initialization
# =============================================================================

def initialize_server():
    """Initialize server on startup."""
    global config, scan_loader, fix_loader

    from .config import get_config as load_config
    config = load_config()
    fix_loader = FixLoader(str(config.project_root))

    logger.info("Static Analysis MCP server initialized")
    logger.info(f"Project root: {config.project_root}")
    logger.info(f"Default output dir: {config.default_output_dir}")
    logger.info(f"Companion port: {config.companion_port}")


def main():
    """Entry point for MCP server."""
    initialize_server()

    # Auto-detect transport
    if "--http" in sys.argv:
        port_idx = sys.argv.index("--http") + 1
        port = int(sys.argv[port_idx]) if port_idx < len(sys.argv) else 8080
        logger.info(f"Starting HTTP transport on port {port}")
        logger.info(f"Companion download available at: http://localhost:{port}/companion/download")

        # Add custom routes for companion download
        from fastapi import Response
        from fastapi.responses import FileResponse
        import zipfile
        import io
        import os

        @mcp.custom_route("/companion/download", methods=["GET"])
        async def download_companion(request):
            """Serve companion server ZIP file for download."""
            try:
                # Create ZIP in memory
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    companion_dir = config.project_root / "companion"

                    if companion_dir.exists():
                        # Add all files in companion/ directory
                        for root, dirs, files in os.walk(str(companion_dir)):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, str(config.project_root))
                                zf.write(file_path, arcname)

                zip_buffer.seek(0)
                return Response(
                    content=zip_buffer.getvalue(),
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": "attachment; filename=companion-server.zip"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to create companion download: {e}")
                return {"error": str(e)}

        @mcp.custom_route("/companion/install.sh", methods=["GET"])
        async def download_installer(request):
            """Serve installer script."""
            installer_path = config.project_root / "install-companion.sh"
            if installer_path.exists():
                return FileResponse(
                    path=str(installer_path),
                    media_type="application/x-sh",
                    filename="install-companion.sh"
                )
            return {"error": "Installer not found"}

        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        logger.info("Starting stdio transport (Claude Desktop)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
