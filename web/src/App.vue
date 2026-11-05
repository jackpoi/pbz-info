<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { duration, hms, secondsAgo } from './format'
import { MOCK } from './mock'

const state = ref(null)
const error = ref(null)
const lastOkAt = ref(0)
const now = ref(Date.now())
const sortKey = ref('idx')
const sortDir = ref(-1)
const bumped = ref(new Set())
const busy = ref(false)
const hasBridge = ref(false)

const api = () => window.pywebview?.api ?? null

/* ---------------------------------------------------------------- 数据 */

function applyBumps(next) {
  const prev = state.value
  if (!prev?.bosses || !next?.bosses) return
  const before = new Map((prev.bosses || []).map((b) => [b.id, b]))
  const hits = new Set()
  for (const boss of next.bosses) {
    const old = before.get(boss.id)
    if (old && boss.deaths > old.deaths) hits.add(boss.id)
  }
  if (next.totals?.deaths > (prev.totals?.deaths ?? 0)) hits.add('__total__')
  if (hits.size) {
    bumped.value = hits
    clearTimeout(applyBumps.timer)
    applyBumps.timer = setTimeout(() => { bumped.value = new Set() }, 1400)
  }
}

function apply(res) {
  if (!res) return
  if (res.ok) {
    applyBumps(res)
    state.value = res
    error.value = null
    lastOkAt.value = Date.now()
  } else {
    error.value = res.error || { code: 'UNKNOWN', message: '未知错误' }
    // 失败但仍有上次成功的数据时，继续显示旧数据并标 stale
    if (res.cycle) {
      state.value = res
      lastOkAt.value = Date.now()
    } else {
      state.value = null
    }
  }
}

async function tick(force = false) {
  const bridge = api()
  if (!bridge) return
  try {
    apply(await bridge.get_state(force))
  } catch (err) {
    error.value = { code: 'BRIDGE', message: String(err) }
  }
}

async function refresh() {
  busy.value = true
  try {
    await tick(true)
  } finally {
    busy.value = false
  }
}

async function pick(kind) {
  const bridge = api()
  if (!bridge) return
  try {
    const res = await bridge[kind]()
    if (res?.path) await tick(true)
  } catch (err) {
    error.value = { code: 'DIALOG', message: String(err) }
  }
}

async function oneShot(method) {
  const bridge = api()
  if (!bridge) return
  try {
    await bridge[method]()
  } catch { /* 用户取消 */ }
}

/* ---------------------------------------------------------------- 派生 */

const bosses = computed(() => state.value?.bosses ?? [])
const cycle = computed(() => state.value?.cycle ?? null)
const totals = computed(() => state.value?.totals ?? null)
const meta = computed(() => state.value?.meta ?? null)

const maxDeaths = computed(() => Math.max(0, ...bosses.value.map((b) => b.deaths)))

const rows = computed(() => {
  const list = [...bosses.value]
  const key = sortKey.value
  const dir = sortDir.value
  list.sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (av == null && bv == null) return b.deaths - a.deaths || (a.id < b.id ? -1 : 1)
    if (av == null) return 1
    if (bv == null) return -1
    const diff = av > bv ? 1 : av < bv ? -1 : 0
    return diff * dir || b.deaths - a.deaths || (a.id < b.id ? -1 : 1)
  })
  return list
})

const worstText = computed(() => {
  const w = totals.value?.worst
  if (!w) return ''
  return `${w.name || w.id} · ${w.deaths} 次死亡`
})

const updatedText = computed(() =>
  lastOkAt.value ? `已更新 ${secondsAgo(lastOkAt.value, now.value)}` : '等待数据',
)

const stampText = computed(() => {
  if (!lastOkAt.value) return '未读取'
  if (error.value && state.value) return '数据已过期'
  return updatedText.value
})

const diffText = computed(() => {
  const c = cycle.value
  if (!c) return '–'
  return c.difficultyName || `难度 ${c.difficulty}`
})

const staleText = computed(() => {
  if (!meta.value?.savedAt) return ''
  return `显示的是 ${meta.value.savedAt} 的数据`
})

const needExe = computed(() => error.value?.code === 'NEED_EXE')
const noData = computed(() => !state.value)

function setSort(key) {
  if (sortKey.value === key) sortDir.value = -sortDir.value
  else {
    sortKey.value = key
    sortDir.value = -1
  }
  api()?.set_view?.(sortKey.value, sortDir.value)
}

function diffLabel(row) {
  if (row.difficultyName) return row.difficultyName
  if (row.difficulty != null) return `难度 ${row.difficulty}`
  return '—'
}

async function loadViewPrefs() {
  const bridge = api()
  if (!bridge?.get_config) return
  try {
    const cfg = await bridge.get_config()
    const view = cfg?.view
    if (view?.sort) {
      sortKey.value = view.sort
      sortDir.value = view.dir ?? -1
    }
  } catch { /* 首次运行没有配置 */ }
}

/* ---------------------------------------------------------------- 生命周期 */

let dataTimer = null
let clockTimer = null

onMounted(() => {
  hasBridge.value = Boolean(api())
  clockTimer = setInterval(() => { now.value = Date.now() }, 500)
  if (hasBridge.value) {
    loadViewPrefs()
    tick()
    dataTimer = setInterval(() => tick(), 1000)
  } else {
    // vite dev：没有 pywebview，用样本数据
    state.value = MOCK
    lastOkAt.value = Date.now()
  }
  window.addEventListener('pywebviewready', onReady)
})

function onReady() {
  hasBridge.value = true
  tick(true)
  if (!dataTimer) dataTimer = setInterval(() => tick(), 1000)
}

onBeforeUnmount(() => {
  clearInterval(dataTimer)
  clearInterval(clockTimer)
  window.removeEventListener('pywebviewready', onReady)
})
</script>

<template>
  <header class="topbar">
    <svg class="mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4.5 19.5 19 5" stroke="#d24a32" stroke-width="2.4" stroke-linecap="round" />
      <path d="M14 4h6v6" stroke="#d24a32" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M4 12.5h6.5" stroke="#6b5f54" stroke-width="1.6" stroke-linecap="round" />
    </svg>
    <div class="wordmark">影之刃零</div>
    <div class="spacer"></div>
    <div v-if="meta?.steamId" class="scope" title="Steam 账号">
      <span>Steam</span><b>{{ meta.steamId }}</b>
    </div>
    <div class="stamp">{{ stampText }}</div>
    <button class="btn" type="button" :disabled="busy" @click="refresh">刷新</button>
  </header>

  <main class="canvas">
    <!-- 无数据：整页状态 -->
    <section v-if="noData" class="statepage">
      <h2>{{ needExe ? '需要一次密钥' : '没有读到存档' }}</h2>
      <p v-if="needExe">
        存档是加密的，密钥来自游戏的 <span class="code">PBZ.exe</span>。
        选一次之后会记在这台机器上，以后不用再选。
      </p>
      <p v-else-if="error?.code === 'NO_GAME'">
        没有在 Steam 库里找到《影之刃零》。这不影响使用——直接选一个存档文件或存档目录即可。
      </p>
      <p v-else-if="error">{{ error.message }}</p>
      <p v-else>尚未选择存档。</p>
      <div class="actions">
        <button v-if="needExe" class="btn primary" type="button" @click="pick('pick_exe')">选择 PBZ.exe</button>
        <button class="btn" type="button" @click="pick('pick_save_file')">选择存档文件</button>
        <button class="btn" type="button" @click="pick('pick_save_folder')">选择存档目录</button>
        <button class="btn" type="button" @click="refresh">重试</button>
      </div>
    </section>

    <template v-else>
      <div v-if="error" class="banner" :title="error.code">
        <strong>{{ error.code === 'NEED_EXE' ? '缺少密钥' : '读取失败' }}</strong>
        <span>{{ staleText }}</span>
        <span class="spacer"></span>
        <button v-if="error.code === 'NEED_EXE'" class="link" type="button" @click="pick('pick_exe')">选择 PBZ.exe</button>
        <button class="link" type="button" @click="refresh">重试</button>
      </div>

      <div class="titlerow">
        <h1>生涯战绩</h1>
        <div class="sub" v-if="totals?.worst">
          最难的一关 <span>{{ worstText }}</span>
        </div>
      </div>

      <section class="kpis" aria-label="本周目总览">
        <div class="kpi">
          <div class="label">本周目时长</div>
          <div class="value">{{ cycle ? hms(cycle.cycleTime) : '–' }}</div>
        </div>
        <div class="kpi">
          <div class="label">总死亡</div>
          <div class="value" :class="{ bump: bumped.has('__total__') }">
            {{ totals ? totals.deaths : '–' }}<span class="unit">次</span>
          </div>
        </div>
        <div class="kpi">
          <div class="label">Boss 死亡合计</div>
          <div class="value">{{ totals ? totals.bossDeaths : '–' }}<span class="unit">次</span></div>
        </div>
        <div class="kpi">
          <div class="label">已击败 Boss</div>
          <div class="value">{{ totals ? totals.killed : '–' }}<span class="unit">个</span></div>
        </div>
      </section>

      <div class="grid">
        <section class="panel railcard" aria-label="本周目与数据来源">
          <header><h2>本周目</h2></header>
          <dl style="margin: 0">
            <div class="kvrow"><dt>周目</dt><dd>{{ cycle ? `第 ${cycle.index} 周目` : '–' }}</dd></div>
            <div class="kvrow"><dt>当前难度</dt><dd :title="`DifficultModeByte = ${cycle?.difficulty}`">{{ diffText }}</dd></div>
            <div class="kvrow"><dt>通关状态</dt><dd>{{ cycle ? (cycle.finished ? '已通关' : '未通关') : '–' }}</dd></div>
            <div class="kvrow"><dt>当前关卡</dt><dd class="mono">{{ cycle?.level || '–' }}</dd></div>
            <div class="kvrow"><dt>存档点</dt><dd class="mono">{{ cycle?.bell || '–' }}</dd></div>
            <div class="kvrow"><dt>剩余天数</dt><dd>{{ cycle ? `${cycle.remainingDays} 天` : '–' }}</dd></div>
            <div class="kvrow"><dt>累计游玩</dt><dd class="num">{{ cycle ? hms(cycle.totalTime) : '–' }}</dd></div>
          </dl>

          <dl style="margin: 0">
            <div class="kvrow sep"><dt>存档槽位</dt><dd class="mono">{{ meta?.slot || '–' }}</dd></div>
            <div class="kvrow"><dt>保存时间</dt><dd class="num">{{ meta?.savedAt || '–' }}</dd></div>
            <div class="kvrow"><dt>存档文件</dt><dd class="mono" :title="meta?.savePath">{{ meta?.fileName || '–' }}</dd></div>
            <div v-if="meta && meta.source !== 'main'" class="kvrow">
              <dt>来源</dt>
              <dd>{{ meta.source === 'snapshot' ? '实时快照' : '指定文件' }}</dd>
            </div>
          </dl>

          <p class="note">
            <template v-if="meta?.unmapped">{{ meta.unmapped }} 个 Boss 的内部 ID 尚未映射中文名；</template>
            历史周目战绩可能被游戏覆盖，本面板只保证当前周目准确。
          </p>

          <div class="tail">
            <button class="link" type="button" @click="pick('pick_save_file')">切换存档</button>
            <button class="link" type="button" @click="oneShot('open_save_dir')">打开目录</button>
            <button
              v-if="meta && meta.source !== 'main'"
              class="link"
              type="button"
              @click="oneShot('use_main_save')"
            >回到主存档</button>
          </div>
        </section>

        <section class="panel ledger" aria-labelledby="boss-h">
          <header>
            <h2 id="boss-h">Boss 战绩</h2>
            <span class="count">{{ bosses.length }} 个 · 合计死亡 {{ totals?.bossDeaths ?? 0 }}</span>
          </header>
          <div class="tablewrap">
          <table>
            <colgroup>
              <col />
              <col style="width: 200px" />
              <col style="width: 88px" />
              <col style="width: 80px" />
              <col style="width: 90px" />
            </colgroup>
            <thead>
              <tr>
                <th data-sort="idx" @click="setSort('idx')">
                  Boss<span v-if="sortKey === 'idx'" class="arrow">{{ sortDir > 0 ? '↑' : '↓' }}</span>
                </th>
                <th class="num col-death" data-sort="deaths" @click="setSort('deaths')">
                  <span class="hlabel">死亡<span v-if="sortKey === 'deaths'" class="arrow">{{ sortDir > 0 ? '↑' : '↓' }}</span></span>
                </th>
                <th class="col-state" data-sort="kill" @click="setSort('kill')">
                  击杀<span v-if="sortKey === 'kill'" class="arrow">{{ sortDir > 0 ? '↑' : '↓' }}</span>
                </th>
                <th
                  class="col-diff"
                  data-sort="difficulty"
                  title="该条战绩发生时的难度，击杀后即为击杀难度"
                  @click="setSort('difficulty')"
                >
                  难度<span v-if="sortKey === 'difficulty'" class="arrow">{{ sortDir > 0 ? '↑' : '↓' }}</span>
                </th>
                <th class="num" data-sort="bestMs" @click="setSort('bestMs')">
                  击杀用时<span v-if="sortKey === 'bestMs'" class="arrow">{{ sortDir > 0 ? '↑' : '↓' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.id"
                :class="{
                  'is-top': row.deaths === maxDeaths && maxDeaths > 0,
                  bump: bumped.has(row.id),
                }"
              >
                <td>
                  <div class="boss" :class="{ 'is-unknown': !row.name }" :title="row.id">
                    <span v-if="row.name" class="name">{{ row.name }}</span>
                    <span v-else class="id">{{ row.id }}</span>
                  </div>
                </td>
                <td class="num">
                  <div class="death">
                    <span class="v num">{{ row.deaths }}</span>
                    <span class="bar" aria-hidden="true">
                      <i v-if="row.deaths > 0" :style="{ width: `${(row.deaths / maxDeaths) * 100}%` }" />
                    </span>
                  </div>
                </td>
                <td class="state">
                  <template v-if="row.kill > 0">已击杀</template>
                  <svg
                    v-if="row.firstTry"
                    class="badge-icon"
                    data-badge="firstTry"
                    viewBox="0 0 16 16"
                    role="img"
                    aria-label="一命通关"
                  >
                    <title>一命通关</title>
                    <path
                      d="M8 1.7l1.9 4.2 4.6.5-3.4 3.1.9 4.5L8 11.9 4 14l.9-4.5L1.5 6.4l4.6-.5L8 1.7Z"
                      fill="currentColor"
                    />
                  </svg>
                </td>
                <td
                  class="diff"
                  :title="row.kill > 0 ? '击杀这个 Boss 时使用的难度' : '遭遇这个 Boss 时使用的难度'"
                >{{ diffLabel(row) }}</td>
                <td class="num">
                  <span v-if="row.bestMs != null">{{ duration(row.bestMs) }}</span>
                  <span v-else class="dash">—</span>
                </td>
              </tr>
              <tr v-if="!rows.length">
                <td colspan="5" class="empty">本周目还没有 Boss 记录</td>
              </tr>
            </tbody>
          </table>
          </div>
        </section>
      </div>
    </template>
  </main>
</template>
