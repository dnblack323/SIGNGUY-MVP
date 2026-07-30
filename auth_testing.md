# Google OAuth Testing Playbook

SignGuy AI owns the Google OAuth flow directly. The frontend never receives a
Google client secret and no external session-data broker is used.

## Local Development Without Google

For local preview, use the development bypass only:

```env
ENV=development
AUTH_DEV_BYPASS=true
DEV_LOGIN_EMAIL=thesigntistslab@gmail.com
DEV_LOGIN_PLATFORM_CREATOR=true
```

The bypass is rejected in production by startup guards.

## Direct Google OAuth

Configure the backend only:

```env
GOOGLE_AUTH_ENABLED=true
GOOGLE_OAUTH_CLIENT_ID=replace-with-google-client-id
GOOGLE_OAUTH_CLIENT_SECRET=replace-with-google-client-secret
```

Use this redirect URI in the Google Cloud OAuth client:

```text
http://localhost:3000/auth/google/callback
```

Production deployments must register their own production origin with the same
path. The frontend starts login through:

```text
POST /api/auth/google/start
```

The backend stores a short-lived, one-time state record and returns the Google
authorization URL. Google returns `code` and `state` to:

```text
/auth/google/callback
```

The frontend then exchanges them through:

```text
POST /api/auth/google/callback
```

The backend validates the state, consumes it once, exchanges the authorization
code with Google, reads the Google profile, and issues the normal SignGuy AI JWT.
