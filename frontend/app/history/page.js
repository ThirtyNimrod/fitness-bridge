"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";

const API = "http://127.0.0.1:8000";

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

function HistoryItem({ workout }) {
  return (
    <motion.div variants={itemVariants} className="history-item">
      <div style={{ flex: 1 }}>
        <p className="text-muted" style={{ fontSize: "0.75rem", textTransform: "uppercase" }}>{workout.date} &bull; {workout.source}</p>
        <h3 style={{ fontSize: "1.125rem", margin: "0.25rem 0" }}>{workout.workout_title || "Untitled Session"}</h3>
        <p className="text-muted" style={{ fontSize: "0.875rem" }}>
          {workout.duration_min ? `${Math.round(workout.duration_min)}m` : "—"} &bull; {workout.total_volume_kg ? `${workout.total_volume_kg.toLocaleString()} kg` : "—"}
        </p>
      </div>
      <div style={{ textAlign: "right" }}>
        {workout.readiness_label && (
          <span className="status-badge status-online" style={{ fontSize: "0.65rem" }}>{workout.readiness_label}</span>
        )}
      </div>
    </motion.div>
  );
}

export default function History() {
  const [workouts, setWorkouts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${API}/api/workouts?limit=50`);
        const data = await res.json();
        setWorkouts(data.workouts || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.05 } } }} style={{ width: '100%', maxWidth: '700px', margin: '0 auto' }}>
      <motion.header variants={itemVariants} style={{ marginBottom: "3rem" }}>
        <h1 className="title">History</h1>
        <p className="text-muted">Your training progression over time.</p>
      </motion.header>

      {loading ? (
        <p className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>Loading activity feed...</p>
      ) : workouts.length === 0 ? (
        <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
          <p className="text-muted">No activities recorded yet.</p>
        </div>
      ) : (
        <div className="card" style={{ padding: '0 1.5rem' }}>
          {workouts.map((w) => (
            <HistoryItem key={`${w.source}-${w.activity_id}`} workout={w} />
          ))}
        </div>
      )}
    </motion.div>
  );
}
