import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "Fitness Bridge",
  description: "Minimalist multi-agent fitness coaching.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="true" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;700;900&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="app-container">
          <nav className="minimal-nav">
            <div className="nav-inner">
              <Link href="/" className="nav-brand">
                 Fitness<span>Bridge</span>
              </Link>
              <div style={{ display: 'flex', gap: '2rem' }}>
                <Link href="/" className="nav-button">
                   Home
                </Link>
                <Link href="/settings" className="nav-button">
                  Settings
                </Link>
              </div>
            </div>
          </nav>
          <main className="main-content">
            {children}
          </main>
          <footer style={{ padding: "4rem 0 2rem", textAlign: "center", borderTop: "1px solid var(--card-border)", marginTop: "auto" }}>
            <p className="text-muted" style={{ fontSize: "0.75rem", letterSpacing: "0.05em", textTransform: "uppercase" }}>
              Fitness Bridge &bull; 2026
            </p>
          </footer>
        </div>
      </body>
    </html>
  );
}
