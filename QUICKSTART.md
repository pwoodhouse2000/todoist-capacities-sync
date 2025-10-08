# Quick Start Guide (Python 3.9)

## ✅ You're All Set Up!

Your environment is ready to go! Here's what's configured:

- ✅ Python 3.9.6
- ✅ Virtual environment created (`venv/`)
- ✅ All dependencies installed
- ✅ Imports tested and working
- ✅ Capacities Space ID configured
- ✅ API tokens configured

## 🚀 Run the Service Now

```bash
./run_simple.sh
```

That's it! The service will start on http://localhost:8000

## 🧪 Test It

### 1. Health Check
Open a new terminal and run:
```bash
curl http://localhost:8000/health
```

You should see: `{"status":"healthy"}`

### 2. Test with Sample Webhook
```bash
curl -X POST http://localhost:8000/todoist/webhook \
  -H "Content-Type: application/json" \
  -d @scripts/sample_webhook.json
```

### 3. Create a Real Task
1. Open Todoist
2. Create a new task
3. Add the `@capsync` label
4. Watch it appear in your Capacities workspace!

## 📊 View Logs

The service logs everything. Watch the terminal where you ran `./run_simple.sh` to see:
- Incoming webhooks
- Task processing
- API calls
- Any errors

## 🛑 Stop the Service

Press `Ctrl+C` in the terminal where the service is running.

## 🔄 Restart After Changes

If you modify any code:
```bash
# The service auto-reloads, but if needed:
# Stop with Ctrl+C
./run_simple.sh  # Start again
```

## ⚠️ Troubleshooting

### "Module not found" errors
```bash
source venv/bin/activate
pip install <missing-package>
```

### "CAPACITIES_SPACE_ID not set"
Your Space ID is already configured in `.env`:
`c2a4e579-859f-44b4-8702-265a9cf9a1a8`

### Port 8000 already in use
```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9

# Or use a different port
python -m uvicorn app.main:app --port 8001
```

## 📝 Your Configuration

| Setting | Value |
|---------|-------|
| Python Version | 3.9.6 ✅ |
| Todoist Token | Configured ✅ |
| Capacities API Key | Configured ✅ |
| Capacities Space ID | `c2a4e579-859f-44b4-8702-265a9cf9a1a8` ✅ |
| Virtual Environment | `venv/` ✅ |

## 🎯 Next Steps

1. **Test Locally** (you're here!)
   - Run `./run_simple.sh`
   - Create a test task in Todoist with `@capsync`
   - Verify it appears in Capacities

2. **Review Capacities API**
   - The Capacities API is in beta
   - If you get API errors, check `app/capacities_client.py`
   - See [Capacities API Docs](https://docs.capacities.io/developer/api)

3. **Deploy to Google Cloud** (optional)
   - See `GETTING_STARTED.md` for full deployment guide
   - Requires GCP account with billing
   - Enables real-time webhooks and hourly reconciliation

## 💡 Tips

- **Watch the logs** - Everything is logged for easy debugging
- **Test incrementally** - Start with one task, then add more
- **Check Capacities** - Verify objects are created correctly
- **Capacities API** - May need endpoint adjustments (beta API)

## 🚀 You're Ready!

Just run:
```bash
./run_simple.sh
```

And start syncing tasks! 🎉

