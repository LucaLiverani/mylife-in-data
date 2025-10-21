# My Life in Data - Dashboard

> **"Turning bad habits into pretty charts."**

A modern, interactive dashboard that aggregates data from various services (Spotify, YouTube, Google Search, Google Maps) to visualize my digital life. Built with Next.js 15 and FastAPI.

![Dashboard Preview](https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=next.js)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?style=flat-square&logo=typescript)
![Python](https://img.shields.io/badge/Python-3.11+-green?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

## 🚀 Features

- **📊 Data Visualization**: Beautiful charts showing my monthly activity across all services
- **🎵 Spotify Integration**: Track listening history with recent plays and statistics
- **🎬 YouTube Activity**: Monitor video watching patterns
- **🔍 Google Search**: View search history and trends
- **🗺️ Travel Map**: Interactive map showing my travel history with connections
- **✨ Modern UI**: Smooth animations, glassmorphism effects, and responsive design
- **🎨 Color-coded Services**: Each service has distinct colors and visual identity
- **⚡ Real-time Updates**: Dynamic data loading from FastAPI backend

## 📁 Project Structure

```
dashboard-nextjs/
├── api/                          # FastAPI Backend
│   ├── main.py                   # API endpoints and data generation
│   ├── requirements.txt          # Python dependencies
│   └── .env                      # Backend environment variables (create from .env.example)
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout with metadata
│   ├── page.tsx                  # Main dashboard page
│   └── globals.css               # Global styles and Tailwind imports
├── components/                   # React Components
│   ├── animations/               # Animation components
│   │   ├── FadeIn.tsx           # Fade-in animation wrapper
│   │   ├── ParticleBackground.tsx # Animated particle background
│   │   └── Typewriter.tsx       # Typewriter text effect
│   ├── charts/                   # Chart components
│   │   └── DataGenerationChart.tsx # Interactive area chart with toggle
│   ├── ui/                       # Shadcn UI components
│   │   ├── button.tsx
│   │   └── card.tsx
│   ├── KPIMetric.tsx            # KPI display component
│   ├── RecentEventItem.tsx      # Event list item with hover effects
│   ├── ServiceCard.tsx          # Service card with stats
│   └── TravelMap.tsx            # Interactive Leaflet map
├── lib/                          # Utilities
│   ├── api.ts                    # API client for backend communication
│   └── utils.ts                  # Helper functions
├── public/                       # Static assets
├── .env.example                  # Environment variables template
└── package.json                  # Dependencies and scripts
```

## 🛠️ Tech Stack

### Frontend
- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 3
- **UI Components**: Shadcn UI
- **Animations**: Framer Motion
- **Charts**: Recharts
- **Maps**: Leaflet + React Leaflet
- **Icons**: Lucide React

### Backend
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Data**: Mock data generation (ready for real API integration)

## 📦 Installation

### Prerequisites

- **Node.js**: v20 or higher ([Download](https://nodejs.org/))
- **Python**: 3.11 or higher ([Download](https://python.org/))
- **npm**: Comes with Node.js

### 1. Clone the Repository

```bash
cd /home/lliverani/projects/mylife-in-data/pipelines/pipeline-2/dashboard-nextjs
```

### 2. Install Frontend Dependencies

```bash
npm install
```

### 3. Install Backend Dependencies

```bash
cd api
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

### 4. Configure Environment Variables

Create environment files from templates:

```bash
# Frontend
cp .env.example .env.local

# Backend
cp api/.env.example api/.env
```

Edit the files with my configuration:

**.env.local** (Frontend):
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**api/.env** (Backend):
```env
CORS_ORIGINS=http://localhost:3000
```

## 🚀 Running the Project

### Development Mode

You can run both frontend and backend simultaneously using the provided script:

```bash
chmod +x start.sh
./start.sh
```

**Or run them separately:**

**Terminal 1 - Backend (FastAPI):**
```bash
cd api
source venv/bin/activate  # On Windows: venv\Scripts\activate
python main.py
# API will run on http://localhost:8000
```

**Terminal 2 - Frontend (Next.js):**
```bash
npm run dev
# App will run on http://localhost:3000
```

### Production Build

```bash
# Build frontend
npm run build
npm start

# Backend (use production ASGI server)
cd api
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🎨 Adding New Pages

### 1. Create a New Route

Next.js uses file-based routing. Create a new folder in the `app/` directory:

```bash
mkdir app/spotify
```

### 2. Add a Page Component

Create `app/spotify/page.tsx`:

```tsx
export default function SpotifyPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a1a1a] to-[#2d2d2d] text-white">
      <div className="max-w-7xl mx-auto px-6 py-20">
        <h1 className="text-4xl font-bold mb-8">Spotify Stats</h1>
        {/* my content here */}
      </div>
    </div>
  );
}
```

### 3. Add Metadata (Optional)

```tsx
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Spotify Stats - My Life in Data',
  description: 'View my Spotify listening statistics',
};

export default function SpotifyPage() {
  // ...
}
```

### 4. Link to the Page

Use Next.js `Link` component:

```tsx
import Link from 'next/link';

<Link href="/spotify">
  View Spotify Stats
</Link>
```

The page will be automatically available at `http://localhost:3000/spotify`.

## 📊 Adding New Components

### 1. Create Component File

```bash
# Create in appropriate directory
touch components/MyNewComponent.tsx
```

### 2. Component Template

```tsx
'use client'; // Only if using hooks or client-side features

interface MyNewComponentProps {
  title: string;
  data: any[];
}

export function MyNewComponent({ title, data }: MyNewComponentProps) {
  return (
    <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
      <h3 className="text-xl font-bold mb-4">{title}</h3>
      {/* Component content */}
    </div>
  );
}
```

### 3. Import and Use

```tsx
import { MyNewComponent } from '@/components/MyNewComponent';

<MyNewComponent title="Test" data={[]} />
```

## 🔌 API Integration

### Adding New Endpoints

Edit `api/main.py`:

```python
@app.get("/api/new-endpoint")
async def get_new_data():
    return {
        "data": [...],
        "timestamp": datetime.now().isoformat()
    }
```

### Consuming in Frontend

Add to `lib/api.ts`:

```typescript
export const newAPI = {
  getData: async () => {
    const response = await fetch(`${API_URL}/api/new-endpoint`);
    return response.json();
  },
};
```

Use in component:

```tsx
const data = await newAPI.getData();
```

## 🎨 Styling Guidelines

This project uses Tailwind CSS with a custom dark theme:

### Color Palette

- **Background**: `from-[#1a1a1a] to-[#2d2d2d]`
- **Spotify Green**: `#1DB954`
- **YouTube Red**: `#FF0000`
- **Google Blue**: `#4285F4`
- **Maps Purple**: `#A855F7`

### Common Patterns

**Glass Card:**
```tsx
<div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8">
  {/* Content */}
</div>
```

**Hover Effect:**
```tsx
<div className="hover:border-white/20 transition-all duration-300">
  {/* Content */}
</div>
```

## 📝 Available Scripts

```bash
# Development
npm run dev          # Start Next.js dev server
npm run build        # Build for production
npm start            # Start production server

# Code Quality
npm run lint         # Run ESLint
npm run type-check   # Run TypeScript compiler check

# Backend
cd api && python main.py    # Start FastAPI server
```

## 🐛 Troubleshooting

### Port Already in Use

If port 3000 or 8000 is already in use:

```bash
# Find and kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Or use different port
PORT=3001 npm run dev
```

### Python Virtual Environment Issues

```bash
# Recreate virtual environment
cd api
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Leaflet Map Not Showing

Ensure Leaflet CSS is imported in the component:

```tsx
import 'leaflet/dist/leaflet.css';
```

## 📚 Documentation

- **Next.js**: [nextjs.org/docs](https://nextjs.org/docs)
- **Tailwind CSS**: [tailwindcss.com/docs](https://tailwindcss.com/docs)
- **FastAPI**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
- **Recharts**: [recharts.org](https://recharts.org/)
- **Leaflet**: [leafletjs.com](https://leafletjs.com/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit my changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Migration**: Migrated from Python Dash to Next.js for better performance and modern stack
- **UI Components**: Built with Shadcn UI
- **Design Inspiration**: Modern glassmorphism and dark mode aesthetics

---

**Built with ❤️ by Luigi Liverani**

*"Pretty charts, brutal honesty, optional self-improvement."*
