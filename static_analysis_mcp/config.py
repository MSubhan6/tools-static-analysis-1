"""Configuration management for MCP server.

Loads settings from:
1. config.yaml (project configuration)
2. Environment variables (overrides)
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """Configuration manager for MCP server."""

    def __init__(self, project_root: Optional[str] = None):
        """Initialize configuration.

        Args:
            project_root: Path to project root. If None, uses parent of mcp/ directory.
        """
        if project_root is None:
            # Default to parent of mcp/ directory
            project_root = str(Path(__file__).parent.parent)

        self.project_root = Path(project_root).resolve()
        self._config_data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config.yaml with defaults."""
        config_path = self.project_root / "config.yaml"

        # Default configuration
        default = {
            "claudePrompt": "Please analyze this code and propose improvements.",
            "claudeCodePath": "claude",
            "githubCopilotEnabled": True,
            "copilotMode": "standalone",
            "copilotCliPath": "copilot",
            "copilotModel": "claude-opus-4.6",
            "companionPort": 3000,
            "serverPort": 8000,
        }

        if not config_path.exists():
            return default

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
                return {**default, **user_config}
        except Exception:
            return default

    @property
    def output_dir(self) -> str:
        """Get output directory from environment or default."""
        return os.environ.get('OUTPUT_DIR', 'output-unified')

    @property
    def default_output_dir(self) -> str:
        """Get default output directory path."""
        return str(self.project_root / self.output_dir)

    @property
    def companion_port(self) -> int:
        """Get companion agent port."""
        return int(os.environ.get('COMPANION_PORT',
                                  self._config_data.get('companionPort', 19280)))

    @property
    def server_port(self) -> int:
        """Get HTTP server port."""
        return int(os.environ.get('SERVER_PORT',
                                  self._config_data.get('serverPort', 8000)))

    @property
    def claude_code_path(self) -> str:
        """Get Claude Code CLI path."""
        return os.environ.get('CLAUDE_CODE_PATH',
                             self._config_data.get('claudeCodePath', 'claude'))

    @property
    def claude_prompt(self) -> str:
        """Get default Claude prompt."""
        return self._config_data.get('claudePrompt',
                                     'Please analyze this code and propose improvements.')

    @property
    def copilot_enabled(self) -> bool:
        """Check if GitHub Copilot is enabled."""
        enabled_str = os.environ.get('GITHUB_COPILOT_ENABLED', '')
        if enabled_str:
            return enabled_str.lower() in ('true', '1', 'yes')
        return self._config_data.get('githubCopilotEnabled', True)

    @property
    def copilot_cli_path(self) -> str:
        """Get GitHub Copilot CLI path."""
        return os.environ.get('COPILOT_CLI_PATH',
                             self._config_data.get('copilotCliPath', 'copilot'))

    @property
    def copilot_model(self) -> str:
        """Get Copilot model name."""
        return os.environ.get('COPILOT_MODEL',
                             self._config_data.get('copilotModel', 'claude-opus-4.6'))

    @property
    def enable_wsl_tools(self) -> bool:
        """Check if WSL tools are enabled."""
        enabled_str = os.environ.get('ENABLE_WSL_TOOLS', '')
        if enabled_str:
            return enabled_str.lower() in ('true', '1', 'yes')
        return self._config_data.get('enableWslTools', False)

    @property
    def wsl_distro(self) -> str:
        """Get WSL distribution name."""
        return os.environ.get('WSL_DISTRO',
                             self._config_data.get('wslDistro', 'Ubuntu-24.04'))

    @property
    def fixes_file(self) -> Path:
        """Get path to companion fixes state file."""
        return self.project_root / ".companion-fixes.json"

    def get_triage_file(self, output_dir: str) -> Path:
        """Get path to triage decisions file for a scan.

        Args:
            output_dir: Scan output directory

        Returns:
            Path to triage.json file
        """
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            output_path = self.project_root / output_path
        return output_path / "triage.json"

    def get_prompts_dir(self) -> Path:
        """Get path to prompts directory."""
        return self.project_root / "prompts"

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config_data.get(key, default)


# Global config instance
_config: Optional[Config] = None


def get_config(project_root: Optional[str] = None) -> Config:
    """Get or create global configuration instance.

    Args:
        project_root: Path to project root. If None, uses cached instance.

    Returns:
        Config instance
    """
    global _config
    if _config is None or project_root is not None:
        _config = Config(project_root)
    return _config
