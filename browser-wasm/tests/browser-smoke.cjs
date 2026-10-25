// SPDX-License-Identifier: MIT
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, 'cases.json'))).cases;
const selected = fixtures.filter(c => ['initial','one-move','main-n12-s202610250000000','missing-center','paper-two-placement-unreachable'].includes(c.id));
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {}), args:['--disable-gpu']});
  const errors = [], requests = [], results = [];
  try {
    const page = await browser.newPage({viewport:{width:390,height:850}});
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => requests.push(request.url()));
    await page.goto(process.env.OTHELLO_PREVIEW_URL || 'http://127.0.0.1:18773/');
    await page.waitForSelector('#solve');
    for (const fixture of selected) {
      const result = await page.evaluate(board => new Promise((resolve, reject) => {
        const worker = new Worker(new URL('solver-worker.js',location.href)), stages=[];
        const timer = setTimeout(()=>{worker.terminate();reject(Error('observational smoke deadline; no reachability verdict'));},120000);
        worker.onerror = event => {clearTimeout(timer);worker.terminate();reject(Error(event.message));};
        worker.onmessage = event => {
          if(event.data.type==='progress') stages.push(event.data.stage);
          else if(event.data.type==='result') {
            clearTimeout(timer);worker.terminate();
            if(event.data.status==='found') RetroRules.verify(event.data.moves,board);
            resolve({...event.data,stages});
          }
        };
        worker.postMessage({type:'solve',board});
      }), fixture.board);
      assert.equal(result.status, fixture.expected==='reachable'?'found':'unreachable',fixture.id+':'+JSON.stringify(result));
      results.push({id:fixture.id,...result});
      console.log(JSON.stringify({id:fixture.id,status:result.status,seconds:result.wall_seconds}));
    }
    for(const width of [320,390,1200]) {
      await page.setViewportSize({width,height:850});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'horizontal overflow');
    }
    assert.equal(requests.filter(u=>/\/api\//.test(u)).length,0,'backend request');
    assert.deepEqual(errors,[]);
    const report={status:'passed',results,page_errors:errors,api_requests:0,requests,viewports:[320,390,1200],browser:'Chromium'};
    const out=path.join(__dirname,'../validation');fs.mkdirSync(out,{recursive:true});
    fs.writeFileSync(path.join(out,'browser-smoke.json'),JSON.stringify(report,null,2)+'\n');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
