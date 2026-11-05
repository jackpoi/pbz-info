/**
 * 用 CDP 驱动无头 Edge 检查界面：滚动、吸顶、行数。
 *
 *   node tools/check-scroll.mjs 40
 *
 * 前置：`cd web && npm run build`。脚本会自己起一个无头浏览器，
 * 加载 web/dist/index.html#mock=<n>，然后在页面里断言：
 *   - 行数 = n
 *   - 表格容器真的可滚动（scrollHeight > clientHeight）
 *   - 滚动后 scrollTop > 0，且表头仍在视口内（吸顶）
 *   - 滚到底部时最后一行完整可见
 */

import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const ROWS = Number(process.argv[2] || 40);
const WIDTH = Number(process.argv[3] || 1180);
const HEIGHT = Number(process.argv[4] || 820);
const PORT = 9333;
const ROOT = resolve(import.meta.dirname, "..");
const PAGE = `file:///${join(ROOT, "web/dist/index.html").replace(/\\/g, "/")}#mock=${ROWS}`;

const EDGE = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
];

async function waitForTarget() {
  for (let i = 0; i < 60; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const targets = await res.json();
      const page = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) return page;
    } catch {
      /* 还没起来 */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("浏览器没有响应");
}

function cdp(url) {
  const ws = new WebSocket(url);
  let id = 0;
  const pending = new Map();
  const ready = new Promise((res, rej) => {
    ws.onopen = () => res();
    ws.onerror = (e) => rej(e);
  });
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve: done, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else done(msg.result);
    }
  };
  return {
    ready,
    send(method, params = {}) {
      id += 1;
      const myId = id;
      ws.send(JSON.stringify({ id: myId, method, params }));
      return new Promise((res, rej) => pending.set(myId, { resolve: res, reject: rej }));
    },
    close: () => ws.close(),
  };
}

async function evaluate(client, expression) {
  const { result } = await client.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.subtype === "error") throw new Error(result.description);
  return result.value;
}

async function shot(client, file) {
  const { data } = await client.send("Page.captureScreenshot", { format: "png" });
  writeFileSync(file, Buffer.from(data, "base64"));
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const profile = mkdtempSync(join(tmpdir(), "pbz-check-"));
  const browser = EDGE.find((p) => {
    try {
      return require("node:fs").existsSync(p);
    } catch {
      return false;
    }
  }) || EDGE[0];

  const child = spawn(
    browser,
    [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars=false",
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      `--window-size=${WIDTH},${HEIGHT}`,
      PAGE,
    ],
    { stdio: "ignore" },
  );

  const target = await waitForTarget();
  const client = cdp(target.webSocketDebuggerUrl);
  await client.ready;
  await client.send("Runtime.enable");
  await client.send("Page.enable");
  await sleep(1200);

  const outDir = join(ROOT, ".taste-skill");
  const info = await evaluate(
    client,
    `(() => {
      const wrap = document.querySelector('.tablewrap');
      const ledger = document.querySelector('.ledger').getBoundingClientRect();
      const rail = document.querySelector('.railcard').getBoundingClientRect();
      const badges = [...document.querySelectorAll('tbody .badge-icon')];
      const diffs = [...document.querySelectorAll('tbody td.diff')].map((td) => ({
        text: td.textContent.trim(),
        clipped: td.scrollWidth > td.clientWidth + 1,
      }));
      const times = [...document.querySelectorAll('tbody td:last-child')].map((td) => td.textContent.trim());
      const bars = [...document.querySelectorAll('tbody tr .death')].map((cell) => {
        const box = cell.getBoundingClientRect();
        const track = cell.querySelector('.bar').getBoundingClientRect();
        const fill = cell.querySelector('.bar i');
        return {
          inside: track.right <= box.right + 1,
          width: Math.round(track.width),
          fill: fill ? Math.round(fill.getBoundingClientRect().width) : 0,
        };
      });
      return {
        rows: document.querySelectorAll('tbody tr').length,
        badges: badges.length,
        diffs,
        times,
        bars,
        scrollHeight: wrap.scrollHeight,
        clientHeight: wrap.clientHeight,
        scrollTop: wrap.scrollTop,
        viewport: { w: window.innerWidth, h: window.innerHeight },
        pageScrolls: document.body.scrollHeight > window.innerHeight + 1,
        ledgerBottom: Math.round(ledger.bottom),
        railBottom: Math.round(rail.bottom),
      };
    })()`,
  );

  await shot(client, join(outDir, `long-${ROWS}-top.png`));

  const afterScroll = await evaluate(
    client,
    `(() => {
      const wrap = document.querySelector('.tablewrap');
      wrap.scrollTop = 400;
      const th = document.querySelector('thead th');
      return { scrollTop: wrap.scrollTop, thTop: th.getBoundingClientRect().top };
    })()`,
  );

  await shot(client, join(outDir, `long-${ROWS}-scrolled.png`));

  const atBottom = await evaluate(
    client,
    `(() => {
      const wrap = document.querySelector('.tablewrap');
      wrap.scrollTop = wrap.scrollHeight;
      const last = [...document.querySelectorAll('tbody tr')].at(-1);
      const box = last.getBoundingClientRect();
      const view = wrap.getBoundingClientRect();
      return {
        scrollTop: wrap.scrollTop,
        lastBottom: Math.round(box.bottom),
        viewBottom: Math.round(view.bottom),
        lastFullyVisible: box.bottom <= view.bottom + 1,
      };
    })()`,
  );

  await shot(client, join(outDir, `long-${ROWS}-bottom.png`));

  // 关于弹窗：版本号、Esc 关闭
  const about = await evaluate(
    client,
    `(async () => {
      const btn = [...document.querySelectorAll('.railcard .tail .link')]
        .find((el) => el.textContent.trim() === '关于');
      if (!btn) return { found: false };
      btn.click();
      await new Promise((r) => setTimeout(r, 120));
      const modal = document.querySelector('.modal');
      const version = document.querySelector('.about-ver')?.textContent?.trim() ?? '';
      const repoLink = document.querySelector('.about-link');
      const box = modal?.getBoundingClientRect();
      const inView = box ? box.top >= 0 && box.bottom <= window.innerHeight + 1 && box.left >= 0 && box.right <= window.innerWidth + 1 : false;
      return {
        found: true,
        open: Boolean(modal),
        version,
        inView,
        repoLink: repoLink ? { tag: repoLink.tagName, text: repoLink.textContent.trim() } : null,
        rows: [...document.querySelectorAll('.about-list .kvrow dt')].map((el) => el.textContent.trim()),
        hasCheckButton: [...document.querySelectorAll('.modal .btn')].some((el) => el.textContent.includes('检查更新')),
      };
    })()`,
  );

  await shot(client, join(outDir, `about-${ROWS}.png`));

  const aboutClosed = await evaluate(
    client,
    `(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      await new Promise((r) => setTimeout(r, 120));
      return !document.querySelector('.modal');
    })()`,
  );

  // 检查更新的成功分支：注入一个假桥，看"发布页版本 + 可更新"的呈现
  const updateText = await evaluate(
    client,
    `(async () => {
      window.pywebview = { api: { check_update: async () => ({
        ok: true, current: '0.2.0', latest: 'v9.9.9', hasUpdate: true,
        url: 'https://github.com/jackpoi/pbz-info/releases/tag/v9.9.9', publishedAt: '2026-11-06',
      }) } };
      const btn = [...document.querySelectorAll('.railcard .tail .link')].find((el) => el.textContent.trim() === '关于');
      btn.click();
      await new Promise((r) => setTimeout(r, 120));
      [...document.querySelectorAll('.modal .btn')].find((el) => el.textContent.includes('检查更新')).click();
      await new Promise((r) => setTimeout(r, 260));
      const msg = document.querySelector('.update-msg')?.textContent?.replace(/\\s+/g, ' ').trim() ?? '';
      const box = document.querySelector('.modal').getBoundingClientRect();
      return {
        msg,
        canUpdate: Boolean(document.querySelector('.can-update')),
        hasButton: [...document.querySelectorAll('.modal .btn')].some((el) => el.textContent.includes('前往发布页')),
        fits: box.bottom <= window.innerHeight + 1,
      };
    })()`,
  );

  await shot(client, join(outDir, `about-update-${ROWS}.png`));

  // 按出现顺序升序，把"一命通关"样本行（idx 1）放到第二行，便于肉眼核对徽章
  await evaluate(
    client,
    `(() => {
      document.querySelector('thead th').click();
      document.querySelector('.tablewrap').scrollTop = 0;
    })()`,
  );
  await sleep(120);
  await shot(client, join(outDir, `badge-${ROWS}-${WIDTH}.png`));

  console.log(JSON.stringify({ rows: ROWS, info, afterScroll, atBottom }, null, 2));

  const problems = [];
  if (info.rows !== ROWS) problems.push(`行数 ${info.rows} ≠ ${ROWS}`);
  if (info.scrollHeight <= info.clientHeight) problems.push("表格没有可滚动区域");
  if (!(afterScroll.scrollTop > 0)) problems.push("滚不动");
  if (Math.round(afterScroll.thTop) < 0) problems.push("表头没有吸顶");
  if (!atBottom.lastFullyVisible) problems.push("最后一行没有完整显示");
  if (info.pageScrolls) problems.push("整页出现了滚动条");
  if (info.ledgerBottom > info.viewport.h + 1) problems.push("表格面板超出窗口");
  if (info.railBottom > info.viewport.h + 1) problems.push("左侧卡超出窗口");
  if (info.badges) problems.push("徽章应当已移除");
  if (info.diffs.length !== ROWS) problems.push("难度列缺失");
  if (info.diffs.some((diff) => !diff.text || diff.text === "—")) problems.push("难度列有空值");
  if (info.diffs.some((diff) => diff.clipped)) problems.push("难度列文字被裁剪");
  if (new Set(info.diffs.map((diff) => diff.text)).size < 2) problems.push("难度列没有体现不同难度");
  if (info.bars.length !== ROWS) problems.push("死亡长度条缺失");
  if (info.bars.some((bar) => !bar.inside)) problems.push("长度条超出所在单元格");
  if (info.bars.some((bar) => bar.width < 30)) problems.push("长度条轨道过窄");
  if (info.bars.some((bar) => bar.fill > bar.width + 1)) problems.push("长度条溢出轨道");
  if (new Set(info.bars.map((bar) => bar.fill)).size < 2) problems.push("长度条没有体现长短差异");
  if (info.times.length !== ROWS) problems.push("击杀用时列缺失");
  if (info.times.some((text) => text !== "—" && !/^(\d+分)?\d+\.\d秒$/.test(text))) {
    problems.push("击杀用时不是“x分x.x秒”");
  }
  if (info.times.some((text) => text.includes(":"))) problems.push("击杀用时仍是旧格式");
  if (!about.found) problems.push("左侧卡没有「关于」入口");
  if (!about.open) problems.push("关于弹窗没有打开");
  if (!about.inView) problems.push("关于弹窗超出窗口");
  if (!/^v\d+\.\d+\.\d+/.test(about.version)) problems.push("关于弹窗没有版本号");
  if (!about.hasCheckButton) problems.push("关于弹窗没有「检查更新」按钮");
  if (about.repoLink?.tag !== "BUTTON") problems.push("项目地址不是可点击的按钮");
  if (!about.repoLink?.text.includes("github.com/jackpoi/pbz-info")) problems.push("项目地址文案不对");
  if (about.rows.includes("联网") || about.rows.includes("存档")) problems.push("联网/存档两行应当已删除");
  if (!aboutClosed) problems.push("Esc 没关掉关于弹窗");
  if (!updateText.msg.includes('v9.9.9')) problems.push(`检查更新没显示发布页版本号：${updateText.msg}`);
  if (!updateText.canUpdate) problems.push("有新版本时没有「可更新」提示");
  if (!updateText.hasButton) problems.push("有新版本时没有「前往发布页」按钮");
  if (!updateText.fits) problems.push("更新提示把弹窗撑出窗口");
  console.log(JSON.stringify({ rows: ROWS, viewport: [WIDTH, HEIGHT], problems }, null, 2));

  client.close();
  child.kill();

  if (problems.length) {
    console.error("FAIL: " + problems.join("；"));
    process.exit(1);
  }
  console.log("PASS");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
