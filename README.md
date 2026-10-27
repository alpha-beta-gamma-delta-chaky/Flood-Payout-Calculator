# Tech Stack: Flood Payout Calculator

Last updated: 27 October 2026
Status: planned. The model bundle, backend, frontend and deployment are not built yet.

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
| Model | Python, scikit-learn, joblib, NumPy | Three quantile gradient-boosting models (25th, 50th, 75th percentile), calibration factors and the input schema | scikit-learn must match the version used in notebook 03, or the saved model may not load |
| Data handling | pandas (only if the model pipeline needs it) | Shapes form input into model input | Check notebook 03 before adding it |
| Backend API | FastAPI, Pydantic v2, uvicorn | Endpoints `/`, `/api/estimate`, `/health`; input validation | Pydantic `extra="forbid"` rejects unknown fields, so no adjuster-only `post_` column reaches the model. FastAPI also gives automatic API docs at `/docs` |
| Rate limiting | slowapi (or a small in-app limiter) | Per-IP request limit | Protects against runaway traffic and cost |
| Frontend | React, Vite, Tailwind CSS | Input form, result page with range bar, "How it works" page | Vite builds static files. The range bar is custom, so no chart library is needed |
| Design reference | Google Stitch | Screen layouts and visual style | Design tool only. Not part of the running app |
| Testing (backend) | pytest, httpx, ruff | Unit tests, leakage test, input validation tests, regression test, API tests, lint | Runs on pull requests |
| Testing (frontend) | Vitest, React Testing Library (optional) | Component tests for the form and result page | Optional for the first version |
| Packaging | Docker (multi-stage build), Docker Compose | One image per model version. Stage 1 builds the React app; stage 2 is the Python runtime | Compose runs the app and Caddy together |
| Reverse proxy | Caddy | HTTPS, with certificates issued and renewed automatically | HTTP only until a domain points at the server |
| Hosting | AWS EC2, t3.small, Ubuntu LTS, Elastic IP, region ap-southeast-1 (Singapore) | Runs the containers | Free plan credits cover the prototype if the account is eligible (to be verified) |
| Registry | GitHub Container Registry (GHCR) | Stores tagged images | No extra AWS account or keys needed to push |
| Source control | GitHub (private repository) | Code, pull requests, workflows | Keep the repository private |
| CI | GitHub Actions on GitHub-hosted runners | Checks on every pull request | Lint, tests, leakage check, regression check, build without push |
| CD | GitHub Actions with a self-hosted runner on the EC2 server | Deploys after manual approval in the "production" environment | Smoke test; the last good tag is restored automatically on failure. Manual rollback workflow |
| Monitoring | Daily health check from GitHub Actions, CloudWatch CPU alarm, AWS Budgets alert and billing alarm | Detects outages and unexpected cost | Set up before the first deploy |
| Upgrade path (later) | AWS Lambda with Lambda Web Adapter, API Gateway, ECR, S3 and CloudFront, GitHub OIDC | Serverless hosting when the server is idle or traffic is spiky | Same Docker image; not started in this phase |

## 4. Why these choices

- **FastAPI, not Express.** The model is a Python file, so a Python backend can load it directly. Express is a Node framework and would need a second Python service or a model conversion.
- **React with Vite.** The team knows React from MERN work. Vite produces plain static files, which can move to S3 and CloudFront later. A plain HTML page with Tailwind is the fallback if time runs short.
- **EC2 with Docker Compose, not Lambda, for now.** One server is easier to debug while the team learns AWS. Lambda is the upgrade path.
- **GHCR, not ECR, for now.** GitHub Actions can push there without AWS keys. ECR is used after the Lambda move.
- **Self-hosted runner on the server.** Deploys need no inbound SSH from GitHub. The risk is that the runner must not run untrusted code: keep the repository private and run deploy jobs from `main` only.

## 5. Repository layout

```
app/            FastAPI app: main.py, schema.py, model.py
model/          joblib bundle exported from notebook 03
frontend/       React + Vite + Tailwind source
tests/          pytest tests: leakage, validation, API
Dockerfile
docker-compose.yml
Caddyfile
requirements.txt
.python-version     Python version used for the model
.nvmrc              Node LTS version for the frontend build
.github/workflows/  pull request checks, deploy, rollback
```

## 6. Version pinning

- Python packages: exact versions in `requirements.txt`. Use the scikit-learn version from notebook 03 (check with `pip show scikit-learn`).
- Frontend packages: `package-lock.json` committed.
- Python and Node versions: `.python-version` and `.nvmrc`.
- Docker base images: pinned by tag, not `latest`.

## 7. Out of scope for the prototype

- Domain name (added later; Caddy then issues HTTPS).
- User accounts, login and saved estimates.
- Database. The application stores no personal data.
- Retraining pipeline (planned for once per flood season, as a separate workflow).

## 8. Open decisions

- React or plain HTML for the frontend. Recommended: React with Vite.
- Exact scikit-learn and Python versions. Confirm from notebook 03.
- AWS account source: AWS free plan credits or a course account. Ask the TA first.
- Whether `pandas` is needed in the request path.
