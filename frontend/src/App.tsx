import { useState } from 'react'
import ChatTab from './tabs/ChatTab'
import PortfolioTab from './tabs/PortfolioTab'
import MarketTab from './tabs/MarketTab'
import GoalsTab from './tabs/GoalsTab'

const TABS = ['Chat', 'Portfolio', 'Market', 'Goals'] as const
type Tab = (typeof TABS)[number]

export default function App() {
  const [tab, setTab] = useState<Tab>('Chat')

  return (
    <>
      <header className="header">
        <h1>💰 AI Finance Assistant</h1>
        <p className="subtitle">
          Learn investing with a team of specialized AI agents — Q&amp;A, portfolio
          analysis, live markets, goal planning, news, and tax education.
        </p>
      </header>

      <div className="disclaimer-banner">
        ⚠️ Educational purposes only — not financial advice. Consult a licensed
        financial advisor before making investment decisions.
      </div>

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </nav>

      <main>
        <div style={{ display: tab === 'Chat' ? 'block' : 'none' }}>
          <ChatTab />
        </div>
        {tab === 'Portfolio' && <PortfolioTab />}
        {tab === 'Market' && <MarketTab />}
        {tab === 'Goals' && <GoalsTab />}
      </main>
    </>
  )
}
