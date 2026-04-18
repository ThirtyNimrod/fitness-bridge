"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API = "http://127.0.0.1:8000";

export default function CoachChat() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [routingTo, setRoutingTo] = useState(null);
  const scrollRef = useRef(null);

  // 1. Initialize session on load
  useEffect(() => {
    async function initChat() {
      try {
        // Try to get latest session
        const sessionsRes = await fetch(`${API}/api/sessions`);
        const sessionsData = await sessionsRes.json();
        
        if (sessionsData.sessions?.length > 0) {
          const latest = sessionsData.sessions[0];
          setSessionId(latest.id);
          // Load messages? Optional, but let's start fresh for now or implement load if database supports it
        } else {
          // Create new session
          const createRes = await fetch(`${API}/api/sessions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "Fitness Consultation" })
          });
          const createData = await createRes.json();
          setSessionId(createData.session_id);
        }
      } catch (e) {
        console.error("Failed to init chat session", e);
      }
    }
    initChat();
  }, []);

  // 2. Scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);
    setRoutingTo("Analyzing intent...");

    try {
      const res = await fetch(`${API}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMessage })
      });
      
      const data = await res.json();
      if (res.ok) {
        setMessages(prev => [...prev, { role: "assistant", content: data.response, agent: data.agent }]);
      } else {
        setMessages(prev => [...prev, { role: "assistant", content: "Sorry, I encountered an error processing that request." }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: "Connection to coaching engine failed." }]);
    } finally {
      setLoading(false);
      setRoutingTo(null);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", width: "100%", height: "100%" }}>
      <header style={{ marginBottom: "2rem", textAlign: "center" }}>
        <h1 className="title">AI Coach</h1>
        <p className="text-muted">Direct consultation with multi-agent fitness specialists.</p>
      </header>

      <div className="card chat-container">
        <div className="chat-messages" ref={scrollRef}>
          {messages.length === 0 && !loading && (
             <div style={{ textAlign: 'center', marginTop: '4rem' }}>
                <p className="text-muted">How can I assist your training today?</p>
                <p className="text-muted" style={{ fontSize: '0.8125rem', marginTop: '0.5rem' }}>
                  Try asking: "Should I train today based on my recovery?" or "What was my total volume this week?"
                </p>
             </div>
          )}
          
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              <div style={{ 
                fontSize: '0.65rem', 
                textTransform: 'uppercase', 
                letterSpacing: '0.05em',
                marginBottom: '0.25rem',
                color: 'var(--muted-foreground)'
              }}>
                {m.role === "user" ? "Athlete" : (m.agent || "Coach")}
              </div>
              <div style={{ 
                background: m.role === "user" ? "rgba(255,255,255,0.03)" : "transparent",
                padding: m.role === "user" ? "0.75rem 1rem" : "0",
                borderRadius: "var(--radius)",
                border: m.role === "user" ? "1px solid var(--card-border)" : "none",
                display: "inline-block",
                textAlign: "left"
              }}>
                {m.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message assistant">
               <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem', color: 'var(--muted-foreground)' }}>
                 {routingTo || "Coach"}
               </div>
               <motion.div
                 animate={{ opacity: [0.3, 1, 0.3] }}
                 transition={{ repeat: Infinity, duration: 1.5 }}
                 className="text-muted"
               >
                 Thinking...
               </motion.div>
            </div>
          )}
        </div>

        <form className="chat-input-wrapper" onSubmit={handleSend}>
          <input
            type="text"
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={loading || !sessionId}
          />
          <button type="submit" disabled={loading || !input.trim() || !sessionId}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
