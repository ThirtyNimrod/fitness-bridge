"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API = "http://127.0.0.1:8000";

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

function SyncPanel() {
  const [syncing, setSyncing] = useState(false);
  const [status, setStatus] = useState(null);

  async function handleSync() {
    setSyncing(true);
    setStatus("Triggering background sync...");
    try {
      const res = await fetch(`${API}/api/sync`, { method: "POST" });
      const data = await res.json();
      setStatus(data.message || "Sync started.");
    } catch (e) {
      setStatus("Sync request failed.");
    }
    setTimeout(() => {
      setSyncing(false);
      setStatus(null);
    }, 3000);
  }

  return (
    <div className="card" style={{ marginBottom: "2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3>Data Synchronization</h3>
          <p className="text-muted" style={{ fontSize: "0.875rem" }}>Pull latest data from Strava and Fitbit.</p>
        </div>
        <button onClick={handleSync} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync Now"}
        </button>
      </div>
      <AnimatePresence>
        {status && (
          <motion.p 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="text-muted" 
            style={{ marginTop: "1rem", fontSize: "0.75rem", fontStyle: "italic" }}
          >
            {status}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Settings() {
  const [tokens, setTokens] = useState({ strava: false, fitbit: false });

  useEffect(() => {
    async function checkTokens() {
      try {
        const res = await fetch(`${API}/api/tokens/status`);
        const data = await res.json();
        setTokens({
          strava: data.strava?.has_token,
          fitbit: data.fitbit?.has_token,
        });
      } catch (e) {}
    }
    checkTokens();
  }, []);

  return (
    <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.05 } } }} style={{ width: '100%', maxWidth: '800px', margin: '0 auto' }}>
      <motion.header variants={itemVariants} style={{ marginBottom: "3rem" }}>
        <h1 className="title">Settings</h1>
        <p className="text-muted">Configuration and maintenance.</p>
      </motion.header>

      <motion.div variants={itemVariants}>
        <SyncPanel />
      </motion.div>

      <motion.div variants={itemVariants} className="grid">
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
            <h3 style={{ fontSize: "1rem" }}>Strava</h3>
            <span className={`status-badge ${tokens.strava ? "status-online" : "status-offline"}`}>
              {tokens.strava ? "Connected" : "Disconnected"}
            </span>
          </div>
          <p className="text-muted" style={{ fontSize: "0.875rem" }}>Used for training logs, volume analysis, and workout titles.</p>
        </div>

        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
            <h3 style={{ fontSize: "1rem" }}>Fitbit</h3>
            <span className={`status-badge ${tokens.fitbit ? "status-online" : "status-offline"}`}>
              {tokens.fitbit ? "Connected" : "Disconnected"}
            </span>
          </div>
          <p className="text-muted" style={{ fontSize: "0.875rem" }}>Used for sleep, HRV, resting heart rate, and biometric analysis.</p>
        </div>
      </motion.div>

      <motion.div variants={itemVariants} style={{ marginTop: "3rem", padding: "2rem", border: "1px dashed var(--card-border)", borderRadius: "var(--radius)", textAlign: "center" }}>
          <p className="text-muted" style={{ fontSize: "0.875rem" }}>
            To update or reconnect credentials, run the following in your terminal:
          </p>
          <code style={{ display: "block", marginTop: "1rem", color: "var(--foreground)", background: "rgba(255,255,255,0.02)", padding: "0.5rem" }}>
            python scripts/setup_tokens.py
          </code>
      </motion.div>
    </motion.div>
  );
}
