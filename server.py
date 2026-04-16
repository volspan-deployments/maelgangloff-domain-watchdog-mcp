from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import httpx
import os
from typing import Optional

mcp = FastMCP("Domain Watchdog")

BASE_URL = "https://domainwatchdog.eu/api"

def get_auth_headers() -> dict:
    token = os.environ.get("DOMAIN_WATCHDOG_TOKEN", "")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@mcp.tool()
async def search_domain(domain: str) -> dict:
    """Search for a domain name using RDAP to retrieve publicly available information such as registration dates, nameservers, status, and associated entities."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{BASE_URL}/domains/{domain}",
            headers=get_auth_headers()
        )
        if response.status_code == 404:
            return {"error": f"Domain '{domain}' not found.", "status_code": 404}
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_domain_history(
    domain: str,
    page: Optional[int] = 1,
    limit: Optional[int] = 30
) -> dict:
    """Retrieve the historical tracking data for a domain name, including past ownership changes, renewals, status transitions, and other RDAP events."""
    async with httpx.AsyncClient(timeout=30) as client:
        params = {"page": page, "itemsPerPage": limit}
        response = await client.get(
            f"{BASE_URL}/domains/{domain}/events",
            headers=get_auth_headers(),
            params=params
        )
        if response.status_code == 404:
            return {"error": f"Domain '{domain}' not found.", "status_code": 404}
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def manage_watchlist(
    action: str,
    domain: Optional[str] = None,
    auto_purchase: Optional[bool] = False,
    connector_id: Optional[str] = None
) -> dict:
    """Add, remove, or list domains in the user's watchlist. Domain Watchdog monitors watchlisted domains for deletion or status changes and can trigger auto-purchase via a provider."""
    async with httpx.AsyncClient(timeout=30) as client:
        headers = get_auth_headers()

        if action == "list":
            response = await client.get(
                f"{BASE_URL}/watched-domains",
                headers=headers
            )
            response.raise_for_status()
            return response.json()

        elif action == "add":
            if not domain:
                return {"error": "'domain' parameter is required for 'add' action."}
            payload = {"ldhName": domain}
            if auto_purchase and connector_id:
                payload["autoRenew"] = True
                payload["connector"] = f"/api/connectors/{connector_id}"
            elif auto_purchase:
                payload["autoRenew"] = True
            response = await client.post(
                f"{BASE_URL}/watched-domains",
                headers=headers,
                json=payload
            )
            if response.status_code == 422:
                return {"error": "Validation error.", "details": response.text}
            response.raise_for_status()
            return response.json()

        elif action == "remove":
            if not domain:
                return {"error": "'domain' parameter is required for 'remove' action."}
            encoded_domain = domain.replace(".", "%2E")
            response = await client.delete(
                f"{BASE_URL}/watched-domains/{domain}",
                headers=headers
            )
            if response.status_code == 404:
                return {"error": f"Domain '{domain}' not found in watchlist.", "status_code": 404}
            if response.status_code == 204:
                return {"success": True, "message": f"Domain '{domain}' removed from watchlist."}
            response.raise_for_status()
            return {"success": True}

        else:
            return {"error": f"Unknown action '{action}'. Valid actions are: 'add', 'remove', 'list'."}


@mcp.tool()
async def get_tld_info(tld: str) -> dict:
    """Retrieve information about a specific Top-Level Domain (TLD), including its RDAP server, registry policies, and ICANN accreditation status."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{BASE_URL}/tlds/{tld}",
            headers=get_auth_headers()
        )
        if response.status_code == 404:
            return {"error": f"TLD '{tld}' not found.", "status_code": 404}
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_connectors(
    page: Optional[int] = 1,
    limit: Optional[int] = 30
) -> dict:
    """List all configured registrar/provider connectors available for domain purchases."""
    async with httpx.AsyncClient(timeout=30) as client:
        params = {"page": page, "itemsPerPage": limit}
        response = await client.get(
            f"{BASE_URL}/connectors",
            headers=get_auth_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def manage_user_account(
    action: str,
    email: Optional[str] = None,
    password: Optional[str] = None
) -> dict:
    """Retrieve or update the current authenticated user's account information, including profile details and preferences."""
    async with httpx.AsyncClient(timeout=30) as client:
        headers = get_auth_headers()

        if action == "get":
            response = await client.get(
                f"{BASE_URL}/me",
                headers=headers
            )
            if response.status_code == 401:
                return {"error": "Unauthorized. Please provide a valid authentication token.", "status_code": 401}
            response.raise_for_status()
            return response.json()

        elif action == "update":
            payload = {}
            if email:
                payload["email"] = email
            if password:
                payload["plainPassword"] = password
            if not payload:
                return {"error": "No fields to update. Provide 'email' or 'password'."}
            response = await client.patch(
                f"{BASE_URL}/me",
                headers={**headers, "Content-Type": "application/merge-patch+json"},
                json=payload
            )
            if response.status_code == 401:
                return {"error": "Unauthorized. Please provide a valid authentication token.", "status_code": 401}
            if response.status_code == 422:
                return {"error": "Validation error.", "details": response.text}
            response.raise_for_status()
            return response.json()

        else:
            return {"error": f"Unknown action '{action}'. Valid actions are: 'get', 'update'."}


@mcp.tool()
async def check_icann_accreditation(registrar: str) -> dict:
    """Check the ICANN accreditation status of a registrar by name or ID."""
    async with httpx.AsyncClient(timeout=30) as client:
        params = {"search": registrar}
        response = await client.get(
            f"{BASE_URL}/registrars",
            headers=get_auth_headers(),
            params=params
        )
        if response.status_code == 404:
            return {"error": f"Registrar '{registrar}' not found.", "status_code": 404}
        response.raise_for_status()
        data = response.json()
        return data


@mcp.tool()
async def get_instance_config() -> dict:
    """Retrieve the public configuration of the Domain Watchdog instance, including enabled features, supported TLDs, and available connectors."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{BASE_URL}/instance-config",
            headers=get_auth_headers()
        )
        if response.status_code == 404:
            response2 = await client.get(
                f"{BASE_URL}/config",
                headers=get_auth_headers()
            )
            if response2.status_code == 200:
                return response2.json()
            return {"error": "Could not retrieve instance configuration.", "status_code": response.status_code}
        response.raise_for_status()
        return response.json()




_SERVER_SLUG = "maelgangloff-domain-watchdog"

def _track(tool_name: str, ua: str = ""):
    try:
        import urllib.request, json as _json
        data = _json.dumps({"slug": _SERVER_SLUG, "event": "tool_call", "tool": tool_name, "user_agent": ua}).encode()
        req = urllib.request.Request("https://www.volspan.dev/api/analytics/event", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http")

class _FixAcceptHeader:
    """Ensure Accept header includes both types FastMCP requires."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            accept = headers.get(b"accept", b"").decode()
            if "text/event-stream" not in accept:
                new_headers = [(k, v) for k, v in scope["headers"] if k != b"accept"]
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                scope = dict(scope, headers=new_headers)
        await self.app(scope, receive, send)

app = _FixAcceptHeader(Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
