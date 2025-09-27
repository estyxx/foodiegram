# 🚀 Deployment Guide

## Overview

This project is split into two parts:
1. **Frontend** (this repo) - Public, deployed on Vercel
2. **Data API** (private repo) - Private, deployed on Vercel

## Step 1: Deploy Data API (Private)

1. **Create GitHub repository:**
   ```bash
   cd /Users/ester.beltrami/Projects/cookstagram-data
   git remote add origin https://github.com/yourusername/cookstagram-data.git
   git push -u origin main
   ```

2. **Deploy to Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Import the `cookstagram-data` repository
   - Set as private repository
   - Deploy with default settings
   - Note the deployment URL (e.g., `https://cookstagram-data.vercel.app`)

## Step 2: Deploy Frontend (Public)

1. **Update API URL:**
   - Edit `ui/index.html` and `ui/app.js`
   - Replace `https://cookstagram-data.vercel.app` with your actual API URL

2. **Deploy to Vercel:**
   ```bash
   cd /Users/ester.beltrami/Projects/cookstagram
   git add .
   git commit -m "Prepare for Vercel deployment"
   git push origin main
   ```


   - Go to [vercel.com](https://vercel.com)
   - Import the `cookstagram` repository
   - Deploy with default settings

## Step 3: Configure CORS

The data API includes CORS headers, but you may need to configure them for your specific domain.

## Testing

1. **Test API locally:**
   ```bash
   cd /Users/ester.beltrami/Projects/cookstagram-data
   npm install
   npm start
   # Visit http://localhost:3001/api/recipes
   ```

2. **Test frontend locally:**
   ```bash
   cd /Users/ester.beltrami/Projects/cookstagram
   npm install
   npm run dev
   # Visit http://localhost:3000
   ```

## Environment Variables

For the data API, you can set these in Vercel:
- `PORT` (optional, defaults to 3001)

## Security Notes

- The data API is private and should not be publicly accessible
- Only the frontend should be able to access the API
- Consider adding authentication if needed
