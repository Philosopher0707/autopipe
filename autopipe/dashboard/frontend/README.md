# AutoPipe Dashboard

A modern, production-grade React dashboard for monitoring ML/DL pipelines with real-time updates, model registry, drift detection, and experiment tracking.

## Features

- 🎨 **Modern UI**: Built with Tailwind CSS, shadcn/ui patterns
- 📊 **Real-time Charts**: Using Recharts for data visualization
- 🗺️ **DAG Visualization**: Pipeline visualization with D3.js (planned)
- ⚡ **Fast Development**: Vite for instant HMR
- 🔄 **State Management**: Zustand for simple, fast state
- 🔌 **API Integration**: React Query for server state management
- 🌐 **WebSocket Support**: Real-time pipeline monitoring
- 📱 **Responsive Design**: Mobile-friendly sidebar navigation

## Quick Start

```bash
# Navigate to frontend directory
cd autopipe/dashboard/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The dashboard will be available at http://localhost:3000

## Project Structure

```
src/
├── api/
│   ├── client.ts          # Axios instance
│   └── endpoints/         # API endpoint definitions
├── components/
│   ├── ui/               # UI primitives (Button, Card, etc.)
│   ├── layout/           # Layout components (Sidebar, Header)
│   ├── charts/           # Chart components
│   └── tables/           # Data table components
├── hooks/                # Custom React hooks
├── pages/                # Page components
│   ├── dashboard/
│   ├── pipelines/
│   ├── runs/
│   ├── models/
│   ├── experiments/
│   └── drift/
├── stores/               # Zustand stores
├── types/                # TypeScript types
└── utils/                # Utility functions
```

## Backend Integration

The frontend expects a FastAPI backend running on port 8000. See `../backend` directory for the backend implementation.

### API Configuration

The frontend uses proxy configuration in `vite.config.ts` to route requests to the backend:

```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
  '/ws': {
    target: 'ws://localhost:8000',
    ws: true,
  },
}
```

## Technologies Used

- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS 3.4
- **State**: Zustand
- **Server State**: React Query / TanStack Query
- **Routing**: React Router v6
- **Charts**: Recharts
- **Icons**: Lucide React
- **Tables**: AG Grid

## Development

```bash
# Run type checker
npm run typecheck

# Build for production
npm run build

# Preview production build
npm run preview
```

## License

MIT - see LICENSE file in the root repository.
