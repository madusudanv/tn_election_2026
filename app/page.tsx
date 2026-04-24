import { createClient } from '@/utils/supabase/server'
import { cookies } from 'next/headers'

type SentimentLabel = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'

type PartyBucket = {
  name: string
  latinKeywords: string[]
  nativeKeywords: string[]
}

type PartyStat = {
  pos: number
  neg: number
  neu: number
  total: number
}

const PARTY_BUCKETS: PartyBucket[] = [
  {
    name: 'TVK (Vijay)',
    latinKeywords: ['tvk', 'vijay', 'thalapathy', 'tamizhaga vettri kazhagam'],
    nativeKeywords: ['தவெக', 'விஜய்', 'தளபதி', 'தமிழக வெற்றிக் கழகம்']
  },
  {
    name: 'DMK',
    latinKeywords: ['dmk', 'stalin', 'mk stalin', 'udhayanidhi', 'udayanidhi'],
    nativeKeywords: ['திமுக', 'ஸ்டாலின்', 'மு க ஸ்டாலின்', 'உதயநிதி']
  },
  {
    name: 'AIADMK + BJP/NDA',
    latinKeywords: ['aiadmk', 'admk', 'eps', 'edappadi', 'edappadi palaniswami', 'bjp', 'nda', 'modi', 'annamalai', 'pmk'],
    nativeKeywords: ['அதிமுக', 'எடப்பாடி', 'எடப்பாடி பழனிசாமி', 'பாஜக', 'என்டிஏ', 'மோடி', 'அண்ணாமலை', 'பாமக']
  },
  {
    name: 'NTK (Seeman)',
    latinKeywords: ['ntk', 'seeman', 'naam tamilar', 'naam tamilar katchi'],
    nativeKeywords: ['நாம் தமிழர்', 'நாம் தமிழர் கட்சி', 'சீமான்']
  }
]

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const hasLatinKeyword = (text: string, keywords: string[]) => {
  if (keywords.length === 0) return false
  const pattern = keywords.map(escapeRegExp).join('|')
  const regex = new RegExp(`(^|[^a-z])(?:${pattern})(?=$|[^a-z])`, 'i')
  return regex.test(text)
}

const getMatchingPartyBuckets = (text: string) => {
  const normalized = text.toLowerCase()

  return PARTY_BUCKETS
    .filter((bucket) => {
      const latinMatch = hasLatinKeyword(normalized, bucket.latinKeywords)
      const nativeMatch = bucket.nativeKeywords.some((keyword) => normalized.includes(keyword.toLowerCase()))
      return latinMatch || nativeMatch
    })
    .map((bucket) => bucket.name)
}

export default async function Dashboard() {
  const cookieStore = await cookies()
  const supabase = createClient(cookieStore)

  const { data: feedComments } = await supabase
    .from('voter_sentiment')
    .select('*')
    .order('published_at', { ascending: false })
    .limit(50)

  // Paginate through all rows so party favorability uses the full dataset
  let statComments: { comment_text: string | null; sentiment_label: string | null; parties: string[] | null }[] = []
  const PAGE_SIZE = 1000
  let page = 0
  while (true) {
    const { data: chunk } = await supabase
      .from('voter_sentiment')
      .select('comment_text, sentiment_label, parties')
      .range(page * PAGE_SIZE, (page + 1) * PAGE_SIZE - 1)
    if (!chunk || chunk.length === 0) break
    statComments = statComments.concat(chunk)
    if (chunk.length < PAGE_SIZE) break
    page++
  }

  const { count: totalComments } = await supabase
    .from('voter_sentiment')
    .select('*', { count: 'exact', head: true })

  const sentiments = statComments?.reduce((acc: Record<string, number>, curr: { sentiment_label?: string | null }) => {
    const label = curr.sentiment_label || 'Pending'
    acc[label] = (acc[label] || 0) + 1
    return acc
  }, {}) || {}

  const totalAnalyzed = Object.values(sentiments).reduce((a, b) => a + b, 0)

  const partyStats = PARTY_BUCKETS.reduce<Record<string, PartyStat>>((acc, bucket) => {
    acc[bucket.name] = { pos: 0, neg: 0, neu: 0, total: 0 }
    return acc
  }, {})

  statComments?.forEach((comment) => {
    const parties = comment.parties

    if (!parties || !Array.isArray(parties)) return

    parties.forEach((partyDataStr) => {
      if (typeof partyDataStr === 'string' && partyDataStr.startsWith('{')) {
        try {
          const parsed = JSON.parse(partyDataStr);
          Object.entries(parsed).forEach(([partyName, sentiment]) => {
            if (!partyStats[partyName]) return
            partyStats[partyName].total += 1
            if (sentiment === 'POSITIVE') partyStats[partyName].pos += 1
            else if (sentiment === 'NEGATIVE') partyStats[partyName].neg += 1
            else partyStats[partyName].neu += 1
          });
        } catch (e) { }
      } else {
        // Fallback for old simple string array
        const party = partyDataStr;
        const label = comment.sentiment_label as SentimentLabel | null;
        if (!label || !['POSITIVE', 'NEGATIVE', 'NEUTRAL'].includes(label)) return;
        if (!partyStats[party]) return
        partyStats[party].total += 1
        if (label === 'POSITIVE') partyStats[party].pos += 1
        else if (label === 'NEGATIVE') partyStats[party].neg += 1
        else partyStats[party].neu += 1
      }
    })
  })

  const getSentimentColor = (label: string) => {
    const normalized = label.toLowerCase()
    if (normalized.includes('pos')) return '#4ade80'
    if (normalized.includes('neg')) return '#f87171'
    return '#94a3b8'
  }

  return (
    <div className="dashboard-container">
      <header className="header">
        <div className="title-group">
          <h1>TN Election 2026 Pulse</h1>
          <p>Real-time Voter Sentiment Monitoring Dashboard</p>
        </div>
        <div className="status-indicator">
          <span className="channel-tag" style={{ background: 'rgba(74, 222, 128, 0.1)', color: '#4ade80' }}>
            ● NLP Pipeline Active
          </span>
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <p className="stat-label">Total Mentions</p>
          <p className="stat-value">{totalComments || 0}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Positive Sentiment</p>
          <p className="stat-value">
            {totalAnalyzed > 0
              ? Math.round(((sentiments.POSITIVE || sentiments.LABEL_1 || 0) / totalAnalyzed) * 100)
              : 0}%
          </p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Negative Sentiment</p>
          <p className="stat-value">
            {totalAnalyzed > 0
              ? Math.round(((sentiments.NEGATIVE || sentiments.LABEL_0 || 0) / totalAnalyzed) * 100)
              : 0}%
          </p>
        </div>
      </div>

      <div className="main-content">
        <section className="feed-container">
          <h2 className="section-title"><span>💬</span> Live Interactivity Feed</h2>

          {feedComments?.map((comment: any) => (
            <div key={comment.id} className="comment-card">
              <div className="comment-header">
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span className="author">{comment.author_name}</span>
                  <span className="channel-tag">{comment.channel_name}</span>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {comment.parties && comment.parties.length > 0 && comment.parties.map((partyDataStr: string, idx: number) => {
                    let pName = partyDataStr;
                    let pSent = comment.sentiment_label;
                    if (typeof partyDataStr === 'string' && partyDataStr.startsWith('{')) {
                      try {
                        const parsed = JSON.parse(partyDataStr);
                        pName = Object.keys(parsed)[0];
                        pSent = Object.values(parsed)[0];
                      } catch (e) { }
                    }
                    return (
                      <span
                        key={idx}
                        className="channel-tag"
                        style={{
                          background: 'rgba(148, 163, 184, 0.1)',
                          color: pSent === 'POSITIVE' ? '#4ade80' : pSent === 'NEGATIVE' ? '#f87171' : '#94a3b8',
                          borderColor: '#334155',
                          border: '1px solid'
                        }}
                      >
                        {pName}
                      </span>
                    )
                  })}
                  <span
                    className="channel-tag"
                    style={{
                      background: `${getSentimentColor(comment.sentiment_label || '')}22`,
                      color: getSentimentColor(comment.sentiment_label || ''),
                      borderColor: `${getSentimentColor(comment.sentiment_label || '')}44`,
                      border: '1px solid'
                    }}
                  >
                    {comment.sentiment_label || 'Pending'}
                  </span>
                </div>
              </div>
              <p className="comment-text">{comment.comment_text}</p>
              <div className="comment-footer">
                <span>{new Date(comment.published_at).toLocaleString()}</span>
                <span>Confidence: {Math.round((comment.sentiment_score || 0) * 100)}%</span>
              </div>
            </div>
          ))}
        </section>

        <aside className="sidebar">
          <div className="chart-card">
            <h2 className="section-title">Sentiment Distribution</h2>
            {Object.entries(sentiments).map(([label, count]) => (
              <div key={label} className="sentiment-bar-container">
                <div className="bar-label">
                  <span>{label}</span>
                  <span>{Math.round((count / totalAnalyzed) * 100)}%</span>
                </div>
                <div className="bar-bg">
                  <div
                    className="bar-fill"
                    style={{
                      width: `${(count / totalAnalyzed) * 100}%`,
                      background: getSentimentColor(label)
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="chart-card">
            <h2 className="section-title">Party Favorability</h2>
            {Object.entries(partyStats).map(([party, stats]) => {
              if (stats.total === 0) return null
              const posPct = Math.round((stats.pos / stats.total) * 100)
              const negPct = Math.round((stats.neg / stats.total) * 100)
              const neuPct = 100 - posPct - negPct

              return (
                <div key={party} className="sentiment-bar-container" style={{ marginBottom: '1.5rem' }}>
                  <div className="bar-label">
                    <span style={{ fontWeight: 600 }}>{party}</span>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Mentions: {stats.total}</span>
                  </div>
                  <div style={{ display: 'flex', height: '10px', borderRadius: '5px', overflow: 'hidden', background: '#334155' }}>
                    <div style={{ width: `${posPct}%`, background: '#4ade80' }} title={`Positive: ${posPct}%`} />
                    <div style={{ width: `${neuPct}%`, background: '#94a3b8' }} title={`Neutral: ${neuPct}%`} />
                    <div style={{ width: `${negPct}%`, background: '#f87171' }} title={`Negative: ${negPct}%`} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginTop: '0.5rem' }}>
                    <span style={{ color: '#4ade80' }}>{posPct}% Pos</span>
                    <span style={{ color: '#94a3b8' }}>{neuPct}% Neu</span>
                    <span style={{ color: '#f87171' }}>{negPct}% Neg</span>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="chart-card">
            <h2 className="section-title">NLP Analytics</h2>
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Using code-mixed Tanglish sentiment classification with party-level mention bucketing.
              Short Latin keywords are matched as standalone tokens to avoid substring collisions like ADMK being counted as DMK.
              AIADMK and BJP/NDA mentions are grouped into a single coalition bucket.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}
