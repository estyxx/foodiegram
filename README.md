# 🍳 Cookstagram Frontend

A beautiful, modern recipe browser for your Instagram saved collections.

## Features

- 🔍 Advanced search and filtering
- 📱 Responsive design
- ❤️ Favorites system
- 🛒 Shopping list
- 📊 Recipe comparison
- 🎯 Smart categorization
- 📤 Export functionality

## Deployment

This frontend is deployed on Vercel and fetches data from a private API.

### Local Development

```bash
npm install
npm run dev
```

### Data Source

The app fetches recipe data from:
- Primary: `https://cookstagram-data.vercel.app/api/recipes`
- Fallback: Local `data/extracted_recipes_realtime.json`

## Project Structure

```
ui/
├── index.html          # Main recipe browser
├── app.js             # Modular JavaScript
├── styles.css         # Styling
├── recipe.html        # Individual recipe view
├── recipe.js          # Recipe page logic
├── analytics.html     # Analytics dashboard
├── mobile.html        # Mobile-optimized view
└── planner.html       # Meal planner
```

## Privacy

- Recipe data is stored in a private repository
- No personal Instagram data is exposed publicly
- All data processing happens client-side
