# 🤖 Telegram Bot Setup Guide

## Step 1: Create Your Bot with @BotFather

1. **Open Telegram** on your phone or computer
2. **Search for "@BotFather"** (verified account with blue checkmark)
3. **Start a chat** with @BotFather
4. **Send command**: `/newbot`
5. **Choose a name** for your bot (e.g., "FlightRadar Cargo Broker")
6. **Choose a username** ending in "bot" (e.g., "flightradar_cargo_bot")
7. **Copy the token** that @BotFather gives you

## Step 2: Add Token to Environment

1. **Copy your bot token** (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
2. **Add to your .env file**:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

## Step 3: Test Your Bot

### Option A: Local Testing (Development)
```bash
# Activate virtual environment
source "/Users/sai/Flightradar crawling/flightradar_scraper/venv/bin/activate"

# Run the bot locally
cd "/Users/sai/Flightradar crawling"
python3 telegram_bot.py
```

### Option B: Production Deployment

#### Railway (Recommended - Free Tier)
1. **Install Railway CLI**:
   ```bash
   npm install -g @railway/cli
   ```

2. **Create account**: https://railway.app/

3. **Deploy**:
   ```bash
   railway login
   railway new
   railway link
   railway up
   ```

#### Heroku Alternative
1. **Install Heroku CLI**: https://devcenter.heroku.com/articles/heroku-cli
2. **Create app**:
   ```bash
   heroku create your-flightradar-bot
   git add .
   git commit -m "Deploy Telegram bot"
   git push heroku main
   ```

## Step 4: Use Your Bot

1. **Find your bot** on Telegram (search for the username you created)
2. **Send** `/start` to begin
3. **Ask questions** like:
   - "Who flies to LAX?"
   - "Emirates routes"
   - "Carriers to London"

## Example Bot Conversation

```
You: /start
Bot: 🛩️ FlightRadar Cargo Charter Broker Bot
     I help you find carriers and routes for cargo flights!

You: Who flies to LAX?
Bot: ✅ Found 101 results:
     
     1. Delta Air Lines
        Flights: 2980 | IATA: DL
     
     2. United Airlines
        Flights: 2132 | IATA: UA
     
     3. American Airlines
        Flights: 931 | IATA: AA
     
     ... and 98 more results

You: Emirates routes
Bot: ✅ Found 45 results:
     
     1. DXB → LAX | Flights: 156
     2. DXB → JFK | Flights: 142
     3. DXB → LHR | Flights: 134
     ...
```

## Environment Variables Needed

Make sure your `.env` file contains:
```env
# Database (already configured)
DB_HOST=aws-0-ap-northeast-1.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres.prcnxrkyjnpljoqiazkp
DB_PASSWORD=alex531531

# Supabase (already configured)
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# AI (already configured)
GEMINI_API_KEY=AIzaSyD-Qv5W4P5phqzZfo8lJk9uOyWBvyaNasE

# NEW: Add your Telegram bot token
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
```

## Bot Features

- **Natural Language Processing**: Ask questions naturally
- **Smart Function Selection**: AI chooses the right data query
- **Mobile Optimized**: Perfect for on-the-go broker work
- **Real-time Data**: Connected to your 1.28M flight records
- **Multiple Query Types**: Destinations, origins, airlines, routes

## Troubleshooting

### Bot doesn't respond
- Check token is correct in `.env`
- Ensure bot is running (`python3 telegram_bot.py`)
- Verify environment variables are loaded

### "Error calling function" messages
- Check Supabase credentials
- Verify internet connection
- Check function deployment status

### Deployment issues
- Ensure all dependencies in `requirements.txt`
- Check environment variables on deployment platform
- Monitor logs for specific errors

## Next Steps

Once your bot is working:
1. **Customize responses** for your specific business needs
2. **Add more commands** (e.g., `/stats`, `/report`)
3. **Set up monitoring** for uptime tracking
4. **Share with team** for collaborative use

Your cargo charter broker business now has 24/7 mobile access to comprehensive flight data! 🚀
