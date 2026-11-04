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
      return {
        rows: document.querySelectorAll('tbody tr').length,
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
