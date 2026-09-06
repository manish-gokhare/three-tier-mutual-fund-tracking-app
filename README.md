# Mutual Fund Tracker — three-tier Docker application

This repository runs a PostgreSQL database, a FastAPI REST API, an AMFI NAV updater, and an Express/EJS dashboard as isolated Docker containers. The dashboard calls the API through its Node server; it never opens a database connection.

## Start it

1. Review the development values in [`.env`](/Users/manish/Documents/ChatGPT/mf-three-tier-app/.env), especially `POSTGRES_PASSWORD`.
2. From this directory, run:

   ```sh
   docker compose up --build
   ```

2a. To temporarily stop the running containers without deleting them or your networks, press Ctrl+C in the terminal where they are running.

If you ran them in detached mode (using -d), run this command from the same directory:

   ```sh
   docker compose stop
   ```

2b.

You can start them back up later by simply running docker compose up -d

   ```sh
   docker compose up -d
   ```


2c.

To stop and remove the containers, along with the custom Docker network, run:

```sh
docker compose down
```
Note: This command keeps your database data intact for the next time you start the app.

2d.

To completely wipe everything (including your database data):
If you need to start completely fresh and delete the persistent database volume, add the -v flag:

```sh
  docker compose down -v
```

3. Open [http://localhost:3000](http://localhost:3000). The FastAPI interactive documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

The first startup initializes the database with a demo investor, 50 Indian equity mutual funds covering Large, Mid, Small, Flexi, and Multi Cap categories, and 60 days of deterministic fallback NAV data. The `nav_updater` service checks AMFI's official complete NAV report every six hours, stores the latest published end-of-day NAV, and transparently prioritizes it over fallback data. AMFI publishes NAVs after each trading day; this is not an intraday price feed.

## Sign in

The dashboard now opens on a login page. Register a personal account or use the local demo account:

- Email: `demo@mftracker.local`
- Password: `DemoPass!2026`

Passwords use PBKDF2-SHA256 hashes in PostgreSQL. The Node dashboard keeps the short-lived API JWT in an `HttpOnly`, `SameSite=Lax` cookie; set `COOKIE_SECURE=true` in `.env` when serving over HTTPS. Replace `JWT_SECRET` and the database password before any non-local deployment.

## API highlights

- `GET /funds` — list funds with their latest NAV (`category` and `search` are optional filters)
- `GET /funds/{fund_id}/nav?days=30` — NAV history
- `POST /auth/register` and `POST /auth/login` — create a session or sign in
- `POST /me/holdings` — add units to the signed-in user's portfolio; repeated additions are merged using a weighted purchase NAV
- `GET /me/holdings` — signed-in holdings with current value and gain/loss
- `GET /nav-sync/status` — latest AMFI refresh status

Example add-holding payload:

```json
{
  "fund_id": 1,
  "units": 12.5,
  "average_purchase_nav": 104.25
}
```

## Reset sample data

The SQL initializer intentionally runs only on a new PostgreSQL volume. To discard all local data and seed again, stop the stack and run `docker compose down -v`, then start it again.
