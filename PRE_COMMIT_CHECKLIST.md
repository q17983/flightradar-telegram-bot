# 🛡️ PRE-COMMIT SECURITY CHECKLIST

## ⚠️ **MANDATORY CHECKS BEFORE EVERY `git commit`**

### **🔍 Step 1: Scan for API Keys**
```bash
# Run this command to check for any API keys before committing:
grep -r "sk-" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules
grep -r "AIza" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules
grep -r "API_KEY" . --exclude-dir=.git --exclude-dir=venv --exclude-dir=node_modules
```

**❌ If ANY results found:** Review and remove API keys before committing!

### **🔍 Step 2: Check Git Status**
```bash
git status
git diff --cached  # Shows exactly what will be committed
```

**❌ If you see:**
- `.env` files
- `.specstory/` directories  
- Any files with `key`, `secret`, `token` in the name
- **STOP and exclude them!**

### **🔍 Step 3: Verify .gitignore Protection**
```bash
cat .gitignore | grep -E "(\.env|\.specstory|secret|key)"
```

**✅ Should show:**
```
.env
.env.local
.specstory/
**/.specstory/
*.secret
*.key
.secrets/
```

## 🚨 **IF API KEY IS ALREADY COMMITTED:**

### **IMMEDIATE ACTION (Don't wait!):**
1. **Create new API key immediately** at provider
2. **Update all environments** (local + Railway)
3. **Revoke old key** at provider (don't rely on auto-detection)

### **Git Cleanup:**
```bash
# Remove from git history (nuclear option)
git filter-branch --force --index-filter \
'git rm --cached --ignore-unmatch path/to/file/with/secrets' \
--prune-empty --tag-name-filter cat -- --all
```

## 💡 **PROPER DEVELOPMENT WORKFLOW:**

### **Environment Variables:**
1. **Local:** Use `.env` file (in .gitignore)
2. **Railway:** Set via Railway dashboard or CLI
3. **GitHub:** Never commit real values, use `.env.example` template

### **Railway Environment Setup:**
```bash
# Set environment variables on Railway (not in code)
railway variables set OPENAI_API_KEY=your_key_here
railway variables set TELEGRAM_BOT_TOKEN=your_token_here
```

### **Conversation Histories:**
- **Always protected:** `.specstory/` in `.gitignore`
- **If accidentally committed:** Move out, commit removal, move back
- **Never delete:** Contains valuable development history

## ✅ **SAFE DEPLOYMENT PROCESS:**

1. **Code changes** (no secrets in code)
2. **Test locally** with `.env` file
3. **Commit code only** (secrets excluded by .gitignore)
4. **Push to GitHub** (clean, no secrets)
5. **Railway auto-deploys** (uses environment variables from Railway dashboard)
6. **No API key recreation needed!**

---

**🎯 GOAL:** Deploy without ever committing secrets = No API key issues ever again!
