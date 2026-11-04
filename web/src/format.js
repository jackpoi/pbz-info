export function hms(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  return [h, m, ss].map((n) => String(n).padStart(2, '0')).join(':')
}

export function duration(ms) {
  if (ms == null) return ''
  const m = Math.floor(ms / 60000)
  const rest = ms % 60000
  const s = Math.floor(rest / 1000)
  const milli = rest % 1000
  return `${m}:${String(s).padStart(2, '0')}.${String(milli).padStart(3, '0')}`
}

export function secondsAgo(ms, current = Date.now()) {
  if (!ms) return ''
  const diff = Math.max(0, Math.round((current - ms) / 1000))
  if (diff < 2) return '刚刚'
  if (diff < 60) return `${diff} 秒前`
  const m = Math.floor(diff / 60)
  if (m < 60) return `${m} 分钟前`
  return `${Math.floor(m / 60)} 小时前`
}
