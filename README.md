<p align="center">
  <img src="./static/favicon.png" alt="ChatNCHU Logo" width="120" />
</p>

<h1 align="center">ChatNCHU</h1>

<p align="center">
  A customized AI chat platform for National Chung Hsing University, built on <a href="https://github.com/open-webui/open-webui/tree/v0.6.5">Open WebUI v0.6.5</a> (BSD-3).
</p>

## Features

- Multi-model AI chat via OpenRouter (Gemini, GPT-4o, Claude, etc.)
- Web search integration (DuckDuckGo, Brave, Google, etc.)
- File & image upload with RAG support
- Built-in i18n support (55 languages)
- Comprehensive admin panel
- Email-verified registration with domain whitelist
- Demo session time limits (daily login count + session duration)
- Employee/Student ID field for campus users

## Quick Start

```bash
# Clone
git clone git@github.com:NCHU-NLP-Lab/ChatNCHU.git
cd ChatNCHU

# Run
docker compose up -d
```

Access at http://localhost:8080

## Configuration

### Environment Variables

Set via `Admin Panel → Settings` or Docker environment variables.

| Variable | Description |
|----------|-------------|
| `OPENAI_API_BASE_URL` | OpenRouter API URL (`https://openrouter.ai/api/v1`) |
| `OPENAI_API_KEY` | OpenRouter API key |
| `WEBUI_AUTH` | Enable authentication (default: `true`) |
| `DEFAULT_USER_ROLE` | Default role for new users (`pending` / `user` / `admin`) |

### SMTP (for email verification)

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server host |
| `SMTP_PORT` | SMTP server port |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `SMTP_FROM` | Sender email address |

## License

ChatNCHU is licensed under the [GNU Affero General Public License v3.0](./LICENSE).

This project is based on [Open WebUI v0.6.5](https://github.com/open-webui/open-webui/tree/v0.6.5), originally released under the BSD 3-Clause License. See [NOTICE](./NOTICE) for the original copyright notice.

## Developed by

[NCHU NLP Lab](https://github.com/NCHU-NLP-Lab) — National Chung Hsing University
