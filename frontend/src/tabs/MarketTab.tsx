import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { api, HistoryPoint, Quote } from '../api'
import { AnimatedNumber, FadeIn, Stagger, StaggerItem } from '../motion'

const POPULAR = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'VTI']
const PERIODS = ['1mo', '3mo', '6mo', '1y', '5y']

function fmtBig(n: number | null): string {
  if (n == null) return '—'
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`
  return `$${n.toLocaleString()}`
}

export default function MarketTab() {
  const [symbol, setSymbol] = useState('SPY')
  const [input, setInput] = useState('SPY')
  const [period, setPeriod] = useState('6mo')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [news, setNews] = useState<Array<Record<string, string>>>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setBusy(true)
      setError('')
      try {
        const [data, newsData] = await Promise.all([
          api.marketQuote(symbol, period),
          api.marketNews(symbol).catch(() => ({ articles: [] }) as any),
        ])
        if (cancelled) return
        setQuote(data.quote)
        setHistory(data.history)
        setNews(newsData.articles ?? [])
      } catch (e: any) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setBusy(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [symbol, period])

  return (
    <div className="panel">
      <h2>Market Overview</h2>

      <div style={{ display: 'flex', gap: 8, margin: '14px 0', flexWrap: 'wrap' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && input.trim() && setSymbol(input.trim())}
          placeholder="Ticker e.g. AAPL"
          style={{
            background: 'var(--panel-light)', border: '1px solid var(--border)',
            color: 'var(--text)', borderRadius: 8, padding: '9px 12px', width: 140,
          }}
        />
        <button className="primary" onClick={() => input.trim() && setSymbol(input.trim())} disabled={busy}>
          Look up
        </button>
        {POPULAR.map((s) => (
          <button key={s} className="ghost" onClick={() => { setInput(s); setSymbol(s) }}>
            {s}
          </button>
        ))}
      </div>

      {error && <div className="error-box">{error}</div>}
      {busy && <div className="spinner">Loading {symbol}…</div>}

      {quote && !busy && (
        <>
          <Stagger className="metric-row">
            <StaggerItem className="metric">
              <div className="label">{quote.name || quote.symbol}</div>
              <div className="value">
                <AnimatedNumber value={quote.price} prefix="$" decimals={2} />
              </div>
            </StaggerItem>
            <StaggerItem className="metric">
              <div className="label">Today</div>
              <div className={`value ${quote.change_percent >= 0 ? 'green' : 'red'}`}>
                {quote.change_percent >= 0 ? '+' : ''}{quote.change_percent.toFixed(2)}%
              </div>
            </StaggerItem>
            <StaggerItem className="metric">
              <div className="label">Market cap</div>
              <div className="value">{fmtBig(quote.market_cap)}</div>
            </StaggerItem>
            <StaggerItem className="metric">
              <div className="label">P/E ratio</div>
              <div className="value">{quote.pe_ratio ? quote.pe_ratio.toFixed(1) : '—'}</div>
            </StaggerItem>
            <StaggerItem className="metric">
              <div className="label">52-week range</div>
              <div className="value" style={{ fontSize: '1rem' }}>
                {quote.fifty_two_week_low ? `$${quote.fifty_two_week_low.toFixed(0)} – $${quote.fifty_two_week_high?.toFixed(0)}` : '—'}
              </div>
            </StaggerItem>
          </Stagger>

          {quote.stale && (
            <div className="stale-note">
              ⚠️ Live data unavailable — showing the most recent cached price ({new Date(quote.as_of).toLocaleString()}).
            </div>
          )}

          <FadeIn delay={0.15}>
          <div className="chart-card" style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>{symbol} — closing price</h3>
              <div style={{ display: 'flex', gap: 4 }}>
                {PERIODS.map((p) => (
                  <button
                    key={p}
                    className="ghost"
                    style={p === period ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}
                    onClick={() => setPeriod(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={history}>
                <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} minTickGap={40} />
                <YAxis stroke="#94a3b8" fontSize={11} domain={['auto', 'auto']} />
                <Tooltip formatter={(v: any) => [`$${v}`, 'Close']} />
                <Line type="monotone" dataKey="close" stroke="#38bdf8" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <div style={{ color: 'var(--text-dim)', fontSize: '0.75rem', marginTop: 6 }}>
              Data: {quote.provider} · as of {new Date(quote.as_of).toLocaleString()}
            </div>
          </div>
          </FadeIn>

          {news.length > 0 && (
            <FadeIn delay={0.25}>
            <div style={{ marginTop: 18 }}>
              <h3 style={{ marginBottom: 6 }}>Recent news</h3>
              {news.slice(0, 6).map((n, i) => (
                <div key={i} className="news-item">
                  <a href={n.link || '#'} target="_blank" rel="noreferrer">{n.title}</a>
                  <div className="meta">{n.publisher}</div>
                </div>
              ))}
            </div>
            </FadeIn>
          )}
        </>
      )}
    </div>
  )
}
