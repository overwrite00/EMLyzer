# 🎨 Frontend — EMLyzer React Dashboard

Modern, responsive web interface for email threat analysis built with **React 19** and **Vite 8**.

> [!NOTE]
> This directory contains the React web application. For backend setup, see [../README.md](../README.md).

---

## 📊 Quick Overview

| 🔧 Technology | 📝 Details |
|---|---|
| **Framework** | React 19 |
| **Build Tool** | Vite 8 |
| **Styling** | CSS Grid + Flexbox (no external UI libraries) |
| **HTTP Client** | Axios with 60s timeout |
| **Localization** | Italian (it) & English (en) |
| **Bundle** | Pre-compiled (`backend/static/`) |

---

## 🚀 Running the Frontend

### 💻 Development Mode

**Requires Node.js 18+**

```bash
npm install
npm run dev
```

Opens **http://localhost:5173** (Vite dev server with HMR)

---

### 📦 Production Build

```bash
npm run build
```

Generates:
- `dist/index.html`
- `dist/assets/index.js`
- `dist/assets/index.css`

Output is copied to `backend/static/` by `start.sh`/`start.bat`.

---

## 📁 Project Structure

```
frontend/
├── src/
│   ├── App.jsx                # Root React component
│   ├── pages/
│   │   └── Dashboard.jsx      # Main analysis interface
│   ├── components/
│   │   ├── UploadZone.jsx     # Drag-and-drop file upload
│   │   ├── AnalysisDetail.jsx # Results panel with tabs
│   │   ├── TabHeader.jsx      # SPF/DKIM/DMARC analysis
│   │   ├── TabBody.jsx        # Content & NLP analysis
│   │   ├── TabURL.jsx         # URL list & risk assessment
│   │   ├── TabAttachment.jsx  # Attachment analysis
│   │   ├── TabReputation.jsx  # Threat intelligence
│   │   ├── CampaignsPanel.jsx # Campaign clustering
│   │   └── ... (more components)
│   ├── i18n/
│   │   ├── LangContext.jsx    # Localization provider
│   │   └── translations.js    # 160+ translations (it/en)
│   ├── api/
│   │   └── client.js          # Axios instance + API functions
│   └── index.css              # Global styles
├── public/                    # Static assets
├── vite.config.js             # Vite configuration
├── package.json               # Dependencies
└── README.md                  # This file
```

---

## 🔧 Building & Deployment

### Build Process

1. **Development:** `npm run dev` (Vite dev server)
2. **Production:** `npm run build` (generates optimized bundle)
3. **Output location:** `backend/static/` (served by FastAPI)

### ⚙️ Important Configuration

**vite.config.js:**
```javascript
export default {
  build: {
    outDir: '../backend/static',
    rollupOptions: {
      output: {
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/index.css'
      }
    }
  }
}
```

> [!IMPORTANT]
> Fixed file names ensure FastAPI can serve them correctly. Do NOT change these names.

---

## 🌍 Localization

Translations managed via **LangContext**:

**File:** `src/i18n/translations.js`

```javascript
const translations = {
  en: {
    "dashboard.title": "Email Analyzer",
    "header.spf_pass": "SPF authentication passed",
    // ... 160+ keys
  },
  it: {
    "dashboard.title": "Analizzatore Email",
    "header.spf_pass": "Autenticazione SPF superata",
    // ... 160+ keys (Italian)
  }
}
```

**Usage in components:**
```jsx
import { useLanguage } from '../i18n/LangContext';

export function MyComponent() {
  const { t } = useLanguage();
  return <h1>{t('dashboard.title')}</h1>;
}
```

---

## 📡 API Integration

**File:** `src/api/client.js`

All backend calls go through Axios with standardized error handling:

```javascript
// Upload email
const response = await client.post('/upload/', formData);
const job_id = response.data.job_id;

// Run analysis
const result = await client.post(`/analysis/${job_id}`);

// Check reputation status
const updated = await client.get(`/analysis/${job_id}`);
```

**Timeout:** 60s for normal requests, 300s for analysis (can take time).

---

## 🎨 Styling

**No external UI library.** Uses:
- CSS Grid for layouts
- Flexbox for alignment
- CSS variables for theming
- Mobile-first responsive design

**Main stylesheet:** `src/index.css`

### Color Scheme

| 🎨 Color | 📝 Purpose |
|---|---|
| `#0066cc` | Primary blue (buttons, links) |
| `#cc0000` | Critical risk (red) |
| `#ff9900` | High/Medium risk (orange) |
| `#ffcc00` | Low risk warning (yellow) |
| `#00cc00` | Success/clean (green) |
| `#f5f5f5` | Light background |
| `#333333` | Dark text |

---

## 🧪 Development

### Debugging

1. **React DevTools browser extension** for inspecting component state
2. **Browser Console** for API errors
3. **Network tab** for request/response inspection
4. **Local Storage** stores language preference: `localStorage.setItem('lang', 'it')`

### Common Patterns

**Fetching data with loading states:**
```jsx
const [data, setData] = useState(null);
const [loading, setLoading] = useState(false);

useEffect(() => {
  const fetch = async () => {
    setLoading(true);
    try {
      const res = await client.get('/api/analysis');
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  fetch();
}, []);
```

**Using context for global state:**
```jsx
const { lang, setLang } = useLanguage();
const { analysisData } = useAnalysis();
```

---

## 📦 Dependencies

### Core
- **react** (19.x) — UI library
- **react-dom** (19.x) — DOM rendering
- **axios** — HTTP client

### Dev
- **vite** (8.x) — Build tool
- **eslint** — Code linting
- **@vitejs/plugin-react** — React plugin for Vite

> [!TIP]
> **No external UI framework** — everything is CSS + vanilla React.

---

## 🚀 Performance Optimizations

- ✅ **Code splitting** — chunks lazy-loaded per route
- ✅ **Asset bundling** — JS + CSS minified and compressed
- ✅ **Lazy load components** — `React.lazy()` for off-screen panels
- ✅ **Memoization** — `React.memo()` for heavy components
- ✅ **Image optimization** — SVG and optimized PNG for icons

---

## 🔐 Security

- ✅ **No hardcoded secrets** — API key handling in backend only
- ✅ **HTTPS ready** — works with HTTPS proxies
- ✅ **Input validation** — file type and size checks
- ✅ **XSS protection** — React escapes content by default

---

## 📚 Components Reference

### 🔤 UploadZone
- Drag-and-drop file upload
- WHOIS checkbox for domain age analysis
- Manual source paste option

### 📊 AnalysisDetail
- Six-tab interface (Summary, Header, Body, URL, Attachment, Reputation)
- Risk gauge visualization
- Analyst notes editor
- Report download button

### 🌐 TabReputation
- 19 reputation services overview
- Phase 1/2 loading indicators
- Service status and result details
- Malicious indicator highlighting

### 🕸️ CampaignsPanel
- Campaign cluster analysis
- Similarity threshold slider
- Cluster expansion/collapse
- Email count and risk summary

---

## 🐛 Troubleshooting

### npm install fails
```bash
rm -rf node_modules package-lock.json
npm install
```

### Vite dev server won't start
```bash
# Check port 5173 is free
lsof -i :5173
npm run dev -- --host 0.0.0.0
```

### Built bundle not loading in backend
1. Verify `build.outDir` in `vite.config.js` points to `../backend/static/`
2. Run `npm run build` explicitly
3. Check `backend/static/` contains `index.html`, `assets/index.js`, `assets/index.css`

---

## ✅ What's Next?

- **Backend setup?** → [../README.md](../README.md)
- **Using the API?** → [../docs/API.md](../docs/API.md)
- **Deploying?** → See `start.bat` / `start.sh`

---

*Built with ❤️ for email security analysis | [License: MIT](../LICENSE)*
