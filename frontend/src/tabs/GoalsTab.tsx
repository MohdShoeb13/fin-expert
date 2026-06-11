import { useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from 'recharts'
import { api, GoalProjection } from '../api'
import { AnimatedNumber, FadeIn, Stagger, StaggerItem } from '../motion'

export default function GoalsTab() {
  const [target, setTarget] = useState(100000)
  const [years, setYears] = useState(10)
  const [monthly, setMonthly] = useState(500)
  const [initial, setInitial] = useState(5000)
  const [risk, setRisk] = useState('moderate')
  const [projection, setProjection] = useState<GoalProjection | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function plan() {
    setBusy(true)
    setError('')
    try {
      const res = await api.planGoal({
        target_amount: target,
        years,
        monthly_contribution: monthly,
        initial_amount: initial,
        risk_profile: risk,
      })
      setProjection(res.projection)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <h2>Goal Planning</h2>
      <p style={{ color: 'var(--text-dim)', margin: '6px 0 14px' }}>
        Project your savings growth under different risk profiles. Returns assumptions:
        conservative 4.5%, moderate 6.5%, aggressive 8.5% per year (historical long-run estimates,
        not guarantees).
      </p>

      <div className="form-grid">
        <label>
          Target amount ($)
          <input type="number" min={1000} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
        </label>
        <label>
          Time horizon (years)
          <input type="number" min={1} max={60} value={years} onChange={(e) => setYears(Number(e.target.value))} />
        </label>
        <label>
          Monthly contribution ($)
          <input type="number" min={0} value={monthly} onChange={(e) => setMonthly(Number(e.target.value))} />
        </label>
        <label>
          Starting amount ($)
          <input type="number" min={0} value={initial} onChange={(e) => setInitial(Number(e.target.value))} />
        </label>
        <label>
          Risk appetite
          <select value={risk} onChange={(e) => setRisk(e.target.value)}>
            <option value="conservative">Conservative (~30% stocks)</option>
            <option value="moderate">Moderate (~60% stocks)</option>
            <option value="aggressive">Aggressive (~90% stocks)</option>
          </select>
        </label>
      </div>

      <button className="primary" onClick={plan} disabled={busy}>
        {busy ? 'Projecting…' : 'Project my goal'}
      </button>

      {error && <div className="error-box">{error}</div>}

      {projection && (
        <>
          <Stagger className="metric-row">
            <StaggerItem className="metric">
              <div className="label">Projected balance</div>
              <div className={`value ${projection.goal_met ? 'green' : 'amber'}`}>
                <AnimatedNumber value={Math.round(projection.projected_final)} prefix="$" />
              </div>
            </StaggerItem>
            <StaggerItem className="metric">
              <div className="label">Goal</div>
              <div className="value">
                <AnimatedNumber value={projection.target_amount} prefix="$" />
              </div>
            </StaggerItem>
            <StaggerItem className="metric">
              <div className="label">{projection.goal_met ? 'Surplus' : 'Shortfall'}</div>
              <div className={`value ${projection.goal_met ? 'green' : 'red'}`}>
                <AnimatedNumber
                  value={Math.round(Math.abs(projection.projected_final - projection.target_amount))}
                  prefix="$"
                />
              </div>
            </StaggerItem>
            <StaggerItem className="metric">
              <div className="label">Monthly needed for goal</div>
              <div className="value">
                <AnimatedNumber value={projection.required_monthly_for_goal} prefix="$" />
              </div>
            </StaggerItem>
          </Stagger>

          <FadeIn delay={0.2}>
          <div className="chart-card" style={{ marginTop: 8 }}>
            <h3>
              Growth projection — {projection.risk_profile} profile (
              {(projection.annual_return * 100).toFixed(1)}%/yr assumed)
            </h3>
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={projection.timeline}>
                <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                <XAxis dataKey="year" stroke="#94a3b8" fontSize={11} label={{ value: 'Year', position: 'insideBottom', dy: 8, fill: '#94a3b8' }} />
                <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v: any, name: string) => [`$${Math.round(v).toLocaleString()}`, name]} />
                <Area type="monotone" dataKey="contributed" name="Contributions" stackId="1" stroke="#94a3b8" fill="#475569" />
                <Area type="monotone" dataKey="growth" name="Investment growth" stackId="1" stroke="#38bdf8" fill="#0284c7" />
                <ReferenceLine y={projection.target_amount} stroke="#fbbf24" strokeDasharray="6 4" label={{ value: 'Goal', fill: '#fbbf24', position: 'right' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          </FadeIn>

          {!projection.goal_met && (
            <FadeIn delay={0.35}>
              <div className="warning-item" style={{ marginTop: 12 }}>
                💡 To reach ${projection.target_amount.toLocaleString()} in {projection.years} years at this
                risk level, you'd need about <b>${projection.required_monthly_for_goal.toLocaleString()}/month</b> —
                or you could extend the timeline, adjust the target, or discuss trade-offs in the Chat tab.
              </div>
            </FadeIn>
          )}
        </>
      )}
    </div>
  )
}
