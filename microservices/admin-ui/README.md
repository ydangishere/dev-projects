# Admin UI - Web Interface

Simple web UI to test and interact with the microservices system.

## 🚀 Quick Start

### Step 1: Make sure all services are running

```powershell
# Terminal 1: Infrastructure
cd d:\microservices
npm run docker:up

# Terminal 2: Auth Service
npm run dev:auth

# Terminal 3: People Service
npm run dev:people

# Terminal 4: Case Service
npm run dev:case
```

### Step 2: Open the UI

Simply open `index.html` in your browser:

```powershell
# Option 1: Double click
# Navigate to d:\microservices\admin-ui\
# Double-click index.html

# Option 2: Command line
cd d:\microservices\admin-ui
start index.html
```

Or if you prefer a local web server (optional):

```powershell
# Using Python
python -m http.server 8080

# Using Node.js http-server (if installed)
npx http-server -p 8080

# Then open: http://localhost:8080
```

## 📋 Features

### 1. Authentication
- Register new user
- Login with JWT
- Auto-save token to localStorage

### 2. People Management
- ✅ Create person
- ✅ List people (with pagination)
- ✅ View person details
- 💡 **Check console to see Redis cache hits/misses!**

### 3. Case Management
- ✅ Create case
- ✅ List cases (with pagination)
- ✅ **Search cases with Elasticsearch**
- ✅ Filter by status, priority
- 💡 **Cases are auto-indexed to Elasticsearch**

### 4. System Health
- Check all services status
- Verify infrastructure connectivity

## 🎯 How to Test

### Test Flow 1: Basic CRUD
1. **Register/Login** with email/password
2. **Create a person**: John Doe
3. **List people** → Check console for "Cache miss"
4. **List people again** → Check console for "Cache hit" 🎉
5. **Create a case** linked to John Doe
6. **List cases** → See the case

### Test Flow 2: Elasticsearch Search
1. **Create multiple cases** with different titles:
   - "Bug in login page"
   - "Feature request for dashboard"
   - "Login timeout issue"
2. **Search** for "login"
3. See Elasticsearch return relevant results 🔍

### Test Flow 3: Kafka Events
1. **Create a person** → Check People Service console
2. See: `Event published: people.created` 📡
3. **Check Case Service console**
4. See: `Received event: people.created` ✅

## 🔍 Developer Console

Open browser DevTools (F12) to see:
- API calls and responses
- Cache hit/miss information
- Kafka event notifications
- Detailed logs

## 📊 What to Look For

### Redis Cache (People Service)
```
First call:  📊 Fetching people list... → Cache miss → Query DB
Second call: 📊 Fetching people list... → Cache hit → Return from Redis
```

### Elasticsearch (Case Service)
```
Create case → 🔍 Case auto-indexed to Elasticsearch!
Search "login" → ✅ Elasticsearch search completed!
```

### Kafka Events
```
Create person → 🎉 Kafka event published: people.created
Case Service console → Received event: people.created
```

## 🎨 UI Features

- **Responsive design**: Works on desktop and mobile
- **Real-time feedback**: Success/error messages
- **Auto-save token**: No need to login every time
- **Console logging**: Detailed logs for learning

## 🐛 Troubleshooting

### Services not responding?
1. Check all terminals are running
2. Click "Check System Health" in UI
3. Verify ports:
   - 3001 (Auth)
   - 3002 (People)
   - 3003 (Cases)

### CORS errors?
This UI uses direct fetch to localhost - no CORS issues.

### Token expired?
Click "Logout" and login again.

## 📱 Mobile Testing

The UI is responsive and works on mobile browsers. You can test APIs from your phone if services are accessible on your network.

## 🔧 Customization

You can modify:
- `styles.css` - Change colors, layout
- `app.js` - Add new features, modify API calls
- `index.html` - Add new sections, forms

## 📚 Next Steps

After testing the UI:
1. Check `ARCHITECTURE.md` to understand the system
2. Look at service logs to see cache hits, events
3. Try Kibana (http://localhost:5601) for Elasticsearch visualization
4. Import `postman_collection.json` for API testing

Enjoy testing! 🚀
