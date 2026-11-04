// vite dev 下没有 pywebview，用样本数据把界面填起来，
// 这样改样式不需要每次重启窗口。
// 注意：这里的数据全部是虚构的，不要从真实存档里拷数值。
export const MOCK = {
  ok: true,
  meta: {
    source: 'main',
    savePath: 'C:\\SteamLibrary\\steamapps\\common\\PBZ\\ProjectPBZ\\Saved\\SaveGames\\Steam\\12345678901234567\\PBZSaveGame.sav',
    fileName: 'PBZSaveGame.sav',
    steamId: '12345678901234567',
    slot: 'AutoSave0',
    savedAt: '2025-01-01 12:00:00',
    readAt: '2025-01-01 12:00:05',
    unmapped: 0,
    stale: false,
  },
  cycle: {
    index: 1,
    difficulty: 3,
    difficultyName: '逆天者',
    finished: false,
    level: 'PBZ_Fujizhilin_WP',
    bell: 'Bell_LZSJ_003',
    remainingDays: 42,
    cycleTime: 12345,
    totalTime: 12345,
  },
  totals: {
    deaths: 33,
    bossDeaths: 30,
    killed: 8,
    worst: { id: 'BP_Monster_MoTian_LongZhu_01', name: '金面具黑衣人', deaths: 10 },
  },
  bosses: [
    { id: 'BP_Monster_ZuoShang', name: '组织冥主：左殇', idx: 0, attempt: 2, kill: 1, deaths: 1, bestMs: 180000 },
    { id: 'BP_Monster_HookMan_HorseCartCombat', name: '猎杀者：追命（序章版）', idx: 1, attempt: 1, kill: 1, deaths: 0, bestMs: 45000 },
    { id: 'BP_Monster_YuCong_FirstTime', name: '三张脸的诡异魔偶', idx: 2, attempt: 1, kill: 0, deaths: 1, bestMs: null },
    { id: 'BP_Monster_MobMan_Elite_Sword', name: '痴狂暴徒：残钢', idx: 3, attempt: 3, kill: 1, deaths: 2, bestMs: 120000 },
    { id: 'BP_Monster_PengMeng_Axe', name: '斧老大：彭猛', idx: 4, attempt: 3, kill: 1, deaths: 2, bestMs: 150000 },
    { id: 'BP_Monster_AHua_GuiTouDao', name: '新娘阿花', idx: 5, attempt: 5, kill: 1, deaths: 4, bestMs: 200000 },
    { id: 'BP_Monster_HookMan', name: '猎杀者：追命', idx: 6, attempt: 2, kill: 1, deaths: 1, bestMs: 100000 },
    { id: 'BP_Monster_HookMan_P2', name: '追命：六绝凶镰', idx: 7, attempt: 4, kill: 1, deaths: 3, bestMs: 160000 },
    { id: 'BP_Monster_MoTian_LongZhu_01', name: '金面具黑衣人', idx: 8, attempt: 11, kill: 1, deaths: 10, bestMs: 300000 },
    { id: 'BP_Monster_HuaQianXIao', name: '剑痴：花千笑', idx: 9, attempt: 6, kill: 0, deaths: 6, bestMs: null },
  ],
}

/**
 * 只在开发时用：`index.html#mock=40` 会把样本重复铺到 40 条，
 * 方便验证「Boss 很多」时的滚动与吸顶表头。生产构建里没人会带这个 hash。
 */
const wanted = Number(new URLSearchParams(location.hash.slice(1)).get('mock'))
if (Number.isFinite(wanted) && wanted > MOCK.bosses.length) {
  const base = MOCK.bosses
  const extra = []
  for (let i = base.length; i < wanted; i += 1) {
    const source = base[i % base.length]
    extra.push({
      ...source,
      id: `${source.id}_${i}`,
      name: `${source.name} ${i + 1}`,
      idx: i,
      deaths: (i * 5) % 24,
      attempt: (i * 5) % 24 + 1,
      kill: i % 3 === 0 ? 0 : 1,
    })
  }
  MOCK.bosses = [...base, ...extra]
  MOCK.totals.bossDeaths = MOCK.bosses.reduce((sum, b) => sum + b.deaths, 0)
  MOCK.totals.deaths = MOCK.totals.bossDeaths + 3
  MOCK.totals.killed = MOCK.bosses.filter((b) => b.kill > 0).length
}
