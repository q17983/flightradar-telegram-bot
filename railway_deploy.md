# 🚂 Quick Railway Deployment Guide

## ✅ **Pre-Deployment Checklist** 
- [x] Bot working locally
- [x] `requirements.txt` updated
- [x] `Procfile` created
- [x] `.gitignore` created
- [x] Environment variables documented

## 🚀 **5-Minute Railway Deployment**

### **Step 1: Create Railway Account**
1. Go to [railway.app](https://railway.app)
2. Click "Start a New Project"
3. Sign up with GitHub (recommended)

### **Step 2: Deploy from GitHub**
1. Click "Deploy from GitHub repo"
2. Select `flightradar_scraper` repository
3. Railway automatically detects Python project
4. Click "Deploy"

### **Step 3: Add Environment Variables**
In Railway dashboard → Variables tab, add:

```
TELEGRAM_BOT_TOKEN=8127356642:AAFkiXL5uGmvNa9-sfWyLaHpAy8HD_TGSG4
GEMINI_API_KEY=AIzaSyD-Qv5W4P5phqzZfo8lJk9uOyWBvyaNasE
SUPABASE_URL=https://rndhquvvnxhmwtllslqn.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJuZGhxdXZ2bnhobXd0bGxzbHFuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTI1MjU2NzgsImV4cCI6MjAyODEwMTY3OH0.FQOq4h7yYHf5V9VvgvZNH_REL-EC0Q4hjxs0
DB_HOST=aws-0-us-west-1.pooler.supabase.com
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.rndhquvvnxhmwtllslqn
DB_PASSWORD=[your-db-password]
```

⚠️ **Note**: Replace `[your-db-password]` with your actual Supabase database password

### **Step 4: Verify Deployment** 
1. Check Railway logs for: `✅ Bot is ready! Send /start to begin.`
2. Test bot on Telegram: Send `/start` to @flightradar_cargo_bot
3. Try a query: "Who flies to LAX?"

### **Step 5: Monitor**
- **Railway Dashboard**: Monitor CPU, memory, logs
- **Custom Domain**: Optional - add in Railway settings
- **Auto-Deploy**: Enabled by default on GitHub pushes

## 📊 **Expected Usage**
- **Memory**: ~100-200MB
- **CPU**: Low (spikes during queries)
- **Monthly Usage**: ~300-400 hours (within free tier)

## 🎉 **Success!**
Your FlightRadar Telegram bot is now running 24/7 in the cloud!

**Bot URL**: Available on Telegram as @flightradar_cargo_bot  
**Admin Panel**: Railway dashboard for monitoring  
**Logs**: Real-time in Railway console  

---

**Need help?** Check the main deployment guide: `CLOUD_DEPLOYMENT_GUIDE.md`
