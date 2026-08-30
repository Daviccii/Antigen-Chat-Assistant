# Antigen Chat Assistant - Railway Production Deployment Guide

## Deployment Configuration

**Selected Architecture:** Railway Full-Stack Deployment
- **Hosting:** Railway (frontend + backend + database)
- **LLM Provider:** OpenAI API (gpt-4o-mini)
- **Voice Features:** Disabled for initial production
- **Database:** Railway PostgreSQL with pgvector

## Current Status

**Repository Audit Complete:** The Antigen Chat Assistant is a fully functional personal AI assistant with:
- ✅ Complete authentication system with JWT
- ✅ User data isolation and security
- ✅ Chat with streaming responses
- ✅ Memory system with pgvector embeddings
- ✅ TimeService for authoritative time context
- ✅ OpenAI API integration (production)
- ✅ Voice functionality disabled for production
- ✅ Proper database migrations and schema
- ✅ Railway deployment configuration

## Security Fixes Applied

1. **Removed committed .env file** - Deleted `backend/.env` which contained test credentials
2. **Updated .gitignore** - Added proper exclusions for .env files, voice models, and build artifacts
3. **Fixed JWT secret placeholder** - Changed hardcoded placeholder to use environment variable
4. **Added FRONTEND_URL configuration** - For proper CORS configuration in production
5. **Updated .env.example** - Added all required environment variables with documentation
6. **Disabled voice endpoints** - Commented out voice router to reduce resource requirements
7. **Added Railway configuration** - Created railway.toml, nixpacks.toml, and Procfile

## Railway Deployment Steps

### 1. Prepare GitHub Repository

1. **Commit all changes** to your repository
2. **Push to GitHub** if not already done
3. **Ensure .gitignore is updated** to exclude sensitive files

### 2. Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Sign up/login with GitHub account
3. Create a new project

### 3. Deploy to Railway

**Option A: Automatic Deployment (Recommended)**
1. In Railway dashboard, click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose your Antigen repository
4. Railway will automatically detect the configuration

**Option B: Manual Configuration**
1. Create a new Railway project
2. Add a PostgreSQL database service
3. Add a web service from your GitHub repository
4. Configure as described below

### 4. Configure Environment Variables

In your Railway project settings, add these environment variables:

**Database:**
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

**OpenAI API:**
```
OPENAI_API_KEY=sk-your-actual-openai-api-key
```

**JWT Secret (generate a strong one):**
```bash
# Run this to generate a secure secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
```
SECRET_KEY=your-generated-secret-key-here
```

**Frontend URL (after Railway provides the domain):**
```
FRONTEND_URL=https://your-app.railway.app
```

**Backend Configuration:**
```
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

**Ollama Configuration (optional, not used in production):**
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

### 5. Configure PostgreSQL Extension

Railway's PostgreSQL includes pgvector support, but you may need to enable it:

1. Access Railway PostgreSQL console
2. Run: `CREATE EXTENSION IF NOT EXISTS vector;`
3. The startup script in `start.sh` will also attempt this automatically

### 6. Frontend Deployment

Since you're using Railway for full-stack, you have two options:

**Option A: Serve Frontend from Backend**
1. Build the frontend: `cd frontend && npm run build`
2. Copy built files to backend static directory
3. Configure FastAPI to serve static files

**Option B: Separate Frontend Service**
1. Create a separate Railway service for frontend
2. Configure it to serve the built React app
3. Update FRONTEND_URL environment variable

For simplicity, I recommend **Option A** (Serving Frontend from Backend) which is now configured:

The deployment is configured to:
1. Build the frontend during deployment
2. Copy built files to `/backend/static/` directory
3. Serve them as static files from the FastAPI backend
4. Use relative URLs when frontend and backend are served from same origin

### 7. Update Frontend API Configuration

The frontend is configured to use relative URLs in production (when served from same origin) and localhost in development. This eliminates the need for a separate VITE_API_BASE environment variable in most cases.

### 8. Testing the Deployment

After Railway deployment completes:

1. **Check health endpoint:** `https://your-app.railway.app/health`
2. **Test AI status:** `https://your-app.railway.app/ai/status`
3. **Test registration:** Use the frontend UI to create first user
4. **Test authentication:** Login with created user
5. **Test chat:** Send a message and verify OpenAI API response
6. **Test memories:** Create memories and test semantic search

## Environment Variables Summary

Create these environment variables in Railway:

**Required:**
- `DATABASE_URL=${{Postgres.DATABASE_URL}}` (Railway provides this)
- `OPENAI_API_KEY=sk-your-actual-openai-api-key`
- `SECRET_KEY=your-generated-secret-key`
- `FRONTEND_URL=https://your-app.railway.app`

**Optional (with defaults):**
- `BACKEND_HOST=0.0.0.0`
- `BACKEND_PORT=8000`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3.2`

## Testing Checklist

After deployment, test:

### Authentication
- [ ] User registration (first user becomes owner)
- [ ] User login
- [ ] Invalid credentials handling
- [ ] Token expiration
- [ ] `/auth/me` endpoint

### Core Features
- [ ] Chat with streaming responses (using OpenAI API)
- [ ] Conversation creation and retrieval
- [ ] User data isolation (User A cannot access User B's data)
- [ ] Memory creation and retrieval
- [ ] Semantic search with pgvector
- [ ] TimeService integration

### Infrastructure
- [ ] HTTPS working (Railway provides automatic HTTPS)
- [ ] Environment variables loaded correctly
- [ ] Database connectivity and migrations
- [ ] CORS configuration
- [ ] Health endpoint responding
- [ ] Frontend served from backend
- [ ] Static files loading correctly

## Local Development After Production

Local development remains unchanged:
1. Start PostgreSQL: `docker compose up -d`
2. Start backend: `cd backend && uvicorn app.main:app --reload`
3. Start frontend: `cd frontend && npm run dev`
4. Use local Ollama: `ollama run llama3.2`

The production deployment won't affect your local development setup.

## Current Limitations

1. **Voice functionality** - Disabled for production due to resource requirements
2. **Ollama dependency** - Local development feature; production uses OpenAI API
3. **Large model files** - Voice models excluded from deployment

## Troubleshooting

**Build fails:**
- Check Railway build logs for specific errors
- Ensure all dependencies are in requirements.txt
- Verify Node.js version compatibility

**Database connection issues:**
- Verify DATABASE_URL is set correctly
- Check PostgreSQL service is running in Railway
- Ensure pgvector extension is enabled

**Frontend not loading:**
- Check that static files were built and copied correctly
- Verify frontend build succeeded in deployment logs
- Check browser console for errors

**API errors:**
- Verify OPENAI_API_KEY is valid and has credits
- Check SECRET_KEY is set and strong
- Ensure CORS configuration is correct

## Next Steps to Complete Deployment

1. **Generate a strong JWT secret:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Get your OpenAI API key** from [platform.openai.com](https://platform.openai.com)

3. **Push all changes to GitHub**

4. **Deploy to Railway:**
   - Go to railway.app
   - Create new project from GitHub repo
   - Add PostgreSQL database
   - Configure environment variables
   - Deploy

5. **Test the deployed application** using the checklist above

The codebase is now fully configured for Railway full-stack deployment with proper security, configuration management, and production optimizations.
