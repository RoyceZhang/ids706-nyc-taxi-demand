// Local-only screenshot capture, run after verify_local.py. No fixture or mock data.
// npm install --no-save --package-lock=false --prefix /tmp/ids706-capture playwright
// npx --prefix /tmp/ids706-capture playwright install chromium
// NODE_PATH is not used by ESM; provide PLAYWRIGHT_MODULE as below.
// PLAYWRIGHT_MODULE=/tmp/ids706-capture/node_modules/playwright/index.mjs node screenshots/capture.mjs
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE || '/tmp/ids706-capture/node_modules/playwright/index.mjs'))
const out = path.dirname(fileURLToPath(import.meta.url))
const browser = await chromium.launch()
try {
  const page = await browser.newPage({ viewport: {width:1600,height:1100} })
  await page.goto('http://127.0.0.1:8088/login/')
  await page.locator('#username').fill(process.env.AIRFLOW_ADMIN_USER || 'admin')
  await page.locator('#password').fill(process.env.AIRFLOW_ADMIN_PASSWORD || 'admin')
  await page.locator('input[type=submit],button[type=submit]').click()
  await page.goto('http://127.0.0.1:8088/dags/nyc_taxi_demand/grid')
  await page.getByText('nyc_taxi_demand',{exact:true}).first().waitFor()
  await page.screenshot({path:path.join(out,'airflow_success.png'),fullPage:true})
  await page.goto('http://127.0.0.1:8088/dags/nyc_taxi_demand/graph')
  await page.getByText('nyc_taxi_demand',{exact:true}).first().waitFor()
  await page.screenshot({path:path.join(out,'airflow_graph.png'),fullPage:true})
  await page.goto('http://127.0.0.1:5173/solution-loop')
  const dataset = page.locator('select').filter({has:page.locator('option[value="taxi_hourly.csv"]')})
  await dataset.selectOption('taxi_hourly.csv')
  await page.getByRole('button',{name:'Run loop',exact:true}).click()
  await page.getByTestId('evaluation-results').waitFor({timeout:180000})
  await page.screenshot({path:path.join(out,'evaluation_results.png'),fullPage:true})
  await page.locator('.react-flow').first().scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(out,'agent_graph.png'),fullPage:true})
  console.log('Captured four genuine screenshots. Review each before submission.')
} finally { await browser.close() }
