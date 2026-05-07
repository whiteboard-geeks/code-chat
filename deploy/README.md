# code-chat deployment

## Prerequisites (one-time)

1. **Infisical machine identity.** In `secrets.whiteboardgeeks.com`:
   - Org settings → Identities → Create → Universal Auth.
   - Add the identity to the "Whiteboard Geeks" project with **Read** on `/code-chat/` and on the root-path key `ANTHROPIC_API_KEY`.
   - Save the client ID + client secret — these are the bootstrap creds.

2. **Secrets in place.** Confirm the Infisical project has, at env=prod:
   - `/code-chat/`: `HEROKU_API_TOKEN`, `GITHUB_PAT`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `OAUTH2_PROXY_COOKIE_SECRET`
   - `/`: `ANTHROPIC_API_KEY`

## Local smoke-test

```bash
cp deploy/.env.example deploy/.env
# fill in INFISICAL_CLIENT_ID and INFISICAL_CLIENT_SECRET

cd deploy
docker compose up --build
# → open http://localhost:3001 (uses INFISICAL_ENV=dev)
```

Check the container logs for `[entrypoint]` lines confirming Infisical pull, then `npm run server` boot.

## wbg-apps deploy (production)

Pattern matches the other apps under `/opt/<name>` with a systemd unit. The container needs Docker, which is added as part of the code-chat deploy.

```bash
# On wbg-apps
sudo install -d -o deploy -g deploy /opt/code-chat
sudo install -d /var/lib/code-chat/{data,repos,claude}    # persisted volumes
sudo chown -R deploy:deploy /var/lib/code-chat

# Pull and build
cd /opt/code-chat
git clone https://github.com/whiteboard-geeks/code-chat.git .
docker build -t code-chat:latest .
```

Then drop a systemd unit at `/etc/systemd/system/code-chat.service`:

```ini
[Unit]
Description=code-chat (forked CloudCLI)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
Restart=on-failure
ExecStartPre=-/usr/bin/docker rm -f code-chat
ExecStart=/usr/bin/docker run --name code-chat \
  -e INFISICAL_CLIENT_ID=__set_in_overrides__ \
  -e INFISICAL_CLIENT_SECRET=__set_in_overrides__ \
  -e INFISICAL_ENV=prod \
  -p 127.0.0.1:3001:3001 \
  -v /var/lib/code-chat/data:/data \
  -v /var/lib/code-chat/repos:/home/app/repos \
  -v /var/lib/code-chat/claude:/home/app/.claude \
  code-chat:latest
ExecStop=/usr/bin/docker stop code-chat

[Install]
WantedBy=multi-user.target
```

Bootstrap creds belong in a drop-in override (mode 600, owned by root) so they don't sit in the unit file:

```bash
sudo systemctl edit code-chat
# Add:
# [Service]
# Environment=INFISICAL_CLIENT_ID=...
# Environment=INFISICAL_CLIENT_SECRET=...
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now code-chat
sudo journalctl -fu code-chat
```

## Caddy snippet

`/etc/caddy/apps/code-chat.caddy`:

```caddy
handle_path /code-chat/* {
    forward_auth localhost:4180 {
        uri /oauth2/auth
        copy_headers X-Auth-Request-Email X-Auth-Request-User
    }
    reverse_proxy localhost:3001
}

handle /oauth2/* {
    reverse_proxy localhost:4180
}
```

After dropping it, `sudo systemctl reload caddy`.

## Update flow

```bash
cd /opt/code-chat
git pull
docker build -t code-chat:latest .
sudo systemctl restart code-chat
```

The volumes (`/var/lib/code-chat/*`) survive across rebuilds.
