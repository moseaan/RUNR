# Deployment Checklist for Render.com

## Critical: Before Every Deploy

Run these git commands to commit all changes:

```bash
# 1. Add all modified files
git add .

# 2. Check what will be committed
git status

# 3. Commit with a message
git commit -m "Update services config and add import/export features"

# 4. Push to your repository
git push origin main
```

## Verify These Files Are Committed

✅ **MUST be in git for Render to work correctly:**
- `config/services_catalog.json` - Your current services configuration
- `app_files/app.py` - Backend routes including import/export
- `app_files/templates/services.html` - Services page with Import button
- `app_files/templates/profiles.html` - Profiles page with Import button
- `app_files/static/script.js` - JavaScript handlers
- `app_files/services_catalog.py` - Services catalog logic

## After Deploying to Render

1. **Wait for build to complete** (check Render dashboard)
2. **Open your app** on Render
3. **Go to Services page**
4. **Check if Import Configs button appears** (should be green, left of Export)
5. **Verify services show your updates**:
   - Instagram Followers → Peakerr #27327
   - Spotify services → All MySocialsBoost

## If Services Are Still Wrong After Deploy

**Option 1: Use Import Button** (recommended)
1. On your LOCAL machine, go to Services page
2. Click "Export Configs" → saves `services_catalog.json`
3. On RENDER website, go to Services page
4. Click "Import Configs" → upload your local file
5. Page reloads with correct services

**Option 2: Check if JSON was committed**
```bash
git ls-files config/services_catalog.json
```
If this returns nothing, the file isn't tracked. Add it:
```bash
git add config/services_catalog.json
git commit -m "Add services catalog to repo"
git push
```

## Quick Fix Command

Run this in your terminal from the project root:

```bash
git add config/services_catalog.json app_files/app.py app_files/templates/services.html app_files/templates/profiles.html app_files/static/script.js app_files/services_catalog.py
git commit -m "Add import/export and update services config"
git push
```

Then redeploy on Render.
