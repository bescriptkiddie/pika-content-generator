"""bb-browser CLI wrapper — 103 platform commands, public data"""

import subprocess
import json


def bb_browser_site(command: str) -> list[dict]:
    """Run a bb-browser site command and return parsed JSON output.

    Examples:
        bb_browser_site("xiaohongshu/hot")
        bb_browser_site("twitter/search AI agent")
        bb_browser_site("github/trending python")
    """
    parts = command.split()
    cmd = ["bb-browser", "site"] + parts

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return [{"error": result.stderr.strip(), "command": command}]

        output = result.stdout.strip()
        if not output:
            return []

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # 非 JSON 输出，按行返回
            return [{"text": line} for line in output.splitlines() if line.strip()]

    except subprocess.TimeoutExpired:
        return [{"error": "timeout", "command": command}]
    except FileNotFoundError:
        return [{"error": "bb-browser not installed. Run: npm install -g bb-browser"}]
