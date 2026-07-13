# Emergent Google Auth — Testing Playbook (Main App Staff Login)

## Step 1: Create Test User & Session (Mongo)
```
mongosh --eval "
use('<DB_NAME from backend/.env>');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.oauth_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```
curl -X GET "https://your-app.com/api/auth/me" -H "Authorization: Bearer YOUR_SESSION_TOKEN"
curl -X GET "https://your-app.com/api/customers" -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Step 3: Browser Testing
```javascript
await page.context.add_cookies([{
    "name": "session_token",
    "value": "YOUR_SESSION_TOKEN",
    "domain": "your-app.com",
    "path": "/",
    "httpOnly": true,
    "secure": true,
    "sameSite": "None"
}]);
await page.goto("https://your-app.com");
```

## Quick Debug
```
mongosh --eval "
use('<DB_NAME>');
db.users.find().limit(2).pretty();
db.oauth_sessions.find().limit(2).pretty();
"
```

## Checklist
- [ ] User document has `user_id` field (custom UUID, MongoDB's `_id` is separate)
- [ ] Session `user_id` matches user's `user_id` exactly
- [ ] All queries use `{"_id": 0}` projection to exclude MongoDB's `_id`
- [ ] Backend queries use `user_id` (not `_id` or `id`)
- [ ] API returns user data with `user_id` field (not 401/404)
- [ ] Browser loads dashboard (not login page)

## Success Indicators
- `/api/auth/me` returns user data
- Dashboard loads without redirect
- CRUD operations work

## Failure Indicators
- "User not found" errors
- 401 Unauthorized responses
- Redirect to login page

## Test Identity Tracking
After setup, record in `/app/memory/test_credentials.md`:
- Allowed Google test accounts (email)
- Linked app users (tenant_id, user_id, role)
- RBAC roles/permissions mapped to each test account
- No app-managed passwords are stored for Google Auth flows.
