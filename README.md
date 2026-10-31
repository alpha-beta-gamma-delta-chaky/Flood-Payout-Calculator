# Tech Stack: Flood Payout Calculator

Last updated: 1 November 2026
Status: the local MVP runs (FastAPI service and React page). The AWS deployment and the deploy workflow are not built yet.

## 1. Summary

The calculator is one web application. A Python backend loads the trained model and serves both the API and the web page. The page is built with React. Everything runs in one Docker container on one AWS EC2 server in Singapore, behind Caddy for HTTPS.

## 2. Architecture

```
Browser
   |  HTTPS (Caddy; HTTP only until a domain is set up)
   v
Caddy (container)
   |
   v
FastAPI app (container)
   |- /                 React web page (static build)
   |- /api/estimate     JSON estimate from the model
   |- /health           health check
   |- loads model bundle (joblib) at startup
```

## 3. Stack by layer

| Layer | Technology | Purpose | Notes |
|---|---|---|---|
| Model | Python, scikit-learn 1.9.1, joblib, NumPy | Per path (with or without water depth): 25th, 50th and 75th percentile gradient-boosting models plus a payout-band classifier (gives the chance of $0); calibrated ranges | scikit-learn must match the version that saved the model, or it may not load |
| Data handling | pandas | Shapes the form into model input (the model takes a DataFrame) | Needed in the request path |
| Backend API | FastAPI, Pydantic v2, uvicorn | Endpoints `/`, `/api/estimate`, `/health`; input validation | Pydantic `extra="forbid"` rejects unknown fields, so no adjuster-only `post_` column reaches the model. FastAPI also gives automatic API docs at `/docs` |
| Rate limiting | slowapi | Per-IP limit on `/api/estimate` (default 30 per minute, set with `RATE_LIMIT`) | Uses the `X-Forwarded-For` header that Caddy sets |
| Frontend | React, Vite, Tailwind CSS | Input form, result page with range bar, "How it works" page | Vite builds static files. The range bar is custom, so no chart library is needed |
| Design reference | Figma | Screen layouts, colours and type (Inter) | Design tool only. Not part of the running app |
| Testing (backend) | pytest, httpx, ruff | Ahmad's 11 tests (leakage guard, input validation, answer checks, regression on six example houses), lint. API-layer tests (HTTP, rate limit) are to be added before deploy | Runs on pull requests |
| Testing (frontend) | Vitest, React Testing Library | Form validation and the form-to-result flow | Runs on pull requests |
| Packaging | Docker (multi-stage build), Docker Compose | One image per model version. Stage 1 builds the React app; stage 2 is the Python runtime | Compose runs the app and Caddy together |
| Reverse proxy | Caddy | HTTPS, with certificates issued and renewed automatically | HTTP only until a domain points at the server |
| Hosting | AWS EC2, t3.small, Ubuntu LTS, Elastic IP, region ap-southeast-1 (Singapore) | Runs the containers | Free plan credits cover the prototype if the account is eligible (to be verified) |
| Registry | GitHub Container Registry (GHCR) | Stores tagged images | No extra AWS account or keys needed to push |
| Source control | GitHub (private repository) | Code, pull requests, workflows | Keep the repository private |
| CI | GitHub Actions on GitHub-hosted runners | Checks on every pull request | Lint, tests, leakage check, regression check, build without push |
| CD | GitHub Actions with a self-hosted runner on the EC2 server | Deploys when someone starts the deploy workflow by hand from `main` | Smoke test; the last good tag is restored automatically on failure. Manual rollback workflow. (Approval gates on environments are not available on private repositories on the free plan) |
| Monitoring | Daily health check from GitHub Actions, CloudWatch CPU alarm, AWS Budgets alert and billing alarm | Detects outages and unexpected cost | Set up before the first deploy |
| Upgrade path (later) | AWS Lambda with Lambda Web Adapter, API Gateway, ECR, S3 and CloudFront, GitHub OIDC | Serverless hosting when the server is idle or traffic is spiky | Same Docker image; not started in this phase |

## 4. Why these choices

- **Monolith.** One FastAPI service serves the API, the model and the React build. It is the simplest option for one model and one server, and it is easy to deploy and debug.
- **Iterative development.** Work runs in thin slices, and each slice ends with something that runs or is deployed. Waterfall was not chosen because the model and UI may change after results come in.
- **React with Vite.** The team knows React from MERN work. Vite produces plain static files, which can move to S3 and CloudFront later. A plain HTML page with Tailwind is the fallback if time runs short.
- **EC2 with Docker Compose, not Lambda, for now.** One server is easier to debug while the team learns AWS. Lambda is the upgrade path.
- **GHCR, not ECR, for now.** GitHub Actions can push there without AWS keys. ECR is used after the Lambda move.
- **Self-hosted runner on the server.** Deploys need no inbound SSH from GitHub. The risk is that the runner must not run untrusted code: keep the repository private and run deploy jobs from `main` only.

## 5. Repository layout

```
app/                  FastAPI service: main.py (routes, rate limit), schema.py (Pydantic), model.py (loads the bundle)
src/flood_payout/     shared model code: bundle.py (validation, prediction), features.py (form fields,
                      leakage rules), final_config.py, models.py, evaluation.py
models/               flood_payout_v2.joblib (model bundle) and MODEL_CARD.md
frontend/             React + Vite + Tailwind source (npm run build writes frontend/dist)
tests/                pytest: leakage guard, validation, answers, regression on example houses
retrain.py            seasonal retraining; promotes a new bundle only if it is not worse
requirements.txt      pinned Python packages (production)
requirements-dev.txt  adds pytest, httpx, ruff
pyproject.toml        ruff and pytest settings
Dockerfile            multi-stage: builds the React app, then the Python runtime image
docker-compose.yml    app + Caddy together
Caddyfile             HTTPS and reverse proxy
.env.example          DOMAIN setting (copy to .env)
.python-version       Python 3.13 (Node 22 is in frontend/.nvmrc)
.github/workflows/    ci.yml (pull request checks); deploy workflow comes later
```

## 6. Version pinning

- Python packages: exact versions in `requirements.txt`, the ones the model file was built with (scikit-learn 1.9.1). A joblib model must be loaded with the same scikit-learn version that saved it.
- Frontend packages: `package-lock.json` committed.
- Python and Node versions: `.python-version` and `frontend/.nvmrc`.
- Docker base images: pinned by tag, not `latest`.

## 7. Out of scope for the prototype

- Domain name (added later; Caddy then issues HTTPS).
- User accounts, login and saved estimates.
- Database. The application stores no personal data.
- Retraining pipeline (planned for once per flood season, as a separate workflow).

## 8. Open decisions

- AWS account source: AWS free plan credits or a course account. Ask the TA first.
- Settled for the MVP: FastAPI with Pydantic, React with Vite, scikit-learn 1.9.1 and Python 3.13 (the versions the model was built with), and `pandas` in the request path.

## 9. Fallback and backup plan

- **Fallback if EC2 cannot be paid for:** AWS Lambda, running the same Docker image through Lambda Web Adapter, API Gateway, ECR, S3 and CloudFront. It costs less at low traffic, and AWS's always-free allowance may cover a demo. The first request after a quiet period is slower, because the model loads again. Test a Lambda deploy of the same image while the free credits last, so the fallback is proven before it is needed.
- **Backup server (school server, ml_brain lab),** if the lab confirms all of the following:
  - it is reachable from the internet on ports 80 and 443
  - Docker can be installed, with root or sudo access
  - hosting a public web app is allowed
  - it stays up through the demo
  - it has enough CPU, memory and uptime for the app

  The same image and DuckDNS subdomain work there too.

## 10. Run the app locally

No AWS account is needed. Run every command from the repository root unless a step says otherwise. There are two ways: Option A needs Python and Node on your computer, Option B needs only Docker Desktop.

### Before you start (Option A)

Check your versions:

```
python3.13 --version     # Python 3.13.x
node --version           # v22.x
```

Python 3.13 and Node 22 are pinned in `.python-version` and `frontend/.nvmrc`. With an older Node (for example v20), `npm ci` stops with "Unsupported engine". Install Node 22 with nvm and open a new terminal:

```
nvm install 22
nvm use 22
```

### Option A: on your computer

**1. Python environment (once).**

```
python3.13 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

**2. Check the back end.** Expect `All checks passed!` and `11 passed`.

```
ruff check .
pytest
```

**3. Build the page** (once, and again after you change the front end). Expect `15 passed` from the tests.

```
cd frontend
npm ci
npm test
npm run build                    # writes frontend/dist
cd ..
```

**4. Start the service.**

```
uvicorn app.main:app --port 8000
```

**5. Use it.** Open http://localhost:8000, choose "Start estimate", answer the ten questions and read the result. Stop the service with Ctrl+C.

The service serves the page at `/`, the estimate endpoint `POST /api/estimate`, a health check at `/health` and API docs at `/docs`. To try the API without the page, in a second terminal:

```
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/estimate -H "Content-Type: application/json" \
  -d '{"flood_zone":"A","year_built":1985,"floors":"1","foundation":"slab","basement":"none","elevated":false,"primary_residence":true,"coverage_building":250000,"deductible_building":1250,"water_depth_inches":12}'
```

This example house returns a low of 38,600, a middle of 88,500 and a high of 138,600, with a coverage limit of 250,000.

**While editing the page.** Keep the service running (step 4). In a second terminal run `cd frontend && npm run dev` and open the address it prints (usually http://localhost:5173). It forwards `/api` and `/health` to the service on port 8000, and your changes show up without a rebuild.

### Option B: Docker Desktop

Start Docker Desktop, then:

```
docker compose up --build
```

The first build downloads the base images and packages, so it takes a while. Open http://localhost. Caddy serves plain HTTP on port 80 while `DOMAIN` is unset. The build compiles the React page and fails if the model file does not load with the pinned library versions. Stop with Ctrl+C, then run `docker compose down`.

### Settings (optional)

| Setting | Default | What it does |
|---|---|---|
| `RATE_LIMIT` | `30/minute` | Requests allowed per client address. Example: `RATE_LIMIT=300/minute uvicorn app.main:app --port 8000` |
| `MODEL_PATH` | `models/flood_payout_v2.joblib` | Model bundle to load |
| `STATIC_DIR` | `frontend/dist` | Folder with the built page (the Docker image sets `/srv/static`) |
| `DOMAIN` | `:80` | Name Caddy serves, set in `.env` for Docker (see `.env.example`) |

### If something goes wrong

| What you see | What to do |
|---|---|
| `Unsupported engine` or `Cannot find native binding` during `npm ci` or `npm test` | Node is older than 22. Run `nvm install 22`, open a new terminal, run `rm -rf frontend/node_modules`, then `npm ci` again. Do not delete `package-lock.json`. |
| http://localhost:8000 shows a short JSON message pointing to `/docs` instead of the page | The page is not built. Run step 3. |
| `Address already in use` | Another program uses the port. Start with `--port 8001` and open that port instead. |
| "Too many requests" in the page | The limit is 30 requests per minute per address. Wait a minute, or raise `RATE_LIMIT`. |
| `ModuleNotFoundError: No module named 'app'` | You are not in the repository root, or the virtual environment is not active. |
| Docker: "Cannot connect to the Docker daemon" | Start Docker Desktop and run the command again. |
| Docker: port 80 or 443 is already allocated | Stop the program that uses it, or change the `ports` entries in `docker-compose.yml`. |

The claims data is not in this repository. `retrain.py` needs it as input (`--table`), so retraining runs where the data is.
