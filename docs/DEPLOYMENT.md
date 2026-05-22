# Deployment Guide — ClinNote AI

## Docker Compose (Recommended)

### Prerequisites
- Docker 24+
- Docker Compose v2

### Steps

1. **Copy environment files**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with production values — especially ENCRYPTION_KEY for HIPAA compliance
   ```

2. **Build and start**
   ```bash
   docker compose up --build -d
   ```

App available at: http://localhost:3000  
API docs at: http://localhost:8003/docs

## Manual Deployment

### Backend (Production)
```bash
cd backend
pip install -r requirements.txt
export SECRET_KEY="<strong-random-key>"
export ENCRYPTION_KEY="<fernet-key>"   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/clinnote_ai"
export OPENAI_API_KEY="sk-..."
export DEEPINFRA_API_KEY="..."
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8003
```

### Frontend (Production Build)
```bash
cd frontend
npm install
npm run build
# Serve dist/ with nginx, caddy, or any static file server
```

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| SECRET_KEY | Yes | JWT signing key — use 64+ random hex chars |
| ENCRYPTION_KEY | Yes (HIPAA) | Fernet key for AES-256 PHI encryption at rest |
| DATABASE_URL | Yes | PostgreSQL or SQLite connection string |
| ALLOWED_ORIGINS | Yes | CORS allowed origins (comma-separated) |
| OPENAI_API_KEY | Yes | OpenAI API key for SOAP note generation |
| DEEPINFRA_API_KEY | Yes | DeepInfra Whisper key for transcription |
| AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT | If OCR enabled | Azure DI endpoint |
| AZURE_DOCUMENT_INTELLIGENCE_KEY | If OCR enabled | Azure DI API key |
| ACCESS_TOKEN_EXPIRE_MINUTES | No | JWT TTL (default: 15) |
| SESSION_INACTIVITY_TIMEOUT | No | Session timeout in seconds (default: 900) |

## Security Checklist (HIPAA)
- [ ] Set ENCRYPTION_KEY for PHI encryption at rest
- [ ] Change default admin password after first login
- [ ] Use a strong, unique SECRET_KEY (64+ hex chars)
- [ ] Set ALLOWED_ORIGINS to your actual domain only
- [ ] Never commit `.env` to version control
- [ ] Enable HTTPS in production (HIPAA requirement)
- [ ] Rotate all API keys before going live
- [ ] Configure audit log retention (HIPAA: 6 years)
- [ ] Implement zero-retention audio policy for production
