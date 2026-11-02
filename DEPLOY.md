# Deploying DIMENSION (Hostinger, Docker + PostgreSQL + ODK Central)

Server: `31.97.187.66`. Same approach as NCD PEN-Plus, tamris and todolist.

**Test data only for now.** The forms are drafts. Before real participant data goes on this server, the PI or NIMR needs to confirm that a server shared with other applications is acceptable.

## How it fits on the server

There are two separate applications, each in its own folder:

| | Django | ODK Central |
|---|---|---|
| Address | https://dimension.tamris.org | https://odk.tamris.org |
| Folder | `/opt/dimension` (this repository) | `/opt/odk-central` (clone of getodk/central) |
| Port on 127.0.0.1 | `8091` | `8092` |
| Database | `dimension-db` | Central's own `postgres14` |

The host nginx and certbot handle HTTPS for both. Neither application takes a public port. `pull_odk` reads from Central over `https://odk.tamris.org`.

## 1. Check the server

```bash
df -h /                                                # at least 15 GB free for Central
free -h                                                # 2 GB available, ideally 4 GB; add swap if it is less
docker compose version                                 # 2.24.4 or newer
ss -tlnp | grep -E ':(8091|8092) ' || echo "ports free"
```

If a port is taken, choose another and change it in `.env` (`WEB_PORT`), or with `ODK_WEB_PORT=...` for Central, and in the matching `docker/nginx-*.conf`.

## 2. Django

```bash
cd /opt/dimension
git checkout develop
git pull
cp .env.production.example .env
nano .env        # DJANGO_SECRET_KEY and POSTGRES_PASSWORD (openssl rand -base64 48)
chmod 600 .env
chmod +x *.sh
```

On your computer, copy the data dictionary, which is not in git:

```bash
./copy-dictionary-to-server.sh
```

Back on the server:

```bash
./deploy-dimension.sh --first
curl -sI http://127.0.0.1:8091/admin/login/       # a 301 to HTTPS is normal
```

`--first` loads the clinics and asks for the first administrator account. Sequences stay empty until the statistician's allocation is in the workbook. Copy the updated workbook across and run `load_sites` again; it refuses to change an allocation already loaded.

Then add the nginx site and certificate (as root):

```bash
cp /opt/dimension/docker/nginx-dimension.conf /etc/nginx/sites-available/dimension.tamris.org
ln -s /etc/nginx/sites-available/dimension.tamris.org /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d dimension.tamris.org
```

## 3. ODK Central

```bash
cd /opt/dimension
./install-odk-central.sh you@example.org      # run inside tmux; the build takes several minutes
```

The script clones Central into `/opt/odk-central`, sets `SSL_TYPE=upstream`, binds Central to `127.0.0.1:8092`, and refuses to start if Central would take any public port.

Add the nginx site and certificate:

```bash
cp /opt/dimension/docker/nginx-odk.conf /etc/nginx/sites-available/odk.tamris.org
ln -s /etc/nginx/sites-available/odk.tamris.org /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d odk.tamris.org
```

Create the administrator:

```bash
cd /opt/odk-central
docker compose exec service odk-cmd --email you@example.org user-create        # asks for a password
docker compose exec service odk-cmd --email you@example.org user-promote
```

Check that Central's containers can reach their own public address, which web forms depend on:

```bash
docker compose exec service node -e "fetch('https://odk.tamris.org/').then(r => console.log(r.status))"     # 200
```

If this fails while the site opens in a browser, the firewall is blocking containers from reaching the server's public address. Central's install guide covers this under its firewall step.

## 4. Connect Django to Central

In https://odk.tamris.org:

1. Create a project and note its number from the address bar (`/projects/1`).
2. Upload `odk_forms/generated/dim_5p_phq9.xlsx` and `dim_6p_gad7.xlsx`, then publish them.
3. Create a separate web user for Django, such as `dimension-pull@…`, and give it the **Project Viewer** role on this project only. Do not use the administrator account.
4. Create an App User and scan its QR code in ODK Collect.

Put the details in `/opt/dimension/.env` (`ODK_EMAIL`, `ODK_PASSWORD`, `ODK_PROJECT_ID`), then:

```bash
cd /opt/dimension
docker compose up -d
docker compose exec dimension-web python manage.py pull_odk
```

Send a test submission from Collect, run `pull_odk` again, and check the score in https://dimension.tamris.org/admin/.

To pull every hour, add with `crontab -e`:

```
5 * * * * cd /opt/dimension && docker compose exec -T dimension-web python manage.py pull_odk >> ~/backups/dimension/pull.log 2>&1
```

## Updates

```bash
cd /opt/dimension
git pull
./deploy-dimension.sh
```

The script backs up the database, builds the new image while the old one keeps serving, runs migrations and switches containers. It prints the rollback and restore commands at the end.

To upgrade Central, read its release notes, set `CENTRAL_VERSION` and rerun the script. It backs up first:

```bash
CENTRAL_VERSION=vYYYY.N.N ./install-odk-central.sh
```

## Backups

```bash
cd /opt/dimension
./backup-dimension.sh           # to ~/backups/dimension
./backup-odk-central.sh         # to ~/backups/odk-central
```

Both keep 30 days (`KEEP_DAYS`). For daily backups, add with `crontab -e`:

```
40 1 * * * cd /opt/dimension && ./backup-dimension.sh daily >> ~/backups/dimension/backup.log 2>&1
50 1 * * * /opt/dimension/backup-odk-central.sh daily >> ~/backups/odk-central/backup.log 2>&1
```

Copy backups off the server regularly. A backup on the same server does not survive losing that server.

## Restoring

Django:

```bash
./restore-dimension.sh                 # lists the backups, newest first; pick a number (Enter = latest)
./restore-dimension.sh latest
./restore-dimension.sh 2026-11-02
```

It asks for confirmation, backs up the current state first, restores in one transaction, and prints the command to undo.

Central has no restore script. Practise this before real data is collected:

```bash
cd /opt/odk-central
docker compose stop service enketo nginx
docker compose exec -T postgres14 pg_restore --clean --if-exists --no-owner --single-transaction --exit-on-error -U odk -d odk < FILE_odk.dump
docker compose up -d
```

## Useful commands

```bash
docker compose ps
docker compose logs -f dimension-web
docker compose exec dimension-web python manage.py shell
docker compose restart dimension-web     # does not reread .env; use `docker compose up -d` after changing it
```

## Never in git

`.env`, `documentations/` and `data_dictionary/`. They are in `.gitignore`.
