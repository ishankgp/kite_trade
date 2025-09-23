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

## 🔒 Token Lifecycle & Daily Login

- **Do I need to log in daily?** Yes. You must obtain a new access token each trading day. The saved token stops working after market close (~3:30 PM IST), so the next day you repeat the login/exchange once.
- **Request token (short‑lived, single‑use)**: You get this only after logging in via the Kite login URL. Use it immediately to exchange for an access token.
- **Access token (used by your code)**: Returned after exchanging the request token. Set it on the client and use it for API calls for the rest of the day. It expires daily.
- **API key vs API secret**:
  - API key: Public identifier of your app; used to init SDK and generate login URL.
  - API secret: Private credential; used only to exchange the request token for an access token. Keep it server‑side.

Daily flow:
- Generate login URL → user logs in → receive `request_token` on the redirect URL → exchange with `api_secret` → get `access_token` → use it for all API calls that day.

Utilities in this repo:
- `kite_api_test.py`: Full auth + endpoint tests, quick checks, and interactive mode.
- `quick_kite_test.py`: Quick pre‑auth checks; add `--full` for a minimal authenticated sanity test.
- `kite_token_manager.py`: Guided auth with token save/reuse for the day.

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

## 📜 Historical Data (OHLC) Usage

Historical endpoints use the same daily access token. Authenticate once per trading day, then call the historical APIs.

Example: authenticate and fetch last 30 days of daily candles for RELIANCE
```python
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
from env_loader import get_kite_config

cfg = get_kite_config()
kite = KiteConnect(api_key=cfg['api_key'])

# Step 1: Open this URL in browser, log in, copy request_token from redirect
print("Login URL:", kite.login_url())
request_token = input("Enter request_token: ").strip()

# Step 2: Exchange for access token (daily)
data = kite.generate_session(request_token, cfg['api_secret'])
kite.set_access_token(data['access_token'])

# Step 3: Resolve an instrument token (e.g., RELIANCE on NSE)
instruments = kite.instruments("NSE")
instrument_token = next(i['instrument_token'] for i in instruments if i['tradingsymbol'] == 'RELIANCE')

# Step 4: Fetch historical data (last 30 days, daily candles)
to_date = datetime.now()
from_date = to_date - timedelta(days=30)
bars = kite.historical_data(
    instrument_token=instrument_token,
    from_date=from_date,
    to_date=to_date,
    interval="day"
)

print(f"Fetched {len(bars)} bars. Latest close:", bars[-1]['close'] if bars else None)
```

Notes:
- You can reuse the same `access_token` for intraday intervals (e.g., `5minute`, `15minute`) until daily expiry.
- Resolve `instrument_token` once and cache it to avoid repeated instrument downloads.
- Rate limits apply; batch your requests accordingly.

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