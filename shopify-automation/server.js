const path = require("path");
const envPath = path.resolve(__dirname, ".env");
require("dotenv").config({ path: envPath });

const crypto = require("crypto");
const express = require("express");
const { createClient } = require("@supabase/supabase-js");

const app = express();
const PORT = process.env.PORT || 3000;
const SHOPIFY_WEBHOOK_SECRET = process.env.SHOPIFY_WEBHOOK_SECRET || "";
const SUPABASE_URL = (process.env.SUPABASE_URL || "").trim();
const SUPABASE_ANON_KEY = (process.env.SUPABASE_ANON_KEY || "").trim();
const isSupabaseConfigured =
  SUPABASE_URL && SUPABASE_ANON_KEY && !SUPABASE_URL.includes("xxxxx") && SUPABASE_ANON_KEY !== "your_anon_key";

const supabase = isSupabaseConfigured ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

app.use("/webhooks", express.raw({ type: "*/*" }));
app.use(express.json()); // for /orders-create-mock (outside /webhooks)

function isValidShopifyWebhook(req, rawBody) {
  const hmacHeader = req.get("X-Shopify-Hmac-Sha256") || "";
  if (!SHOPIFY_WEBHOOK_SECRET || !hmacHeader) return false;

  const digest = crypto
    .createHmac("sha256", SHOPIFY_WEBHOOK_SECRET)
    .update(rawBody, "utf8")
    .digest("base64");

  const digestBuffer = Buffer.from(digest);
  const headerBuffer = Buffer.from(hmacHeader);
  if (digestBuffer.length !== headerBuffer.length) return false;

  return crypto.timingSafeEqual(digestBuffer, headerBuffer);
}

function mapOrderToRow(payload) {
  return {
    shopify_order_id: payload.id,
    order_number: payload.order_number?.toString() || null,
    email: payload.email || null,
    total_price: payload.total_price ? parseFloat(payload.total_price) : null,
    financial_status: payload.financial_status || null,
    shop_domain: payload.source_name || null,
    raw_json: payload,
  };
}

app.get("/health", (req, res) => {
  res.status(200).send("ok");
});

// Serve orders page (static HTML)
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "orders-page.html"));
});

app.post("/webhooks/products-update", (req, res) => {
  const rawBody = req.body.toString("utf8");
  if (!isValidShopifyWebhook(req, rawBody)) {
    console.log("Invalid webhook signature");
    return res.status(401).send("invalid signature");
  }

  console.log("Topic:", req.get("X-Shopify-Topic"));
  console.log("Shop:", req.get("X-Shopify-Shop-Domain"));
  console.log("Payload:", rawBody);
  return res.status(200).send("ok");
});

// Shopify order webhook — store to database
app.post("/webhooks/orders-create", async (req, res) => {
  const rawBody = req.body.toString("utf8");
  if (!isValidShopifyWebhook(req, rawBody)) {
    console.log("Invalid webhook signature");
    return res.status(401).send("invalid signature");
  }

  let payload;
  try {
    payload = JSON.parse(rawBody);
  } catch (e) {
    console.error("Invalid JSON:", e.message);
    return res.status(400).send("invalid json");
  }

  if (!supabase) {
    console.log("Orders webhook received (Supabase not configured):", payload.id);
    return res.status(200).send("ok");
  }

  try {
    const row = mapOrderToRow(payload);
    const { data, error } = await supabase.from("orders").insert(row).select();
    if (error) {
      console.error("Supabase insert error:", error);
      return res.status(500).json({ error: error.message });
    }
    console.log("Order stored:", data?.[0]?.id ?? row.shopify_order_id);
    return res.status(200).send("ok");
  } catch (err) {
    console.error("Orders webhook error:", err);
    return res.status(500).send("error");
  }
});

// List orders from database
app.get("/orders", async (req, res) => {
  if (!supabase) {
    return res.status(503).json({
      error: "Supabase not configured",
      hint: "Set SUPABASE_URL and SUPABASE_ANON_KEY in .env",
    });
  }
  const limit = Math.min(parseInt(req.query.limit, 10) || 50, 100);
  const { data, error } = await supabase
    .from("orders")
    .select("id, shopify_order_id, order_number, email, total_price, financial_status, shop_domain, created_at")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) {
    console.error("Supabase select error:", error);
    return res.status(500).json({ error: error.message });
  }
  return res.json({ orders: data, count: data?.length ?? 0 });
});

// Mock endpoint: no HMAC, for demo/portfolio (e.g. Postman) — outside /webhooks so body is JSON
app.post("/orders-create-mock", async (req, res) => {
  const payload = req.body?.id ? req.body : {
    id: 5678901234,
    order_number: "1234",
    email: "demo@example.com",
    total_price: "99.99",
    financial_status: "paid",
    source_name: "demo.myshopify.com",
  };

  if (!supabase) {
    console.log("Mock order (Supabase not configured):", payload.id);
    return res.status(200).json({
      stored: false,
      message: "Supabase not configured — add SUPABASE_URL and SUPABASE_ANON_KEY in .env",
      mock_order: payload,
    });
  }

  try {
    const row = mapOrderToRow(payload);
    const { data, error } = await supabase.from("orders").insert(row).select();
    if (error) {
      console.error("Supabase insert error:", error);
      return res.status(500).json({ error: error.message });
    }
    console.log("Mock order stored:", data?.[0]?.id);
    return res.status(200).json({ stored: true, id: data?.[0]?.id });
  } catch (err) {
    console.error("Mock order error:", err);
    return res.status(500).json({
      stored: false,
      error: err.message || String(err),
      hint: "Check SUPABASE_URL and SUPABASE_ANON_KEY, and run supabase-orders-table.sql in Supabase.",
    });
  }
});

app.listen(PORT, () => {
  console.log(`Webhook server: http://localhost:${PORT}`);
  if (!SHOPIFY_WEBHOOK_SECRET) {
    console.log("Warning: SHOPIFY_WEBHOOK_SECRET is empty");
  }
  if (!supabase) {
    console.log("Warning: SUPABASE_URL / SUPABASE_ANON_KEY not set — orders will not be saved");
  }
});
