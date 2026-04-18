"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API = "http://127.0.0.1:8000";

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

function Metric({ label, value, subtext }) {
  return (
    <div style={{ marginBottom: "1.5rem" }}>
      <p className="text-muted" style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</p>
      <h2 style={{ fontSize: "2rem", margin: "0.25rem 0" }}>{value}</h2>
      {subtext && <p className="text-muted" style={{ fontSize: "0.875rem" }}>{subtext}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [latestWorkout, setLatestWorkout] = useState(null);
  const [tokens, setTokens] = useState({ strava: false, fitbit: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [workoutsRes, tokensRes] = await Promise.all([
          fetch(`${API}/api/workouts?limit=1`),
          fetch(`${API}/api/tokens/status`),
        ]);

        if (!workoutsRes.ok || !tokensRes.ok) throw new Error("API unavailable");

        const workoutsData = await workoutsRes.json();
        const tokensData = await tokensRes.json();

        setLatestWorkout(workoutsData.workouts?.[0] || null);
        setTokens({
          strava: tokensData.strava?.has_token,
          fitbit: tokensData.fitbit?.has_token,
        });
      } catch (err) {
        setError("Backend offline");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) return <div className="animate-fade-in" style={{ textAlign: 'center', padding: '4rem' }}>Loading Dashboard...</div>;

  return (
    <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.05 } } }} style={{ width: '100%' }}>
      <motion.header variants={itemVariants} style={{ marginBottom: "4rem", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 className="title">Dashboard</h1>
          <p className="text-muted">Latest Workout Analysis</p>
        </div>
        <div style={{ display: "flex", gap: "1rem" }}>
          <span className={`status-badge ${tokens.strava ? "status-online" : "status-offline"}`}>Strava</span>
          <span className={`status-badge ${tokens.fitbit ? "status-online" : "status-offline"}`}>Fitbit</span>
        </div>
      </motion.header>

      {error && (
        <motion.div variants={itemVariants} style={{ padding: "1rem", border: "1px solid var(--card-border)", marginBottom: "2rem", color: "var(--muted-foreground)" }}>
          {error}
        </motion.div>
      )}

      {!latestWorkout ? (
        <motion.div variants={itemVariants} className="card" style={{ padding: '4rem', textAlign: 'center' }}>
          <p className="text-muted">No workout data found. Go to Settings to sync your accounts.</p>
        </motion.div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: "3rem" }}>
          {/* Main Hero Section */}
          <motion.section variants={itemVariants}>
            <div style={{ marginBottom: "3rem" }}>
               <p className="text-muted" style={{ marginBottom: "0.5rem" }}>{latestWorkout.date} &bull; {latestWorkout.source}</p>
               <h2 style={{ fontSize: "3rem", marginBottom: "1.5rem" }}>{latestWorkout.workout_title || "Untitled Session"}</h2>
               
               <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
                 <Metric label="Duration" value={`${Math.round(latestWorkout.duration_min)}m`} />
                 <Metric label="Total Volume" value={`${latestWorkout.total_volume_kg?.toLocaleString()} kg`} subtext={`${latestWorkout.exercise_count} exercises`} />
                 <Metric label="Readiness" value={latestWorkout.readiness_label || "—"} subtext={`Score: ${latestWorkout.readiness_score || "—"}`} />
                 <Metric label="Source" value={latestWorkout.source?.toUpperCase()} />
               </div>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: "1rem", fontSize: "1rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>Session Exercises</h3>
              {latestWorkout.exercises_raw && latestWorkout.exercises_raw !== "[]" ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                   {latestWorkout.exercises_raw.split('\n').filter(Boolean).map((ex, i) => (
                     <div key={i} style={{ paddingBottom: "0.5rem", borderBottom: "1px solid var(--card-border)", fontSize: "0.9375rem" }}>
                       {ex}
                     </div>
                   ))}
                </div>
              ) : (
                <p className="text-muted" style={{ padding: "1rem 0" }}>No exercise detail available for this activity type.</p>
              )}
            </div>
          </motion.section>

          {/* Biometric Sidebar */}
          <motion.aside variants={itemVariants}>
            <div className="card" style={{ background: "transparent" }}>
              <h3 style={{ marginBottom: "1.5rem", fontSize: "0.875rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>Recovery State</h3>
              <Metric label="Resting HR" value={latestWorkout.resting_hr ? `${latestWorkout.resting_hr} bpm` : "—"} />
              <Metric label="HRV" value={latestWorkout.hrv_ms ? `${latestWorkout.hrv_ms} ms` : "—"} />
              <Metric label="Sleep" value={latestWorkout.sleep_hours ? `${latestWorkout.sleep_hours}h` : "—"} subtext={latestWorkout.sleep_efficiency ? `${latestWorkout.sleep_efficiency}% efficiency` : "—"} />
            </div>
          </motion.aside>
        </div>
      )}
    </motion.div>
  );
}
