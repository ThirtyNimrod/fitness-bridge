"use client";

import { motion } from "framer-motion";
import Link from "next/link";

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

function LobbyCard({ title, description, href }) {
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <motion.div
        className="card lobby-card"
        variants={itemVariants}
        whileHover={{ borderColor: "var(--foreground)" }}
        whileTap={{ scale: 0.99 }}
      >
        <div>
          <h3>{title}</h3>
          <p className="text-muted" style={{ fontSize: "0.875rem" }}>{description}</p>
        </div>
        <div className="arrow">→</div>
      </motion.div>
    </Link>
  );
}

export default function Lobby() {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={containerVariants}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        paddingTop: "2rem",
      }}
    >
      <motion.div variants={itemVariants} style={{ marginBottom: "4rem" }}>
        <h1 className="title">Fitness Bridge</h1>
        <p className="text-muted" style={{ fontSize: "1rem", maxWidth: "500px", margin: "0 auto" }}>
          your personalized multi-agent model for fitness dashboard and conversation
        </p>
      </motion.div>

      <motion.div className="grid" style={{ maxWidth: "900px" }} variants={containerVariants}>
        <LobbyCard
          title="Dashboard"
          description="View your latest performance metrics, readiness score, and recovery biometrics."
          href="/dashboard"
        />
        <LobbyCard
          title="Coach"
          description="Direct access to elite strength and conditioning agents for program optimization."
          href="/coach"
        />
        <LobbyCard
          title="History"
          description="Review your training progression and historical activity data in a minimal feed."
          href="/history"
        />
      </motion.div>
    </motion.div>
  );
}
