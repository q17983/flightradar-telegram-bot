# 🚀 FlightRadar Telegram Bot - Cloud Deployment Guide

## 📋 **Pre-Deployment Checklist**

✅ **Bot Working Locally**: Confirmed  
✅ **Environment Variables**: All set in `.env`  
✅ **Dependencies**: Listed in `requirements.txt`  
✅ **Database Connection**: Supabase working  
✅ **All Functions**: 7 Edge Functions deployed  

---

## 🌟 **Recommended Deployment: Railway**

**Why Railway?**
- ✅ **Free tier available** (500 hours/month)
- ✅ **Easy Python deployment** 
- ✅ **Built-in environment variables**
- ✅ **Automatic HTTPS**
- ✅ **GitHub integration**
- ✅ **Persistent storage**

### 🚂 **Railway Deployment Steps**

#### **Step 1: Prepare Your Repository**
```bash
# Create a Procfile for Railway
echo "web: python telegram_bot.py" > Procfile

# Ensure requirements.txt is up to date
pip freeze > requirements.txt
```

#### **Step 2: Setup Railway Account**
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub account
3. Connect your repository

#### **Step 3: Deploy**
1. Click "New Project" → "Deploy from GitHub repo"
2. Select your FlightRadar repository
3. Railway will auto-detect Python and deploy

#### **Step 4: Configure Environment Variables**
In Railway dashboard, add these variables:
```
TELEGRAM_BOT_TOKEN=8127356642:AAFkiXL5uGmvNa9-sfWyLaHpAy8HD_TGSG4
GEMINI_API_KEY=AIzaSyD-Qv5W4P5phqzZfo8lJk9uOyWBvyaNasE
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DB_HOST=aws-0-us-west-1.pooler.supabase.com
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.your-ref
DB_PASSWORD=your-password
```

---

## 🐳 **Alternative 1: Render** 

**Pros**: Simple setup, free tier  
**Cons**: Cold starts on free tier

### **Render Deployment**
1. Go to [render.com](https://render.com)
2. Connect GitHub repository
3. Create new "Web Service"
4. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python telegram_bot.py`
5. Add environment variables from Railway list above

---

## ☁️ **Alternative 2: Heroku**

**Pros**: Robust platform, good documentation  
**Cons**: No free tier anymore (~$7/month)

### **Heroku Deployment**
```bash
# Install Heroku CLI
# Create Procfile
echo "worker: python telegram_bot.py" > Procfile

# Deploy
heroku login
heroku create your-flightradar-bot
git push heroku main

# Set environment variables
heroku config:set TELEGRAM_BOT_TOKEN=8127356642:AAFkiXL5uGmvNa9-sfWyLaHpAy8HD_TGSG4
heroku config:set GEMINI_API_KEY=AIzaSyD-Qv5W4P5phqzZfo8lJk9uOyWBvyaNasE
# ... (add all environment variables)

# Scale worker
heroku ps:scale worker=1
```

---

## 🔥 **Alternative 3: Google Cloud Run**

**Pros**: Pay-per-use, scales to zero  
**Cons**: More complex setup

### **Cloud Run Deployment**
```bash
# Create Dockerfile
cat > Dockerfile << EOF
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "telegram_bot.py"]
EOF

# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT-ID/flightradar-bot
gcloud run deploy --image gcr.io/PROJECT-ID/flightradar-bot --platform managed
```

---

## 🖥️ **Alternative 4: DigitalOcean App Platform**

**Pros**: Simple deployment, good performance  
**Cons**: Starts at $5/month

### **DigitalOcean Deployment**
1. Go to [DigitalOcean Apps](https://cloud.digitalocean.com/apps)
2. Create app from GitHub repository
3. Configure as Python app
4. Add environment variables
5. Deploy

---

## 🏆 **Recommended Choice: Railway**

**Railway is perfect for your use case because:**

1. **Free tier**: 500 hours/month (enough for 24/7 for ~21 days)
2. **Easy setup**: Just connect GitHub and deploy
3. **Automatic deploys**: Push to GitHub = auto-deploy
4. **Built-in monitoring**: See logs and metrics
5. **No cold starts**: Unlike Render's free tier

---

## 📋 **Post-Deployment Setup**

### **1. Verify Bot is Running**
```bash
# Check Railway logs
# Look for: "✅ Bot is ready! Send /start to begin."
```

### **2. Set Up Custom Domain (Optional)**
- Railway provides: `your-app.railway.app`
- Can add custom domain in settings

### **3. Monitor Usage**
- Railway dashboard shows:
  - CPU usage
  - Memory usage
  - Request logs
  - Restart history

### **4. Set Up Alerts**
- Configure email notifications for:
  - App crashes
  - High CPU usage
  - Deployment failures

---

## 🔧 **Deployment Files Needed**

**All files are ready in your project:**
- ✅ `telegram_bot.py` - Main bot code
- ✅ `requirements.txt` - Dependencies  
- ✅ `.env` - Environment variables (DO NOT commit)
- ✅ `supabase/` - Edge Functions (already deployed)

**Files to create:**
- `Procfile` - For process definition
- `.gitignore` - To exclude `.env` file

---

## 💰 **Cost Comparison**

| Platform | Free Tier | Paid Plan | Best For |
|----------|-----------|-----------|----------|
| **Railway** | 500 hrs/month | $5/month | **Recommended** |
| **Render** | 750 hrs/month | $7/month | Budget option |
| **Heroku** | None | $7/month | Enterprise |
| **Cloud Run** | Generous | Pay-per-use | Variable usage |
| **DigitalOcean** | None | $5/month | Predictable cost |

---

## 🚀 **Quick Start with Railway**

1. **Create Railway account**: [railway.app](https://railway.app)
2. **Connect GitHub**: Link your repository
3. **Deploy**: One-click deployment
4. **Add env vars**: Copy from your `.env` file
5. **Test**: Send `/start` to your bot

**Your bot will be live 24/7 within 5 minutes!** 🎉

---

## 📞 **Support & Troubleshooting**

**Common Issues:**
- **Bot not responding**: Check environment variables
- **Database errors**: Verify Supabase credentials
- **Timeout errors**: Check Supabase function URLs
- **Memory issues**: Upgrade to paid plan

**Monitoring:**
- **Railway logs**: Real-time bot activity
- **Supabase logs**: Function call history
- **Telegram bot health**: @BotFather analytics

---

**Ready to deploy? Let's start with Railway! 🚂**
