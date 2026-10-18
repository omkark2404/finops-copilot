import {test as base,expect,chromium} from '@playwright/test'

// Optional serverless Chromium exits when its last context closes in single-process mode.
// Keep normal Playwright/CI fixtures; use a fresh browser per test only for that fallback.
export const test=process.env.FINOPS_CHROMIUM?base.extend({
  context:async({launchOptions,contextOptions,baseURL},provide)=>{
    const browser=await chromium.launch(launchOptions)
    try{
      const context=await browser.newContext({...contextOptions,baseURL})
      await provide(context)
    }finally{await browser.close()}
  },
}):base
export {expect}
