# Deploying ParcelPilot Backend to Render

This guide walks you through deploying the FastAPI backend to [Render](https://render.com).

## Prerequisites

- GitHub account with this repository pushed
- Render account (free tier available)
- Neon PostgreSQL database (or another PostgreSQL provider)
- OpenAI API key

## Step 1: Set Up PostgreSQL Database (Neon)

1. Go to [neon.tech](https://neon.tech) and create an account
2. Create a new project
3. Copy the connection string (looks like: `postgresql://user:password@ep-xxx.neon.tech/parcelpilot?sslmode=require`)
4. Keep this handy for Step 4

## Step 2: Push to GitHub

Ensure your code is pushed to GitHub:

```bash
git add Procfile render.yaml .env.example backend/
git commit -m "Add Render deployment configuration"
git push origin main
```

## Step 3: Connect to Render

1. Go to [render.com](https://render.com) and sign up
2. Click **New +** → **Web Service**
3. Connect your GitHub account and select this repository
4. Configure the service:
   - **Name**: `parcelpilot-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT backend.main:app`
   - **Plan**: Free or Starter (your choice)

## Step 4: Set Environment Variables

In the Render dashboard, go to **Environment** and add:

```
OPENAI_API_KEY=sk-your-actual-key-here
DATABASE_URL=postgresql://user:password@ep-xxx.neon.tech/parcelpilot?sslmode=require
FRONTEND_URL=https://your-frontend.onrender.com
BACKEND_HOST=0.0.0.0
BACKEND_PORT=10000  # (Render assigns a dynamic port; this is overridden)
```

## Step 5: Deploy

1. Click **Create Web Service**
2. Render will automatically deploy when you push to `main`
3. Monitor the build logs in the **Logs** tab
4. Once deployed, you'll get a URL like: `https://parcelpilot-backend.onrender.com`

## Step 6: Verify Deployment

Test the health endpoint:

```bash
curl https://parcelpilot-backend.onrender.com/health
# Should return: {"status":"ok"}
```

## Step 7: Initialize Database (One-Time)

After your first deploy, initialize the database schema:

```bash
# Option 1: SSH into Render shell (if available on your plan)
# Option 2: Run locally with production DATABASE_URL in .env
python -c "from backend.db.config import init_db; init_db()"
```

Then load your data:

```bash
cd backend
python db/chunk_documents.py
python db/embed_chunks.py
python db/load_data.py
```

## Step 8: Update Frontend

In your frontend deployment (Vercel, Render, etc.), set:

```
NEXT_PUBLIC_API_URL=https://parcelpilot-backend.onrender.com
```

## Troubleshooting

### Deploy fails with "ModuleNotFoundError"
- Ensure `backend/` directory structure is correct
- Check that `requirements.txt` is in the root `backend/` folder
- Render should pick up the build command from `render.yaml`

### 502 Bad Gateway
- Check logs for startup errors
- Verify `DATABASE_URL` is correct
- Ensure `OPENAI_API_KEY` is set

### Health check fails
- Backend may still be starting (give it 30-60s)
- Check `/health` endpoint responds with `{"status":"ok"}`

### Database connection timeout
- Verify PostgreSQL is running and accessible
- Test connection locally first: `psql $DATABASE_URL`
- Check if Render IP is whitelisted (Neon: allow all for free tier or add Render IPs)

## Monitoring

- **Logs**: Render dashboard → **Logs** tab
- **Metrics**: Render dashboard → **Metrics** tab (CPU, Memory, Requests)
- **Health**: `curl https://your-backend-url.onrender.com/health`

## Auto-Deploy on Push

Render automatically redeploys when you push to `main`. To disable or change branches, go to **Settings** → **Deploy** → **Deploy on Push**.

## Environment Variable Updates

To update env vars without redeploying:
1. Go to **Environment** in Render dashboard
2. Edit the variable
3. Click **Save** (will trigger a redeploy)

---

**Backend URL after deploy:** `https://parcelpilot-backend.onrender.com`

Update your frontend `NEXT_PUBLIC_API_URL` to point here.
