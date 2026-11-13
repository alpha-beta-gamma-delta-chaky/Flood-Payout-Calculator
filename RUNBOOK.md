# Runbook: Flood Payout Calculator on AWS

What to do when something needs attention on the live server. For how the deployment is built, see README section 12.

## Quick facts

| Item | Value |
|---|---|
| Live site | https://flood-payout-alpha.duckdns.org (API docs at `/docs`, health at `/health`) |
| Server | AWS EC2 instance `flood-payout`, t3.small, Ubuntu 24.04, region ap-southeast-2 (Sydney) |
| Address | A fixed Elastic IP, with the DuckDNS name `flood-payout-alpha.duckdns.org` pointing at it. The IP is not written here: ask the project owner (Han) for the address and the key file if you need them |
| Log in | `ssh -i <key file> ubuntu@<server address>`. Only works from an IPv4 address allowed in the security group; ask the project owner (Han) for the address and the key file if you need them |
| App folder on the server | `~/flood-payout`: `docker-compose.yml`, `Caddyfile`, `.env` (`DOMAIN`, `IMAGE_TAG`), `.last_good_tag` |
| Deploy runner | `~/actions-runner`, service `actions.runner.alpha-beta-gamma-delta-chaky-Flood-Payout-Calculator.flood-payout-ec2` |
| Images | GitHub Container Registry, `ghcr.io/alpha-beta-gamma-delta-chaky/flood-payout-calculator`, tags `sha-xxxxxxx` and `main` |
| Alerts | `health` workflow (daily, 08:17 Bangkok time) emails on failure; CloudWatch alarm `flood-payout-cpu-high` emails when CPU stays at 80% or more for 15 minutes |

All server commands below are run after logging in, from the app folder:

```
cd ~/flood-payout
```

## 1. Is the site up?

From any computer, in the repository folder:

```
python3 scripts/smoke_test.py https://flood-payout-alpha.duckdns.org
```

`PASSED` means the page, the API and the model all work. Or run the `health` workflow by hand: GitHub, Actions, `health`, Run workflow.

## 2. Deploy

- **Normal:** push to `main`. The `ci` run tests, builds, publishes and deploys by itself (`backend`, `frontend`, `docker`, `publish`, `deploy`).
- **Redeploy the newest build** (for example after a server restart that went wrong): GitHub, Actions, `deploy`, Run workflow, branch `main`, Tag empty.
- **Work that is not ready:** use a branch and a pull request. Pull requests run the checks but never deploy.

## 3. Roll back

A failed smoke test after a deploy rolls back by itself to the tag in `.last_good_tag`, and the run shows red.

To go back by hand to an older build:

1. Find the tag. The `ci` run of the commit you want shows it in the `publish` log, and the tags are listed on GitHub under the repository's Packages. The tag is `sha-` plus the first 7 characters of the commit.
2. GitHub, Actions, `deploy`, Run workflow, branch `main`, Tag `sha-xxxxxxx`.

If GitHub Actions itself is down, roll back on the server (works for any build still stored on the server):

```
docker image ls ghcr.io/alpha-beta-gamma-delta-chaky/flood-payout-calculator   # builds on the server
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=sha-xxxxxxx/' .env
docker compose up -d
python3 ~/actions-runner/_work/Flood-Payout-Calculator/Flood-Payout-Calculator/scripts/smoke_test.py https://flood-payout-alpha.duckdns.org
```

## 4. Read the logs

```
docker compose ps                         # both containers should be "Up", the app "(healthy)"
docker compose logs --tail 100 app        # the API: estimates, errors, start-up
docker compose logs --tail 100 caddy      # HTTPS, certificates, requests that did not reach the app
docker compose logs -f app                # follow live; Ctrl+C to stop
```

The app logs only anonymous counts and timings, never the form answers. Logs rotate at 10 MB, three files per container.

## 5. Restart

```
docker compose restart app                # restart the app only (a few seconds of downtime)
docker compose up -d                      # start whatever is not running, with the settings in .env
```

Restarting does not change the version: `IMAGE_TAG` in `.env` decides which build runs.

## 6. The deploy runner

If deploys stay "Queued" in GitHub, the runner is offline. Check it on GitHub (Settings, Actions, Runners: `flood-payout-ec2` should be Idle), then on the server:

```
cd ~/actions-runner
sudo ./svc.sh status
sudo ./svc.sh start                       # if it is not running
```

## 7. Stop and start the server (to save credit)

The server uses about $0.80 of credit per day while running; a stopped server still costs about $0.18 per day for the address and the disk.

1. Disable the `health` workflow first, or it fails every day: GitHub, Actions, `health`, "...", Disable workflow.
2. EC2 console, Instances, `flood-payout`, Instance state, **Stop** (never Terminate: that deletes the server and its disk).
3. To start again: Instance state, Start. Wait about 2 minutes, then run the smoke test (section 1) and check that the runner is Idle. Enable the `health` workflow again.

The containers are set to start again by themselves (`restart: unless-stopped`) and the runner is a system service. This was not yet tested after a real restart (README section 11), so check it the first time.

## 8. SSH stopped working

A timeout on port 22 means your IP address changed. Get the new one with `curl -4 https://checkip.amazonaws.com`, then EC2 console, Security Groups, `launch-wizard-1`, Edit inbound rules, set the SSH source to `<new address>/32`, Save rules. Delete the SSH rule again when you are done; the deploys do not need it.

## 9. Alerts and what to do

| You see | Likely cause | Do this |
|---|---|---|
| `health` run failed: "does not answer" | Server stopped, containers down, or DNS | Is the instance running (EC2 console)? Then section 4 (`docker compose ps`) and section 5 |
| `health` run failed: estimate does not match | A different model is live | Check `IMAGE_TAG` in `.env` and the last deploy; roll back (section 3) |
| `health` run failed: certificate expires in under 7 days | Caddy could not renew | `docker compose logs caddy`; ports 80 and 443 must be open and the DuckDNS name must point at the server's Elastic IP (EC2 console, Elastic IPs) |
| CloudWatch email "ALARM: flood-payout-cpu-high" | The app is stuck or flooded with requests | `docker stats --no-stream`, `docker compose logs --tail 100 app`, then restart the app (section 5) |
| A deploy run is red, "Rolled back" | The new build failed the smoke test | The site runs the last good build. Read the deploy log, fix the code, push again |
| A deploy run is red, "Rollback failed too" | The site may be down | Section 4, then deploy a known good tag by hand (section 3) |
| Disk almost full (`df -h /` above 85%) | Old images and logs | `docker image prune -f`, then remove old builds with `docker image rm <image>:<old tag>`; keep the current and last good tags |
