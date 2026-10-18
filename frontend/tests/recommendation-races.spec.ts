import {test,expect} from './fixtures'
const A='11111111-1111-4111-8111-111111111111'
const B='22222222-2222-4222-8222-222222222222'
for(const operation of ['decision','simulate'] as const){
  for(const status of [200,500]){
    test(`stale ${operation} ${status} cannot alter a newer dataset`,async({page,context})=>{
      const auth=await context.request.post('http://127.0.0.1:38180/auth/login',{data:{email:'browser@test.local',password:'browser-test-password-123'}})
      expect(auth.status()).toBe(200)
      await context.addInitScript(id=>localStorage.setItem('finops.datasetId',id),A)
      const recommendation=(id:string)=>({id,title:id==='a-rec'?'A recommendation':'B recommendation',description:'SYNTHETIC UI FIXTURE',evidence:[],status:'pending',risk_level:'low'})
      await page.route('**/datasets',route=>route.fulfill({json:[{id:A,name:'Dataset A',row_count:40},{id:B,name:'Dataset B',row_count:40}]}))
      await page.route('**/recommendations?*',route=>route.fulfill({json:[recommendation(new URL(route.request().url()).searchParams.get('dataset_id')===A?'a-rec':'b-rec')]}))
      let releaseA!:()=>void
      let releaseB!:()=>void
      const gateA=new Promise<void>(resolve=>{releaseA=resolve})
      const gateB=new Promise<void>(resolve=>{releaseB=resolve})
      await page.route(`**/recommendations/*/${operation}`,async route=>{
        const isA=route.request().url().includes('/a-rec/')
        await (isA?gateA:gateB)
        await route.fulfill({status:isA?status:200,json:isA&&status===500?{detail:'stale A failure'}:operation==='decision'?{status:'approved'}:{scope:isA?'STALE A SCENARIO':'B scenario result',period_start:'2024-01-01',period_end:'2024-01-31',current_cost:100,projected_cost:90,estimated_savings:10,currency:'USD',assumptions:[]}})
      })
      try{
        await page.goto('/recommendations')
        await expect(page.getByRole('heading',{name:'A recommendation',exact:true})).toBeVisible()
        const send=async()=>{
          if(operation==='decision')await page.getByRole('button',{name:'Record approval',exact:true}).click()
          else{
            await page.getByText('Hypothetical whole-dataset scenario',{exact:true}).click()
            await page.getByLabel('Assumed usage reduction (%)').fill('10')
            await page.getByRole('button',{name:'Simulate scenario',exact:true}).click()
          }
        }
        const startedA=page.waitForRequest(r=>r.url().includes(`/a-rec/${operation}`))
        const endedA=page.waitForResponse(r=>r.url().includes(`/a-rec/${operation}`))
        await send();await startedA
        await page.getByRole('combobox',{name:'Active billing dataset'}).selectOption(B)
        await expect(page.getByRole('heading',{name:'B recommendation',exact:true})).toBeVisible()
        const startedB=page.waitForRequest(r=>r.url().includes(`/b-rec/${operation}`))
        const endedB=page.waitForResponse(r=>r.url().includes(`/b-rec/${operation}`))
        await send();await startedB
        releaseA()
        await (await endedA).finished()
        // Flush queued React paints after the response body, while B's request stays pending.
        await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))))
        await expect(page.getByRole('heading',{name:'B recommendation',exact:true})).toBeVisible()
        await expect(page.getByText('stale A failure',{exact:false})).toHaveCount(0)
        await expect(page.getByText('STALE A SCENARIO',{exact:true})).toHaveCount(0)
        await expect(page.getByRole('button',{name:operation==='decision'?'Record approval':'Simulate scenario',exact:true})).toBeDisabled()
        releaseB();await (await endedB).finished()
        await expect(page.getByRole('button',{name:'Record approval',exact:true})).toBeEnabled()
        if(operation==='simulate')await expect(page.getByText('B scenario result',{exact:true})).toBeVisible()
      }finally{releaseA();releaseB()}
    })
  }
}
