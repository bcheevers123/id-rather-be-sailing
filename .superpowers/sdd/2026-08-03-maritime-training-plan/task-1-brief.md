### Task 1: Repository scaffold and tooling

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `package.json`
- Create: `vite.config.ts`
- Create: `tsconfig.json`
- Create: `tailwind.config.ts`
- Create: `src/main.tsx`
- Create: `src/App.tsx`
- Create: `index.html`
- Create: `.gitignore`
- Create: `pipeline/__init__.py`
- Create: `pipeline/adapters/__init__.py`
- Create: `tests/pipeline/.gitkeep`
- Create: `tests/frontend/.gitkeep`
- Create: `src/data/.gitkeep`

**Interfaces:**
- Produces: working `npm run dev` (Vite dev server) and `pytest` (zero tests, zero failures)

- [ ] **Step 1: Create `requirements.txt`**

```
pdfplumber==0.11.4
requests==2.32.3
beautifulsoup4==4.12.3
lxml==5.2.2
jsonschema==4.23.0
python-dateutil==2.9.0
pytest==8.3.2
pytest-cov==5.0.0
responses==0.25.3
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --tb=short
```

- [ ] **Step 3: Create `package.json`**

```json
{
  "name": "id-rather-be-sailing",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src --ext ts,tsx"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.1",
    "fuse.js": "^7.0.0",
    "react-big-calendar": "^1.13.1",
    "date-fns": "^3.6.0",
    "clsx": "^2.1.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@types/react-big-calendar": "^1.8.9",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.3",
    "vite": "^5.4.1",
    "vitest": "^2.0.5",
    "@vitest/coverage-v8": "^2.0.5",
    "jsdom": "^24.1.1",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.8",
    "tailwindcss": "^3.4.9",
    "postcss": "^8.4.41",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.9.0",
    "@typescript-eslint/eslint-plugin": "^8.0.1",
    "@typescript-eslint/parser": "^8.0.1"
  }
}
```

- [ ] **Step 4: Create `vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/id-rather-be-sailing/',
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
  build: {
    outDir: 'dist',
  },
})
```

- [ ] **Step 5: Create `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 6: Create `tailwind.config.ts`**

```typescript
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f4ff',
          100: '#e0e9ff',
          600: '#1e3a6e',
          700: '#162d5a',
          800: '#0f2044',
          900: '#081530',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
```

- [ ] **Step 7: Create `index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>I'd Rather Be Sailing — MCA Maritime Training Finder</title>
    <meta name="description" content="Find MCA-approved maritime training courses, approved centres, upcoming dates and prices." />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Create `src/main.tsx`**

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 9: Create `src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 10: Create `src/App.tsx` (stub)**

```typescript
export default function App() {
  return <div className="min-h-screen bg-white"><p>Loading…</p></div>
}
```

- [ ] **Step 11: Create `src/test-setup.ts`**

```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 12: Create pipeline stubs**

```bash
touch pipeline/__init__.py pipeline/adapters/__init__.py
mkdir -p tests/pipeline/fixtures tests/frontend src/data src/types src/lib src/components src/views
touch src/data/.gitkeep
```

- [ ] **Step 13: Create `.gitignore`**

```
node_modules/
dist/
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.env
coverage/
.coverage
```

- [ ] **Step 14: Install dependencies and verify**

```bash
pip install -r requirements.txt
npm install
npm run build
pytest  # should collect 0 items, exit 0
```

Expected: build succeeds, `pytest` exits 0 with "no tests ran".

- [ ] **Step 15: Commit**

```bash
git add -A
git commit -m "feat: project scaffold — Python pipeline + React/Vite/Tailwind frontend"
```

---
