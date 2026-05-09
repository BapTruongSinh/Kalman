# Server Runtime Artifacts

Put deployment-local runtime artifacts here when deploying `Server/` without the full monorepo.

Expected default:

```text
Server/backend/artifacts/arx_model.json
```

`ARX_MODEL_PATH` can still override this path. In monorepo development, settings fall back to `ARX/arx_model.json` when this local artifact file is absent.
