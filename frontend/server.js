const express = require("express");
const path = require("path");

const app = express();
const port = Number(process.env.PORT || 3000);
const backendApiUrl = (process.env.BACKEND_API_URL || "http://localhost:8000").replace(/\/$/, "");
const cookieSecure = process.env.COOKIE_SECURE === "true";
const sessionCookie = "mf_tracker_session";

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.use(express.urlencoded({ extended: false }));
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

function readCookies(req) {
  return Object.fromEntries(
    (req.headers.cookie || "").split(";").filter(Boolean).map((item) => {
      const separator = item.indexOf("=");
      return [item.slice(0, separator).trim(), decodeURIComponent(item.slice(separator + 1))];
    }),
  );
}

function sessionToken(req) {
  return readCookies(req)[sessionCookie];
}

function setSession(res, token) {
  const attributes = ["HttpOnly", "Path=/", "SameSite=Lax", "Max-Age=28800"];
  if (cookieSecure) attributes.push("Secure");
  res.setHeader("Set-Cookie", `${sessionCookie}=${encodeURIComponent(token)}; ${attributes.join("; ")}`);
}

function clearSession(res) {
  res.setHeader("Set-Cookie", `${sessionCookie}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0`);
}

async function api(pathname, options = {}, token) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${backendApiUrl}${pathname}`, { ...options, headers });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(body?.detail || `Backend request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

const asyncRoute = (handler) => (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);

function requireSession(req, res, next) {
  if (!sessionToken(req)) return res.redirect("/login");
  return next();
}

app.get("/login", (_req, res) => res.render("login", { mode: "login", error: null }));
app.get("/register", (_req, res) => res.render("login", { mode: "register", error: null }));

app.post("/auth/login", asyncRoute(async (req, res) => {
  try {
    const result = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: req.body.email, password: req.body.password }),
    });
    setSession(res, result.access_token);
    res.redirect("/");
  } catch (error) {
    res.status(error.status || 502).render("login", { mode: "login", error: error.message });
  }
}));

app.post("/auth/register", asyncRoute(async (req, res) => {
  try {
    const result = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ full_name: req.body.full_name, email: req.body.email, password: req.body.password }),
    });
    setSession(res, result.access_token);
    res.redirect("/");
  } catch (error) {
    res.status(error.status || 502).render("login", { mode: "register", error: error.message });
  }
}));

app.post("/auth/logout", (req, res) => {
  clearSession(res);
  res.redirect("/login");
});

app.get("/", requireSession, asyncRoute(async (req, res) => {
  const token = sessionToken(req);
  try {
    const [user, funds, holdings, navSync] = await Promise.all([
      api("/auth/me", {}, token),
      api("/funds"),
      api("/me/holdings", {}, token),
      api("/nav-sync/status"),
    ]);
    res.render("index", { funds, holdings, navSync, user, apiError: null });
  } catch (error) {
    if (error.status === 401) {
      clearSession(res);
      return res.redirect("/login");
    }
    res.status(error.status || 502).render("index", { funds: [], holdings: [], navSync: null, user: null, apiError: error.message });
  }
}));

app.get("/api/funds/:fundId/nav", requireSession, asyncRoute(async (req, res) => {
  const days = Math.min(Math.max(Number(req.query.days || 30), 1), 3650);
  res.json(await api(`/funds/${encodeURIComponent(req.params.fundId)}/nav?days=${days}`));
}));

app.get("/api/holdings", requireSession, asyncRoute(async (req, res) => {
  res.json(await api("/me/holdings", {}, sessionToken(req)));
}));

app.post("/api/holdings", requireSession, asyncRoute(async (req, res) => {
  const fundId = Number(req.body.fund_id);
  const units = Number(req.body.units);
  const purchaseNav = req.body.average_purchase_nav === "" || req.body.average_purchase_nav == null
    ? null
    : Number(req.body.average_purchase_nav);
  if (!Number.isInteger(fundId) || fundId < 1 || !Number.isFinite(units) || units <= 0 || (purchaseNav !== null && (!Number.isFinite(purchaseNav) || purchaseNav <= 0))) {
    return res.status(400).json({ detail: "Enter a valid fund, units, and optional purchase NAV." });
  }
  const holding = await api("/me/holdings", {
    method: "POST",
    body: JSON.stringify({ fund_id: fundId, units, average_purchase_nav: purchaseNav }),
  }, sessionToken(req));
  res.status(201).json(holding);
}));

app.use((error, _req, res, _next) => {
  console.error(error);
  res.status(error.status || 502).json({ detail: error.message || "The dashboard could not reach the API." });
});

app.listen(port, "0.0.0.0", () => {
  console.log(`Mutual Fund Tracker dashboard listening on port ${port}`);
});
