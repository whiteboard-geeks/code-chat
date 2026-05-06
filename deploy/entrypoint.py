#!/usr/bin/env python3
"""
code-chat container entrypoint.

Pulls runtime secrets from self-hosted Infisical (secrets.whiteboardgeeks.com),
configures gh / heroku / temporal CLI auth, then exec's the CMD passed by the
Dockerfile (the CloudCLI server).

Required env (provided by `docker run -e ...`):
  INFISICAL_CLIENT_ID, INFISICAL_CLIENT_SECRET   (machine identity creds)
  INFISICAL_ENV                                  (defaults to "prod")

Pulls from Infisical project d6c0f76a-f68d-4e90-a5f5-1954eb7a5072 ("Whiteboard Geeks"):
  /code-chat/  : HEROKU_API_TOKEN, GITHUB_PAT, GOOGLE_OAUTH_*, OAUTH2_PROXY_*
  /            : ANTHROPIC_API_KEY (shared across WBG)
"""

import os
import subprocess
import sys

import requests

INFISICAL_DOMAIN = "https://secrets.whiteboardgeeks.com"
INFISICAL_PROJECT_ID = "d6c0f76a-f68d-4e90-a5f5-1954eb7a5072"


def die(msg, code=1):
    print(f"[entrypoint] FATAL: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def log(msg):
    print(f"[entrypoint] {msg}", flush=True)


def get_infisical_token():
    client_id = os.environ.get("INFISICAL_CLIENT_ID")
    client_secret = os.environ.get("INFISICAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        die("INFISICAL_CLIENT_ID and INFISICAL_CLIENT_SECRET must be set")
    r = requests.post(
        f"{INFISICAL_DOMAIN}/api/v1/auth/universal-auth/login",
        json={"clientId": client_id, "clientSecret": client_secret},
        timeout=15,
    )
    if not r.ok:
        die(f"Infisical login failed: HTTP {r.status_code} {r.text[:200]}")
    return r.json()["accessToken"]


def fetch_secrets(token, env, path):
    r = requests.get(
        f"{INFISICAL_DOMAIN}/api/v3/secrets/raw",
        params={
            "workspaceId": INFISICAL_PROJECT_ID,
            "environment": env,
            "secretPath": path,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if not r.ok:
        die(f"fetch_secrets({path}) failed: HTTP {r.status_code} {r.text[:200]}")
    return {s["secretKey"]: s["secretValue"] for s in r.json().get("secrets", [])}


def main():
    env = os.environ.get("INFISICAL_ENV", "prod")
    log(f"authenticating to Infisical (env={env})")
    token = get_infisical_token()

    log("fetching /code-chat/ secrets")
    code_chat = fetch_secrets(token, env, "/code-chat/")
    log(f"  got {len(code_chat)} keys: {sorted(code_chat.keys())}")

    log("fetching /ANTHROPIC_API_KEY")
    root = fetch_secrets(token, env, "/")
    if "ANTHROPIC_API_KEY" not in root:
        die("ANTHROPIC_API_KEY missing from Infisical root path")

    secrets = {**code_chat, "ANTHROPIC_API_KEY": root["ANTHROPIC_API_KEY"]}

    # Configure gh CLI — writes ~/.config/gh/hosts.yml
    if "GITHUB_PAT" in secrets:
        log("configuring gh CLI auth")
        r = subprocess.run(
            ["gh", "auth", "login", "--with-token"],
            input=secrets["GITHUB_PAT"],
            text=True,
            capture_output=True,
        )
        if r.returncode != 0:
            log(f"  gh auth login failed (rc={r.returncode}): {r.stderr.strip()}")
            # Non-fatal — agent might not need gh on every session

    # Heroku CLI honors HEROKU_API_KEY env var
    if "HEROKU_API_TOKEN" in secrets:
        secrets["HEROKU_API_KEY"] = secrets["HEROKU_API_TOKEN"]

    # Export everything to the child process env
    for k, v in secrets.items():
        os.environ[k] = v

    # Exec the CMD argv
    if len(sys.argv) < 2:
        die("no CMD passed; usage: entrypoint.py <cmd> [args...]")
    log(f"exec: {' '.join(sys.argv[1:])}")
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
