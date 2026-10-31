import {defineConfig} from 'vite'; import react from '@vitejs/plugin-react'
// Local dev: run `uvicorn app.main:app --reload` (port 8000); Vite forwards /api to it.
export default defineConfig({plugins:[react()],server:{proxy:{'/api':{target:'http://127.0.0.1:8000',rewrite:p=>p.replace(/^\/api/,'')}}}})
