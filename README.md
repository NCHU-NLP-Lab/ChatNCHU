<p align="center">
  <img src="./static/static/splash.png" alt="ChatNCHU Logo" width="140" />
</p>

<h1 align="center">ChatNCHU</h1>

<p align="center">
  國立中興大學 AI 聊天平台<br>
  Built on <a href="https://github.com/open-webui/open-webui/tree/v0.6.5">Open WebUI v0.6.5</a> (BSD-3-Clause)
</p>

<p align="center">
  <a href="https://hub.docker.com/r/nchunlplab/chatnchu"><img src="https://img.shields.io/docker/v/nchunlplab/chatnchu?label=Docker%20Hub&logo=docker" alt="Docker Hub" /></a>
  <a href="https://github.com/NCHU-NLP-Lab/ChatNCHU/actions"><img src="https://img.shields.io/github/actions/workflow/status/NCHU-NLP-Lab/ChatNCHU/docker-publish.yml?label=CI&logo=github" alt="CI" /></a>
</p>

<p align="center">
  <img src="./static/assets/images/nchu-gate.jpg" alt="NCHU Campus" width="600" />
</p>

---

## Features

### Inherited from Open WebUI v0.6.5

- OpenAI-compatible API support (connect to any provider)
- Web search integration (17+ engines)
- File & image upload with RAG support
- Built-in i18n (55 languages)
- Comprehensive admin panel (users, models, connections, search, etc.)
- LDAP / OAuth authentication

### ChatNCHU Additions

- **Email-verified registration** — 6-digit verification code via SMTP
- **Forgot password** — 3-step reset flow (email → code → new password)
- **Email domain whitelist** — restrict registration to specific domains (e.g. `nchu.edu.tw`)
- **Employee / Student ID** — required unique identifier for all users, supports login by ID
- **Demo session time limit** — daily login count + session duration countdown + modal warnings (15 min / 5 min) + auto-logout
- **Admin email on login page** — configurable contact info displayed in footer
- **LanguageSwitcher** — 7 languages (zh-TW, en-US, ja-JP, ko-KR, vi-VN, th-TH, id-ID)
- **Model management** — batch enable/disable, active-first sorting, auto-assign logos
- **Campus branding** — custom logo, campus gate background, branded onboarding
- **Admin user management** — custom RoleDropdown with colored role badges, CSV batch import (4-column), suspended role support
- **Password UX** — show/hide toggle + Caps Lock warning on all password fields

## Quick Start

### Using Docker Hub (recommended)

```bash
docker run -d -p 3000:8080 -v chatnchu-data:/app/backend/data --name chatnchu nchunlplab/chatnchu:latest
```

Or with `docker compose`:

```yaml
services:
  chatnchu:
    image: nchunlplab/chatnchu:latest
    ports:
      - "3000:8080"
    volumes:
      - chatnchu-data:/app/backend/data

volumes:
  chatnchu-data:
```

### Build from source

```bash
git clone git@github.com:NCHU-NLP-Lab/ChatNCHU.git
cd ChatNCHU
docker compose up -d --build
```

Access at http://localhost:3000 — the first registered user becomes admin.

> **Note:** For production deployment configuration (`.env`, reverse proxy, etc.), see the separate deploy repo.

## Admin Panel Configuration

Most settings can be configured through the **Admin Panel** GUI after login:

| Section | What you can configure |
|---------|----------------------|
| **Connections** | LLM API endpoint & key (OpenRouter, Ollama, etc.) |
| **Models** | Enable/disable models, set default models |
| **Web Search** | Search engine selection & API keys |
| **ChatNCHU Settings** | Email domains, verification, demo limits, SMTP, admin email |
| **Authentication** | Signup toggle, default role, JWT expiration, LDAP |

## License

ChatNCHU is licensed under the [GNU Affero General Public License v3.0](./LICENSE).

Based on [Open WebUI v0.6.5](https://github.com/open-webui/open-webui/tree/v0.6.5), originally released under the BSD 3-Clause License. See [NOTICE](./NOTICE) for the original copyright notice.

## Developed by

[NCHU NLP Lab](https://github.com/NCHU-NLP-Lab) — National Chung Hsing University
