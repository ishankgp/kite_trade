# Kite Trade - Zerodha API Integration

A comprehensive testing and development environment for Zerodha Kite Connect API in GitHub Codespaces.

## 🚀 Setup Status

✅ **API Key Validated**: `175722d7dzbcd8t4`  
✅ **KiteConnect Library**: Installed and working  
✅ **Redirect URL**: `https://laughing-space-rotary-phone-g59jj4v55v6c95qr-5000.app.github.dev/callback`  
✅ **Postback URL**: `https://laughing-space-rotary-phone-g59jj4v55v6c95qr-5000.app.github.dev/postback`  

## 📁 Project Structure

```
kite_trade/
├── README.md                 # This file
├── .env                     # Environment variables (API key/secret, URLs)
├── kite_api_test.py         # Unified quick validation + full auth & API testing
├── test_server.py           # Basic callback server
├── debug_server.py          # Enhanced debugging server
└── .gitignore              # Protects your credentials
```

## 🔑 Authentication Flow

### Step 1: Create `.env` file
Create or edit `.env` (already present):
```
KITE_API_KEY=175722d7dzbcd8t4
KITE_API_SECRET=akboz1c5fu5hp06ybu360ong73c3zpw8
KITE_REDIRECT_URL=https://your-codespace-url.app.github.dev/callback
KITE_POSTBACK_URL=https://your-codespace-url.app.github.dev/postback
KITE_DEBUG=true
```
Never commit real production credentials.

### Step 2: Run Unified Test Script
```bash
# Quick validation only
python3 kite_api_test.py --quick

# Full authentication flow (if quick passes or skip quick entirely)
python3 kite_api_test.py --full

# Quick + then full automatically
python3 kite_api_test.py --quick --full

# After auth, auto-enter interactive shell
python3 kite_api_test.py --full --interactive
```

Full flow will:
1. Generate a login URL
2. You authenticate in browser
3. You copy the request_token and paste back
4. Script exchanges for access token
5. Runs endpoint tests (profile, margins, etc.)
6. Optional interactive mode

## 🧪 Available Tests

### Quick Validation (within `kite_api_test.py --quick`)
- ✅ API key format validation
- ✅ KiteConnect initialization
- ✅ Login URL generation
- ✅ Redirect URL accessibility

### Full API Test (`kite_api_test.py --full`)
- 🔐 Complete OAuth flow
- 👤 User profile
- 💰 Account margins
- 📈 Holdings
- 📍 Positions
- 📋 Orders
- 🏛️ Instruments
- 📊 Live quotes
- 🎮 Interactive mode

## 🌐 Server Components

### Test Server (`test_server.py`)
Basic HTTP server for handling Zerodha callbacks.

### Debug Server (`debug_server.py`)
Enhanced server with detailed logging for troubleshooting 413 errors and other issues.

```bash
# Start debug server
python3 debug_server.py
```

## 🔧 Configuration

Environment variables are auto-loaded by `env_loader.py`. If `python-dotenv` is installed (see `requirements.txt`), it will be used; otherwise a lightweight fallback parser loads `.env`. No secrets are hard‑coded in the source.

Install dependencies:
```bash
pip install -r requirements.txt
```

## 📚 Kite API Documentation

- **Official Docs**: https://kite.trade/docs/connect/v3/
- **Python Library**: https://github.com/zerodhatech/pykiteconnect
- **API Reference**: https://kite.trade/docs/connect/v3/api/

## 🚨 Common Issues & Solutions

### 413 Request Entity Too Large
- Usually caused by incorrect URLs
- Ensure redirect URL exactly matches registration
- Check for extra parameters in URLs

### Invalid Postback URL
- Must be HTTPS (not localhost)
- Use your Codespace URL: `https://xxx-5000.app.github.dev/postback`

### Authentication Errors
- Verify API key and secret
- Check redirect URL is accessible
- Ensure no extra slashes in URLs

## 🔒 Security Notes

1. **Never commit credentials** to git (protected by `.gitignore`)
2. **API Secret** is required for generating access tokens
3. **Access Tokens** expire daily and need regeneration
4. **Use HTTPS** for all callback URLs

## 🎯 Next Steps

1. **Get API Secret** from Kite Developer Console
2. **Add it to `.env` (or provide when prompted)**
3. **Run full test**: `python3 kite_api_test.py --full`
4. **(Optional)** Enter interactive shell
5. **Start building** your trading strategy!

## 🆘 Support

- **Zerodha Support**: https://support.zerodha.com/
- **Kite Connect Forum**: https://kite.trade/forum/
- **API Issues**: Check the debug server logs

---

**⚡ Your API key is validated and ready to use!** 🎉