const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1366,height:768}});const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.goto('http://127.0.0.1:8124/');await p.check('#c1');await p.check('#c2');await p.click('#next1');await p.fill('#pid','TT1');await p.click('#go');
await p.click('.thread >> nth=0');await p.waitForSelector('.head h3:text("Alex")');await p.fill('#inp','hi');await p.press('#inp','Enter');
const t0=Date.now();await p.waitForSelector('text=What just happened',{timeout:90000});
console.log('idle timeout -> debrief after',Math.round((Date.now()-t0)/1000),'s; support card shown:',await p.locator('.card.support').count(),'| errors:',errs.length?errs:'none');await b.close()})();
