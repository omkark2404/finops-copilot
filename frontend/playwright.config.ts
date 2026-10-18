import {defineConfig} from '@playwright/test'
import path from 'node:path'
import {mkdtempSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
const dataDir=mkdtempSync(path.join(tmpdir(),'finops-browser-'))
process.once('exit',()=>rmSync(dataDir,{recursive:true,force:true}))
const python=process.env.FINOPS_PYTHON || path.resolve('../backend/.venv/bin/python')
export default defineConfig({
  testDir:'./tests',
  fullyParallel:false,
  workers:1,
  retries:0,
  use:{baseURL:'http://127.0.0.1:38179',trace:'retain-on-failure',
    launchOptions:{executablePath:process.env.FINOPS_CHROMIUM,args:process.env.FINOPS_CHROMIUM?['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-zygote','--single-process']:[]}},
  webServer:[
    {command:python+' -m uvicorn app.main:app --host 127.0.0.1 --port 38180',cwd:'../backend',
      url:'http://127.0.0.1:38180/health',timeout:60000,reuseExistingServer:false,
      env:{APP_ENV:'test',DATA_DIR:dataDir,USE_LOCAL_SQLITE:'true',
        JWT_SECRET_KEY:'browser-test-only-secret-at-least-32-characters',
        ADMIN_EMAIL:'browser@test.local',ADMIN_PASSWORD:'browser-test-password-123',GEMINI_API_KEY:'',
        CORS_ORIGINS:'http://127.0.0.1:38179',COOKIE_SECURE:'false',COOKIE_SAMESITE:'lax'}},
    {command:'npm run build && npm start -- --port 38179 --hostname 127.0.0.1',url:'http://127.0.0.1:38179/login',
      timeout:120000,reuseExistingServer:false,env:{NEXT_PUBLIC_API_URL:'http://127.0.0.1:38180',NEXT_TELEMETRY_DISABLED:'1'}},
  ],
})
