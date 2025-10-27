# Configuration Files

This folder contains service and API configuration files.

## Important Files

- **services_catalog.json** - Primary services configuration. This file MUST be committed to git and deployed to production.
- **SMM_Services_Tiers.csv** - Reference CSV (used for migration if JSON doesn't exist)
- **service_overrides.json** - Legacy overrides (deprecated, use services_catalog.json)
- **profiles.json** - User profiles (managed at runtime, can be imported/exported)
- **API key files** - Keep these secure and never commit to public repos

## Deployment to Render.com

To ensure your services configuration persists on Render:

1. **Commit the JSON file**:
   ```bash
   git add config/services_catalog.json
   git commit -m "Update services configuration"
   git push
   ```

2. **Verify after deploy**:
   - Open Services page on Render
   - Check that your configured services appear
   - If old services appear, use "Import Configs" to upload your local `services_catalog.json`

## Updating Services

- Use the Services Configuration page in the web UI
- Changes save to `config/services_catalog.json`
- Export and re-import on different environments as needed
