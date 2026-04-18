# OAuth 2.0 & Token Rotation Architecture
*Learnings from Fitbit API integration, generalized for robust serverless OAuth.*

This document explains the required architecture for interacting with high-security, rotating-token OAuth APIs (like Fitbit and Strava) in a stateless/serverless environment like Vercel.

---

## 1. The Two Phases of OAuth

When dealing with user data, the OAuth flow is strictly divided into two distinct phases. They cannot be merged.

### Phase 1: Human Consent (Manual)
You cannot automate logging into an API that guards personal health/activity data. 
- A human must click a physical UI button granting permission (Scopes).
- The API responds with an **Authorization Code**, which your backend exchanges for an **Initial Access Token** and an **Initial Refresh Token**.
- *Goal*: Secure the Initial Refresh Token and store it in your `.env`.

### Phase 2: The Automated Heartbeat (Serverless)
Once the server has an active Refresh Token, it can sustain the connection forever without human intervention.
- The server uses the Refresh Token to continually generate temporary (e-g., 1-hour) Access Tokens.
- Access Tokens are used to actually fetch the data via HTTP `GET` requests.

---

## 2. The "Rotating Token" Problem

Standard APIs (like older versions of Spotify or GitHub) offer a static Refresh Token. You put it in your `.env` once, and it lasts forever. 

**Fitbit and Strava use Token Rotation.** 
This means Refresh Tokens are **single-use**.
1. Your server sends the Refresh Token to the API.
2. The API gives you an Access Token, **AND a brand new Refresh Token**.
3. The API immediately invalidates/shreds the old Refresh Token.

If your code crashes before saving the *new* Refresh Token, you will be permanently locked out on your next request (`401 Unauthorized`) because the environment variable still holds the shredded token.

---

## 3. The Serverless Persistence Solution

Because Vercel serverless functions are stateless, runtime variables reset after every API call. Furthermore, `.env` file values are strictly read-only on Vercel. 

To solve Token Rotation, you **must use an external persistence layer (database)**. In this project, we used **Upstash Redis** due to its low latency and native REST API support (crucial for Edge environments).

### The Step-by-Step Execution Path

When a user triggers an API route (e.g., `/api/workout`):

1. **Check the Vault (Redis)**: The code ignores the `.env` file first and checks Redis: *"What was the last saved Refresh Token?"* (If Redis is empty, it falls back to the `.env` Initial Token).
2. **The Exchange**: The backend sends `client_id`, `client_secret`, and the `current_refresh_token` to the provider's `/oauth2/token` endpoint. 
3. **Persist the New Key MUST HAPPEN IMMEDIATELY**: The provider returns a `new_access_token` and `new_refresh_token`. Before processing any actual data, the code executes:
   ```javascript
   await redis.set('provider:refresh_token', json.new_refresh_token);
   ```
4. **Fetch Data**: The code uses the `new_access_token` to fetch the user's activities.
5. **Cache Response (Optional but Recommended)**: The code caches the massive JSON response in Redis with a TTL (Time-To-Live). This heavily reduces API limits and latency for subsequent visitors.

---

## 4. Translating this to Strava API

If applying this identical architecture to a Strava integration:

*   **Human Consent**: Strava's initial OAuth URL requires scopes like `read,activity:read_all`. 
*   **The Problem**: Strava explicitly enforces Token Rotation exactly like Fitbit. Your current architecture handles this perfectly.
*   **The Exchange URL**: Change Fitbit's `https://api.fitbit.com/oauth2/token` to Strava's `https://www.strava.com/api/v3/oauth/token`.
*   **Persistence Keys**: Instead of `redis.set('fitbit:refresh_token')`, use `redis.set('strava:refresh_token')` to maintain separation of concerns within the same Redis database.
*   **Webhooks**: Note that while Fitbit allows robust pulling via this method, Strava heavily relies on Webhooks for real-time Delta syncing (pushing data to you when an activity is complete, rather than you polling for it). 

---

## 5. Implementation Status (Fitness Bridge)

This architecture has been **implemented locally** using SQLite instead of Redis:

*   **Token Vault**: `src/utils/database.py` → `api_tokens` table with columns `provider`, `access_token`, `refresh_token`, `expires_at`.
*   **Persist-First Pattern**: Both `FitbitClient` and `StravaClient` call `upsert_api_token()` immediately after a successful refresh, before processing any data.
*   **Fallback**: Clients check the database vault first via `get_api_token(provider)`, falling back to `.env` environment variables if the vault is empty (initial setup).
*   **Token Setup**: `scripts/setup_tokens.py` handles the initial OAuth consent flow and saves tokens directly to the vault.

*For serverless deployment (e.g. Vercel), replace SQLite with Upstash Redis using the same pattern.*
