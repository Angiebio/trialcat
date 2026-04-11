# frontend/

Static HTML/CSS/JS served by FastAPI. No build step, no framework — just Leaflet and vanilla JS for fast iteration and zero bundling overhead.

## Structure

```
frontend/
├── templates/
│   └── index.html       # Main map page
└── static/
    ├── css/
    ├── js/
    │   ├── map.js       # Leaflet setup + choropleth
    │   └── filters.js   # Filter controls
    └── geo/
        └── countries.geojson  # Country boundaries (Natural Earth)
```

If we outgrow vanilla JS (unlikely for MVP), the migration to React/Svelte is clean because we're not coupling the backend to any template engine beyond serving static files.
