"""GEOFlow API wrapper — push content to GEOFlow for publishing"""

import requests
import json

GEOFLOW_BASE = "http://localhost:18080"
GEOFLOW_API = f"{GEOFLOW_BASE}/api/v1"


def push_article_to_geoflow(
    title: str,
    content: str,
    keywords: str = "",
    description: str = "",
    api_token: str = "",
) -> dict:
    """Create a draft article in GEOFlow via API.

    Args:
        title: Article title
        content: Article body (Markdown)
        keywords: SEO keywords (comma-separated)
        description: Meta description
        api_token: GEOFlow API bearer token
    """
    try:
        resp = requests.post(
            f"{GEOFLOW_API}/articles",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={
                "title": title,
                "content": content,
                "keywords": keywords,
                "meta_description": description,
                "status": "draft",
            },
            timeout=30,
        )

        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": f"GEOFlow API error: {resp.status_code}", "body": resp.text}

    except requests.ConnectionError:
        return {"error": f"GEOFlow not reachable at {GEOFLOW_BASE}"}
    except Exception as e:
        return {"error": str(e)}


def create_geoflow_task(
    name: str,
    title_library_id: int,
    prompt_id: int,
    ai_model_id: int,
    api_token: str = "",
) -> dict:
    """Create a generation task in GEOFlow."""
    try:
        resp = requests.post(
            f"{GEOFLOW_API}/tasks",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={
                "name": name,
                "title_library_id": title_library_id,
                "prompt_id": prompt_id,
                "ai_model_id": ai_model_id,
                "status": "active",
            },
            timeout=30,
        )

        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": f"GEOFlow API error: {resp.status_code}", "body": resp.text}

    except requests.ConnectionError:
        return {"error": f"GEOFlow not reachable at {GEOFLOW_BASE}"}
    except Exception as e:
        return {"error": str(e)}
