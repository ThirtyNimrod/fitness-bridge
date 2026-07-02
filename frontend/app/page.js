"use client";

import { motion } from "framer-motion";
import Link from "next/link";

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

function ActionModule({ title, description, href, delay = 0 }) {
  return (
    <Link href={href} style={{ textDecoration: 'none' }}>
      <motion.div 
        className="action-module group"
        variants={itemVariants}
      >
        <div className="module-header">
          <h3 className="module-title">{title}</h3>
          <span className="module-arrow">→</span>
        </div>
        <p className="module-desc">{description}</p>
      </motion.div>
    </Link>
  );
}

export default function Home() {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={containerVariants}
    >
      <section className="hero-section">
        <motion.span className="eyebrow" variants={itemVariants}>
          Current Status
        </motion.span>
        <motion.div variants={itemVariants} style={{ display: 'flex', alignItems: 'baseline', gap: '1rem' }}>
          <h1 className="hero-metric">84</h1>
          <span style={{ fontSize: '2rem', fontFamily: 'var(--font-display)', color: 'var(--muted-foreground)' }}>/ 100</span>
        </motion.div>
        <motion.h2 className="display-title" variants={itemVariants} style={{ fontSize: 'clamp(2rem, 5vw, 4rem)', marginTop: '1rem' }}>
          Optimal Readiness
        </motion.h2>
        <motion.p className="text-muted" variants={itemVariants} style={{ maxWidth: '600px', fontSize: '1.25rem', marginTop: '1rem' }}>
          Your central nervous system has fully recovered from yesterday's heavy load. Proceed with the planned hypertrophy protocol.
        </motion.p>
      </section>

      <section className="module-grid">
        <ActionModule 
          title="Dashboard" 
          description="Live biometrics, strain analysis, and recovery forecasting." 
          href="/dashboard" 
        />
        <ActionModule 
          title="Coach Intel" 
          description="Direct dialogue with your specialized AI training models." 
          href="/coach" 
        />
        <ActionModule 
          title="Log Archive" 
          description="Unfiltered telemetry from your past performances." 
          href="/history" 
        />
      </section>
    </motion.div>
  );
}
