import { useState } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
} from 'recharts'
import { api, Holding, PortfolioAnalysis } from '../api'

const COLORS = ['#38bdf8', '#4ade80', '#fbbf24', '#f87171', '#a78bfa', '#fb923c', '#2dd4bf', '#f472b6']

const ASSET_TYPES = [
  { value: 'stock', label: 'Individual stock' },
  { value: 'stock_etf', label: 'Stock ETF / fund' },
  { value: 'bond_etf', label: 'Bond ETF / fund' },
  { value: 'reit_etf', label: 'REIT' },
  { value: 'cash', label: 'Cash' },
  { value: 'crypto', label: 'Crypto' },
]

const SAMPLE: Holding[] = [
  { symbol: 'VTI', shares: 30, asset_type: 'stock_etf' },
  { symbol: 'VXUS', shares: 25, asset_type: 'stock_etf' },
  { symbol: 'BND', shares: 20, asset_type: 'bond_etf' },
]

export default function PortfolioTab() {
  const [holdings, setHoldings] = useState<Holding[]>(SAMPLE)
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function update(i: number, field: keyof Holding, value: string) {
    setHoldings((h) =>
      h.map((row, idx) =>
        idx === i ? { ...row, [field]: field === 'shares' ? Number(value) : value } : row,
      ),
    )
  }

  async function analyze() {
    setBusy(true)
    setError('')
    try {
      const valid = holdings.filter((h) => h.symbol.trim() && h.shares > 0)
      if (valid.length === 0) throw new Error('Add at least one holding with a symbol and shares.')
      setAnalysis(await api.analyzePortfolio(valid))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <h2>Portfolio Analysis</h2>
      <p style={{ color: 'var(--text-dim)', margin: '6px 0 14px' }}>
        Enter your holdings and get live valuation, allocation, diversification, and risk metrics.
      </p>

      <table className="holdings-table">
        <thead>
          <tr><th>Symbol</th><th>Shares</th><th>Type</th><th></th></tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <tr key={i}>
              <td>
                <input
                  value={h.symbol}
                  onChange={(e) => update(i, 'symbol', e.target.value.toUpperCase())}
                  style={{ width: 110 }}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={0}
                  value={h.shares || ''}
                  onChange={(e) => update(i, 'shares', e.target.value)}
                  style={{ width: 110 }}
                />
              </td>
              <td>
                <select value={h.asset_type} onChange={(e) => update(i, 'asset_type', e.target.value)}>
                  {ASSET_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </td>
              <td>
                <button className="ghost" onClick={() => setHoldings((rows) => rows.filter((_, idx) => idx !== i))}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button
          className="ghost"
          onClick={() => setHoldings((h) => [...h, { symbol: '', shares: 0, asset_type: 'stock' }])}
        >
          + Add holding
        </button>
        <button className="primary" onClick={analyze} disabled={busy}>
          {busy ? 'Analyzing…' : 'Analyze portfolio'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {analysis && (
        <>
          <div className="metric-row">
            <div className="metric">
              <div className="label">Total value</div>
              <div className="value">${analysis.total_value.toLocaleString()}</div>
            </div>
            <div className="metric">
              <div className="label">Diversification</div>
              <div className={`value ${analysis.diversification_score > 60 ? 'green' : analysis.diversification_score > 30 ? 'amber' : 'red'}`}>
                {analysis.diversification_score}/100
              </div>
            </div>
            <div className="metric">
              <div className="label">Risk score</div>
              <div className="value">{analysis.risk_score}/100</div>
            </div>
            <div className="metric">
              <div className="label">Risk level</div>
              <div className={`value ${analysis.risk_level === 'Aggressive' ? 'red' : analysis.risk_level === 'Moderate' ? 'amber' : 'green'}`}>
                {analysis.risk_level}
              </div>
            </div>
          </div>

          <div className="charts-row">
            <div className="chart-card">
              <h3>Allocation by holding</h3>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={analysis.holdings}
                    dataKey="allocation_pct"
                    nameKey="symbol"
                    label={(e: any) => `${e.symbol} ${e.allocation_pct}%`}
                    outerRadius={90}
                  >
                    {analysis.holdings.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: any) => `${v}%`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-card">
              <h3>Allocation by asset type</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={Object.entries(analysis.allocation_by_type).map(([type, pct]) => ({ type, pct }))}
                >
                  <XAxis dataKey="type" stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} unit="%" />
                  <Tooltip formatter={(v: any) => `${v}%`} />
                  <Bar dataKey="pct" fill="#38bdf8" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <table className="holdings-table">
            <thead>
              <tr><th>Symbol</th><th>Name</th><th>Shares</th><th>Price</th><th>Value</th><th>Allocation</th><th>Day</th></tr>
            </thead>
            <tbody>
              {analysis.holdings.map((h) => (
                <tr key={h.symbol}>
                  <td>{h.symbol}</td>
                  <td>{h.name}</td>
                  <td>{h.shares}</td>
                  <td>${h.price.toLocaleString()}</td>
                  <td>${h.value.toLocaleString()}</td>
                  <td>{h.allocation_pct}%</td>
                  <td style={{ color: h.change_percent >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {h.change_percent >= 0 ? '+' : ''}{h.change_percent.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {analysis.warnings.length > 0 && (
            <div className="warning-list">
              {analysis.warnings.map((w, i) => (
                <div key={i} className="warning-item">⚠️ {w}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
