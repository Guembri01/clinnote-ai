# Quick Start Guide — ClinNote AI

Get up and running in under 10 minutes.

## Prerequisites
- Python 3.11+ (`python --version`)
- Node.js 18+ (`node --version`)
- Git

## Steps

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd project_03_clinnote_ai
   ```

2. **Set up the backend**
   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\activate   # Windows
   # source venv/bin/activate  # macOS/Linux
   ```

3. **Install backend dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and set:
   - `SECRET_KEY` — run: `python -c "import secrets; print(secrets.token_hex(32))"`
   - `ENCRYPTION_KEY` — run: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `OPENAI_API_KEY` — your OpenAI key (required for SOAP note generation)
   - `DEEPINFRA_API_KEY` — your DeepInfra key (required for audio transcription)
   - `DATABASE_URL` — defaults to SQLite for local dev

5. **Initialize the database**
   ```bash
   python -c "from app.database import Base, engine; import asyncio; asyncio.run(engine.dispose())"
   # Database tables are created automatically on startup via lifespan hook
   ```

6. **Start the backend**
   ```bash
   uvicorn app.main:app --reload --port 8003
   ```
   API available at: http://localhost:8003/docs

7. **Set up the frontend** (new terminal)
   ```bash
   cd ../frontend
   npm install
   ```

8. **Configure frontend environment**
   ```bash
   cp .env.example .env.local
   # Verify VITE_API_URL=http://localhost:8003
   ```

9. **Start the frontend**
   ```bash
   npm run dev
   ```
   App available at: http://localhost:3000

10. **Log in**
    - Email: `admin@clinnote.test`
    - Password: `Admin123!`

## Troubleshooting
- **Backend won't start**: Check `.env` has `SECRET_KEY` set (must be 32+ chars); run `pip install -r requirements.txt` again
- **Frontend blank page**: Make sure backend is running first; check `.env.local` has `VITE_API_URL=http://localhost:8003`
- **Database errors**: Delete `*.db` and restart backend (tables auto-created on startup)
- **SOAP notes not generating**: Ensure `OPENAI_API_KEY` is valid
- **Transcription fails**: Confirm `DEEPINFRA_API_KEY` is set; check audio format is WAV/MP3/WebM
- **HIPAA Warning**: Set `ENCRYPTION_KEY` for PHI encryption in any non-demo environment
