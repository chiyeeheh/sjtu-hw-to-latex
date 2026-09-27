// 用本机 Chrome(或 Edge) 把 html/ 里的每题页面截成 PNG。
// 用法: node shoot.js <jobs.json>
//   jobs.json: {chrome, htmlDir, outDir, width, scale}
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
  const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const { chrome, htmlDir, outDir, width, scale } = cfg;

  fs.mkdirSync(outDir, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: chrome,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--font-render-hinting=none'],
  });

  const files = fs.readdirSync(htmlDir).filter(f => f.endsWith('.html')).sort();

  for (const f of files) {
    const page = await browser.newPage();
    await page.setViewport({ width, height: 800, deviceScaleFactor: scale });
    await page.goto(pathToFileURL(path.join(htmlDir, f)).href, {
      waitUntil: 'networkidle0', timeout: 60000,
    });
    await page.evaluate(() => window.MathJax.startup.promise);
    await new Promise(r => setTimeout(r, 400));

    // 超宽自检：公式被挤出画布就说一声
    const over = await page.evaluate(w => {
      let m = 0;
      document.querySelectorAll('mjx-container > svg').forEach(e => {
        m = Math.max(m, e.getBoundingClientRect().right);
      });
      return m > w - 20 ? Math.ceil(m) : 0;
    }, width);
    if (over) console.log(`WARN ${f} 有公式超宽(右边界 ${over}px)`);

    const out = path.join(outDir, f.replace(/\.html$/, '.png'));
    await (await page.$('body')).screenshot({ path: out });
    console.log(`OK ${out}`);
    await page.close();
  }

  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
