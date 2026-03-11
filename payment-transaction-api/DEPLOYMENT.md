# Deployment Guide

## Deploy to Render (Production Payment Infrastructure)

**Context**: This guide deploys a production-ready payment transaction API. Follow security best practices as this service handles financial data.

### Step 1: Prepare GitHub Repository

1. **Initialize Git** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Order/Payment API with idempotency"
   ```

2. **Create GitHub repository**:
   - Go to https://github.com/new
   - Create a new repository (e.g., `order-concurrency-lab`)
   - **Don't** initialize with README (you already have one)

3. **Push to GitHub**:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/order-concurrency-lab.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Create PostgreSQL Database on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name**: `order-api-db` (or any name)
   - **Database**: `orderdb`
   - **User**: `postgres` (default)
   - **Region**: Choose closest to you
   - **PostgreSQL Version**: 15 (or latest)
4. Click **"Create Database"**
5. **Important**: Copy the **"Internal Database URL"** (starts with `postgresql://...`)
   - This will be used as `DATABASE_URL` environment variable
   - Format: `postgresql://user:password@host:port/database`

### Step 3: Create Redis Instance on Render

1. In Render Dashboard, click **"New +"** → **"Redis"**
2. Configure:
   - **Name**: `order-api-redis`
   - **Region**: Same as PostgreSQL
   - **Redis Version**: 7 (or latest)
3. Click **"Create Redis"**
4. **Important**: Copy the **"Internal Redis URL"**
   - Format: `redis://host:port` or `rediss://host:port`
   - This will be used as `REDIS_URL` environment variable

### Step 4: Deploy Web Service

1. In Render Dashboard, click **"New +"** → **"Web Service"**
2. Connect your GitHub repository:
   - Click **"Connect account"** if not connected
   - Select your repository: `order-concurrency-lab`
3. Configure service:
   - **Name**: `order-api`
   - **Environment**: **Docker**
   - **Region**: Same as database/Redis
   - **Branch**: `main` (or your default branch)
   - **Root Directory**: `.` (leave empty)
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Context**: `.`
4. **Environment Variables**:
   - Click **"Add Environment Variable"**
   - Add:
     - **Key**: `DATABASE_URL`
     - **Value**: Paste the Internal Database URL from Step 2
   - Add:
     - **Key**: `REDIS_URL`
     - **Value**: Paste the Internal Redis URL from Step 3
5. **Advanced Settings**:
   - **Start Command**: Leave empty (Dockerfile CMD handles it)
   - **Health Check Path**: `/` (optional)
6. Click **"Create Web Service"**

### Step 5: Wait for Deployment

- Render will:
  1. Build Docker image
  2. Run `alembic upgrade head` (from Dockerfile CMD)
  3. Start the FastAPI server
- This takes **3-5 minutes** for first deployment
- Watch the **Logs** tab for progress

### Step 6: Verify Deployment

Once deployment is complete:

1. **Copy your public URL** (e.g., `https://order-api.onrender.com`)
2. **Test endpoints**:
   ```bash
   # Replace with your Render URL
   export RENDER_URL="https://your-app.onrender.com"
   
   # Test root
   curl $RENDER_URL/
   
   # Test products
   curl $RENDER_URL/products
   
   # Test create order
   curl -X POST $RENDER_URL/orders \
     -H "Content-Type: application/json" \
     -H "Idempotency-Key: prod-test-123" \
     -d '{"customerId":"c123","items":[{"productId":"p1","qty":1}]}'
   ```

### Step 7: Update README with Production URL

Add your Render URL to README.md:

```markdown
## Live Demo

API is deployed at: https://your-app.onrender.com
```

## Troubleshooting

### Issue: Build fails

**Check:**
- Dockerfile syntax is correct
- All files are committed to Git
- Requirements.txt has all dependencies

**Solution:**
- Check Render logs for specific error
- Test Docker build locally: `docker build -t order-api .`

### Issue: Database connection fails

**Check:**
- `DATABASE_URL` is set correctly (Internal URL, not Public URL)
- Database is running (check Render dashboard)
- Wait for database to be fully provisioned

**Solution:**
- Verify Internal Database URL format
- Check database status in Render dashboard

### Issue: Redis connection fails

**Check:**
- `REDIS_URL` is set correctly
- Redis instance is running

**Solution:**
- Verify Redis URL format
- Check Redis status in Render dashboard

### Issue: Migrations fail

**Check:**
- Database is accessible
- Alembic migrations are in `alembic/versions/`

**Solution:**
- Check migration logs in Render
- Run migrations manually if needed (SSH into container)

### Issue: App crashes on startup

**Check:**
- Environment variables are set
- Port is correctly configured (`$PORT` env var)

**Solution:**
- Check Render logs for error messages
- Verify Dockerfile CMD uses `$PORT` variable

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string (Internal URL) | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis connection string (Internal URL) | `redis://host:6379` |
| `PORT` | Server port (auto-set by Render) | `10000` |

## Cost Estimate (Render Free Tier)

- **PostgreSQL**: Free tier available (limited hours/month)
- **Redis**: Free tier available
- **Web Service**: Free tier available (spins down after inactivity)

**Note**: Free tier services may spin down after inactivity. First request after spin-down may take 30-60 seconds to wake up.

## Alternative: Deploy to Other Platforms

### Railway

1. Connect GitHub repo
2. Add PostgreSQL and Redis services
3. Set environment variables
4. Deploy

### Fly.io

1. Install Fly CLI
2. Run `fly launch`
3. Add PostgreSQL and Redis
4. Set secrets: `fly secrets set DATABASE_URL=... REDIS_URL=...`

### Heroku

1. Create Heroku app
2. Add PostgreSQL and Redis addons
3. Set config vars
4. Deploy via Git

---

**Need help?** Check Render documentation: https://render.com/docs
