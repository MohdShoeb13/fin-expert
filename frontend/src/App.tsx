import { useState } from 'react'
import { motion, MotionConfig } from 'framer-motion'
import ChatTab from './tabs/ChatTab'
import PortfolioTab from './tabs/PortfolioTab'
import MarketTab from './tabs/MarketTab'
import GoalsTab from './tabs/GoalsTab'

const TABS = ['Chat', 'Portfolio', 'Market', 'Goals'] as const
type Tab = (typeof TABS)[number]

export default function App() {
  const [tab, setTab] = useState<Tab>('Chat')

  return (
    <MotionConfig reducedMotion="user">
      <motion.header
        className="header"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1>💰 AI Finance Assistant</h1>
        <p className="subtitle">
          Learn investing with a team of specialized AI agents — Q&amp;A, portfolio
          analysis, live markets, goal planning, news, and tax education.
        </p>
      </motion.header>

      <motion.div
        className="disclaimer-banner"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.15 }}
      >
        ⚠️ Educational purposes only — not financial advice. Consult a licensed
        financial advisor before making investment decisions.
      </motion.div>

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>
            {t === tab && (
              <motion.span
                layoutId="tab-pill"
                className="tab-pill"
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}
              />
            )}
            <span className="tab-label">{t}</span>
          </button>
        ))}
      </nav>

      <main>
        {/* Chat stays mounted so the conversation survives tab switches. */}
        <div style={{ display: tab === 'Chat' ? 'block' : 'none' }}>
          <ChatTab />
        </div>
        {tab !== 'Chat' && (
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            {tab === 'Portfolio' && <PortfolioTab />}
            {tab === 'Market' && <MarketTab />}
            {tab === 'Goals' && <GoalsTab />}
          </motion.div>
        )}
      </main>
    </MotionConfig>
  )
}
