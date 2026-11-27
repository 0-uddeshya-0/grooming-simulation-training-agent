const { chromium } = require('playwright'); const out = (process.argv[2]||'.');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1366,height:768}});const errs=[];
p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>m.type()==='error'&&errs.push(m.text()));
const say=async t=>{await p.fill('#inp',t);await p.press('#inp','Enter')};
await p.goto('http://127.0.0.1:8123/');await p.screenshot({path:out+'/n_gate.png'});
await p.click('#next1');console.log('err1:',await p.textContent('#err1'));
await p.check('#c1');await p.check('#c2');await p.click('#next1');await p.fill('#pid','T042');await p.click('#go');
await p.screenshot({path:out+'/n_welcome.png'});
await p.click('.thread >> nth=0');await say('hey, who is this?');await p.waitForTimeout(1900);await p.screenshot({path:out+'/n_typing.png'});
await p.waitForSelector('.them .bubble:not(.typing)',{timeout:8000});await p.waitForTimeout(500);await say('i love music, just moved here');await p.waitForFunction(()=>document.querySelectorAll('.row.them .bubble:not(.typing)').length>=2,null,{timeout:9000});await p.waitForTimeout(3500);
await p.screenshot({path:out+'/n_chat.png'});
// multi-thread: start Sam, send, switch back before reply -> unread dot on Sam
await p.click('.thread >> nth=2');await p.waitForSelector('.head h3:text("Sam")');await say('hello sam');await p.waitForTimeout(300);await p.click('.thread >> nth=0');await p.waitForTimeout(4500);
console.log('unread dot on sam:',await p.locator('.thread >> nth=2').locator('.dot').count());
await p.screenshot({path:out+'/n_threads.png'});
// stop alex
await p.click('#stop');await p.waitForSelector('text=What just happened',{timeout:8000});await p.screenshot({path:out+'/n_debrief.png'});
await p.evaluate(()=>document.querySelector('.scroll').scrollTo(0,900));await p.screenshot({path:out+'/n_debrief2.png'});
await p.click('[data-w=bad]');
// distress on sam
await p.click('.thread >> nth=2');await p.waitForSelector('#inp');await say('i want to kill myself');await p.waitForSelector('.card.support',{timeout:8000});await p.screenshot({path:out+'/n_distress.png'});
await p.click('#sumbtn');await p.waitForSelector('text=Overall summary',{timeout:8000});await p.waitForTimeout(400);await p.screenshot({path:out+'/n_summary.png'});
// STOP text on jordan
await p.click('.thread >> nth=1');await p.waitForSelector('.head h3:text("Jordan")');await say('STOP');await p.waitForSelector('text=What just happened',{timeout:8000});
console.log('timer text present:',await p.locator('text=/\\d+:\\d\\d/').count(),'| errors:',errs.length?errs:'none');await b.close()})();
