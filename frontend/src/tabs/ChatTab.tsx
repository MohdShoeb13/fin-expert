import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { api, Citation } from '../api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  agent?: string
  citations?: Citation[]
}

const AGENT_LABELS: Record<string, string> = {
  finance_qa: 'Finance Q&A',
  portfolio_analysis: 'Portfolio Analyst',
  market_analysis: 'Market Analyst',
  goal_planning: 'Goal Planner',
  news_synthesizer: 'News Desk',
  tax_education: 'Tax Educator',
}

const SUGGESTIONS = [
  'What is compound interest?',
  'How is Apple stock doing today?',
  'I want to save $100k in 10 years — can I do it with $500/month?',
  'How are capital gains taxed?',
  "What's the latest market news?",
]

const WELCOME: Message = {
  role: 'assistant',
  content:
    "👋 Hi! I'm your AI finance education assistant. I'm backed by six specialized agents " +
    'covering general questions, portfolio analysis, live market data, goal planning, news, ' +
    'and taxes. Ask me anything — or try a suggestion below!',
  agent: 'finance_qa',
}

export default function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([WELCOME])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sessionId] = useState(() => `web-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  async function send(text?: string) {
    const message = (text ?? input).trim()
    if (!message || busy) return
    setInput('')
    setError('')
    setMessages((m) => [...m, { role: 'user', content: message }])
    setBusy(true)
    try {
      const res = await api.chat(message, sessionId)
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: res.content, agent: res.agent, citations: res.citations },
      ])
    } catch (e: any) {
      setError(e.message || 'Something went wrong — please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel chat-window">
      <div className="chat-messages">
        {messages.map((m, i) => (
          <motion.div
            key={i}
            className={`msg ${m.role}`}
            initial={{ opacity: 0, y: 14, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
          >
            {m.role === 'assistant' && m.agent && (
              <span className="agent-badge">{AGENT_LABELS[m.agent] ?? m.agent}</span>
            )}
            {m.role === 'assistant' ? <ReactMarkdown>{m.content}</ReactMarkdown> : m.content}
            {m.citations && m.citations.length > 0 && (
              <div className="citations">
                📚 Sources: {m.citations.map((c) => c.title).join(' · ')}
              </div>
            )}
          </motion.div>
        ))}
        {busy && (
          <motion.div
            className="msg assistant typing"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="chat-input">
        <input
          value={input}
          placeholder="Ask about investing, your portfolio, the market, goals, or taxes…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          disabled={busy}
        />
        <button className="primary" onClick={() => send()} disabled={busy || !input.trim()}>
          Send
        </button>
      </div>

      {messages.length === 1 && <div className="suggestions-hint">✨ Try one of these to get started:</div>}
      <div className="chat-suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => send(s)} disabled={busy}>
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
