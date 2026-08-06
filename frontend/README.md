# SignGuy MVP Frontend

React 19 frontend for the SignGuy MVP. The app is built with Create React App through CRACO so the project can keep CRA scripts while using aliases, Jest mappings, the `/api` development proxy, and the optional local health-check plugin.

## Requirements

- Node dependencies installed in `frontend/node_modules`
- Backend API running locally on `http://localhost:8001` for the default development proxy

## Environment

The frontend reads API calls from `REACT_APP_API_BASE_URL`.

```env
REACT_APP_API_BASE_URL=/api
SIGNGUY_DEV_API_TARGET=http://localhost:8001
```

`REACT_APP_API_BASE_URL` defaults to `/api` when it is not set. During `npm start`, CRACO proxies same-origin `/api` requests to `SIGNGUY_DEV_API_TARGET`, which defaults to `http://localhost:8001`.

## Commands

Run commands from this directory.

```powershell
npm.cmd start
npm.cmd test -- --watchAll=false
npm.cmd run build
```

Useful focused test form:

```powershell
npm.cmd test -- --runTestsByPath src/__tests__/WorkspaceDock.test.jsx --watchAll=false
```

Production builds use `craco build` and output to `frontend/build`.
