// Thin typed client over the FastAPI backend.

export interface Holding {
  symbol: string
  shares: number
  asset_type: string
}

export interface Citation {
  title: string
  source: string
  category: string
  score: number
}

export interface ChatResponse {
  content: string
  agent: string
  route: string
  citations: Citation[]
  data: Record<string, any>
}

export interface Quote {
  symbol: string
  price: number
  change: number
  change_percent: number
  currency: string
  name: string
  market_cap: number | null
  pe_ratio: number | null
  dividend_yield: number | null
  fifty_two_week_high: number | null
  fifty_two_week_low: number | null
  provider: string
  as_of: string
  stale: boolean
}

export interface HistoryPoint {
  date: string
  close: number
}

export interface PortfolioAnalysis {
  total_value: number
  holdings: Array<{
    symbol: string
    name: string
    shares: number
    price: number
    value: number
    allocation_pct: number
    asset_type: string
    change_percent: number
  }>
  allocation_by_type: Record<string, number>
  diversification_score: number
  risk_score: number
  risk_level: string
  warnings: string[]
}

export interface ProjectionPoint {
  year: number
  balance: number
  contributed: number
  growth: number
}

export interface GoalProjection {
  target_amount: number
  years: number
  risk_profile: string
  annual_return: number
  projected_final: number
  goal_met: boolean
  shortfall: number
  required_monthly_for_goal: number
  timeline: ProjectionPoint[]
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  chat: (message: string, sessionId: string, holdings?: Holding[]) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId, holdings }),
    }),

  analyzePortfolio: (holdings: Holding[]) =>
    request<PortfolioAnalysis>('/api/portfolio/analyze', {
      method: 'POST',
      body: JSON.stringify({ holdings }),
    }),

  marketQuote: (symbol: string, period = '6mo') =>
    request<{ quote: Quote; history: HistoryPoint[] }>(
      `/api/market/${encodeURIComponent(symbol)}?period=${period}`,
    ),

  marketNews: (symbol: string) =>
    request<{ symbol: string; articles: Array<Record<string, string>> }>(
      `/api/market/${encodeURIComponent(symbol)}/news`,
    ),

  planGoal: (params: {
    target_amount: number
    years: number
    monthly_contribution: number
    initial_amount: number
    risk_profile: string
  }) =>
    request<{ projection: GoalProjection }>('/api/goals/plan', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
}
