export function hms(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  return [h, m, ss].map((n) => String(n).padStart(2, '0')).join(':')
}

export function duration(ms) {
  if (ms == null) return ''
  // 击杀用时按 0.1 秒取整：95 分钟这种长局也只需要一位小数
  const tenths = Math.max(0, Math.round(ms / 100))
  const minutes = Math.floor(tenths / 600)
  const seconds = (tenths % 600) / 10
  const text = seconds.toFixed(1).padStart(4, '0')
  return minutes > 0 ? `${minutes}分${text}秒` : `${text}秒`
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
