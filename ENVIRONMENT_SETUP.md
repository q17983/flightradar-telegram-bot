# 🔐 Environment Variables Setup Guide

## 📋 Required Environment Variables

The FlightRadar Telegram Bot requires the following environment variables to run properly:

### **Core Bot Variables**
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```

### **Supabase Integration**
```bash
SUPABASE_URL=https://prcnxrkyjnpljoqiazkp.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
```

### **Database Connection (Optional - for scrapers)**
```bash
DB_HOST=your_db_host
DB_PORT=6543
DB_NAME=postgres
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

### **FlightRadar24 Credentials (Optional - for scrapers)**
```bash
FR24_USERNAME=your_fr24_username
FR24_PASSWORD=your_fr24_password
```

## 🚀 Quick Setup Steps

### **1. Get Telegram Bot Token**
1. Message @BotFather on Telegram
2. Use `/newbot` command
3. Follow prompts to create your bot
4. Copy the token (format: `123456789:ABCdef...`)

### **2. Get OpenAI API Key**
1. Go to https://platform.openai.com/api-keys
2. Create new API key
3. Copy the key (format: `sk-...`)
4. ⚠️ **Important**: This is a paid service - monitor usage

### **3. Supabase Configuration**
- **URL**: Already configured (no change needed)
- **ANON_KEY**: Contact administrator for current key

### **4. Create .env File (Local Development)**
```bash
# Create .env file in project root
cat > .env << 'EOF'
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=https://prcnxrkyjnpljoqiazkp.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
EOF
```

### **5. Railway Cloud Deployment**
Add all variables in Railway Dashboard → Variables tab:
- No quotes needed
- Use the exact variable names listed above
- Replace placeholder values with actual credentials

## 🔍 Testing Configuration

### **Local Test**
```bash
cd "/Users/sai/Flightradar crawling"
python telegram_bot.py
```

**Expected Output:**
```
🤖 Starting FlightRadar Telegram Bot...
✅ OpenAI initialized successfully
✅ Bot is ready! Send /start to begin.
📱 Find your bot on Telegram and start chatting!
```

### **Error Troubleshooting**

**❌ `ModuleNotFoundError: No module named 'openai'`**
- **Solution**: Install dependencies: `pip install -r requirements.txt`

**❌ `Error: TELEGRAM_BOT_TOKEN not found`**
- **Solution**: Add TELEGRAM_BOT_TOKEN to .env file or environment

**❌ `Error: OPENAI_API_KEY not found`**
- **Solution**: Add OPENAI_API_KEY to .env file or environment

**❌ `Error: SUPABASE_ANON_KEY not found`**
- **Solution**: Add SUPABASE_ANON_KEY to .env file or environment

## 📊 Environment Variable Priority

1. **System Environment Variables** (highest priority)
2. **.env file** (medium priority)
3. **Default values** (lowest priority)

Only SUPABASE_URL has a default value - all other variables are required.

## 🔒 Security Notes

- Never commit API keys to version control
- Add `.env` to `.gitignore`
- Rotate keys regularly
- Monitor OpenAI usage/billing
- Use different keys for development/production

---

**Last Updated**: September 14, 2025  
**Status**: Ready for deployment ✅
