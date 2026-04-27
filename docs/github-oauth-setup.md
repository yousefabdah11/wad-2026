# GitHub OAuth setup (what you need to prepare)

This project uses **GitHub OAuth (Authorization Code flow)** so a user can sign in with GitHub, and then the backend will issue:

- a short-lived **JWT access token**
- a long-lived **refresh session** stored in **Redis** (TTL = **30 days**)

## 1) Create a GitHub OAuth App

In GitHub:

- **Settings** → **Developer settings** → **OAuth Apps** → **New OAuth App**

Fill the fields:

- **Application name**: e.g. `WAD Homework Chat`
- **Homepage URL**: `http://localhost:8000`
- **Authorization callback URL**: `http://localhost:8000/auth/github/callback`

After creating the app, GitHub will show:

- **Client ID**
- **Client secret** (generate / reveal)

## 2) Decide scopes

Recommended minimal scopes for sign-in:

- `read:user`
- `user:email` (so we can read a verified primary email when it’s not public)

## 3) Configure environment variables

In `project/.env` (copy from `.env.example`):

- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `GITHUB_REDIRECT_URI` (must match the callback URL you configured)
- `APP_BASE_URL` (normally `http://localhost:8000`)

## 4) What the backend will do during OAuth

1. Redirect user to GitHub authorization endpoint with `client_id`, `redirect_uri`, scopes, and a CSRF `state`
2. GitHub redirects back to `/auth/github/callback?code=...&state=...`
3. Backend exchanges `code` for GitHub access token
4. Backend fetches:
   - user profile (`/user`)
   - user emails (`/user/emails`) if needed
5. Backend upserts rows:
   - `users` (create if first login)
   - `oauth_accounts` (provider=`github`, provider_user_id)
6. Backend issues JWT + refresh token (refresh stored in Redis with TTL 30 days)

## 5) Local testing checklist

- OAuth App created and env vars set
- Clicking “Sign in with GitHub” redirects to GitHub
- After approving, you land back in the app and are logged in
- Refresh session exists in Redis and rotates on refresh

