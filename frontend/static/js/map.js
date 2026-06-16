/**
 * trialcat map frontend
 *
 * Architecture:
 *   1. On load: fetch /api/filters → populate dropdowns,
 *      fetch /api/aggregate?by=country → color world choropleth
 *   2. On filter change: re-fetch aggregate, recolor
 *   3. Click country → popup with stats + (if US) "View by state" button
 *   4. "View by state" → zoom to US, swap world layer for state choropleth
 *   5. Click state → popup with state-level stats
 *   6. "Back to world" → zoom out, swap state layer back to world layer
 */

// =============================================================================
// GLOBALS
// =============================================================================

let map;
let worldGeoLayer;       // Country-level choropleth (always loaded)
let stateGeoLayer;       // US state choropleth (loaded on first drill-down)
let stateGeoData;        // Cached US states GeoJSON
let countryData = {};    // { iso_a2: { trial_count, total_enrollment } }
let stateData = {};      // { state_code: { trial_count, total_enrollment } }
let viewMode = 'world';  // 'world' or 'us_states'
let backControl;         // Leaflet control for the "Back to world" button

const COLORS = {
    noData: '#f0ece0',
    low:    '#c7e3b1',
    mid:    '#5bb545',
    high:   '#2d7a1e',
    border: '#4a0873',
};

const US_BOUNDS = [[24, -130], [50, -65]];

// =============================================================================
// INIT
// =============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    initMap();
    await Promise.all([
        loadFilters(),
        loadWorldGeoJSON(),
    ]);
    await refreshWorldChoropleth();

    document.getElementById('btn-apply').addEventListener('click', () => {
        if (viewMode === 'us_states') {
            refreshStateChoropleth();
        } else {
            refreshWorldChoropleth();
        }
    });
    document.getElementById('btn-reset').addEventListener('click', resetFilters);
});

// =============================================================================
// MAP SETUP
// =============================================================================

function initMap() {
    map = L.map('map', {
        center: [25, 10],
        zoom: 2,
        minZoom: 2,
        maxZoom: 8,
        zoomControl: true,
        attributionControl: false,
        maxBounds: [[-85, -200], [85, 200]],
        maxBoundsViscosity: 1.0,
    });

    L.control.attribution({ prefix: false }).addTo(map);

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
}

// =============================================================================
// DATA FETCHING
// =============================================================================

async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`API ${resp.status}`);
    return resp.json();
}

function buildFilterParams() {
    const params = new URLSearchParams();
    const area = document.getElementById('filter-area').value;
    const phase = document.getElementById('filter-phase').value;
    const status = document.getElementById('filter-status').value;
    const intervention = document.getElementById('filter-intervention').value;
    const productCategory = document.getElementById('filter-product-category').value;
    const deviceClass = document.getElementById('filter-device-class').value;
    const startDate = document.getElementById('filter-start').value;
    const endDate = document.getElementById('filter-end').value;

    if (area) params.set('therapeutic_area', area);
    if (phase) params.set('phase', phase);
    if (status) params.set('status', status);
    if (intervention) params.set('intervention_type', intervention);
    // Drill-downs only matter when an intervention type is chosen; they're
    // wiped + hidden otherwise, so a stale value can't leak into the query.
    if (productCategory) params.set('product_category', productCategory);
    if (deviceClass) params.set('device_class', deviceClass);
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);

    return params.toString();
}

// =============================================================================
// FILTERS
// =============================================================================

// Stash the /api/filters payload so the dependent drill-downs can rebuild
// their options on the fly when the intervention type changes.
let filterData = null;

async function loadFilters() {
    try {
        const data = await fetchJSON('/api/filters');
        filterData = data;
        populateSelect('filter-area', data.therapeutic_areas);
        populateSelect('filter-phase', data.phases);
        populateSelect('filter-status', data.statuses);
        populateSelect('filter-intervention', data.intervention_types);
        populateSelect('filter-device-class', (data.device_classes || []).map(c => ({
            value: c, label: `Class ${c}`,
        })));
        // Wire the dependent drill-down: when intervention type changes, show
        // the right finer cut (device family / drug class) and the device class.
        document.getElementById('filter-intervention')
            .addEventListener('change', updateDrilldowns);
    } catch (e) {
        console.error('[trialcat] Failed to load filters:', e);
    }
}

/**
 * Show/hide + repopulate the product-category and device-class drill-downs
 * based on the selected intervention type. A device has both a product family
 * AND an FDA class; a drug has a pharmacologic class; everything else has
 * neither. Switching type always clears the stale drill-down values so they
 * can't silently survive into the next query.
 */
function updateDrilldowns() {
    const itype = document.getElementById('filter-intervention').value;
    const pcGroup = document.getElementById('group-product-category');
    const pcSelect = document.getElementById('filter-product-category');
    const pcLabel = document.getElementById('label-product-category');
    const dcGroup = document.getElementById('group-device-class');
    const dcSelect = document.getElementById('filter-device-class');

    // Always reset the dependent values when the parent changes.
    pcSelect.value = '';
    dcSelect.value = '';

    const byType = (filterData && filterData.product_categories_by_type) || {};
    const cats = byType[itype] || [];

    if (cats.length) {
        // Label adapts to the domain: devices have "families", drugs have "classes".
        pcLabel.textContent = itype === 'DEVICE' ? 'Device category'
            : itype === 'DRUG' ? 'Drug class'
            : 'Product category';
        populateSelect('filter-product-category', cats);
        pcGroup.style.display = '';
    } else {
        pcGroup.style.display = 'none';
    }

    // FDA device class is device-only.
    dcGroup.style.display = (itype === 'DEVICE' && (filterData?.device_classes || []).length)
        ? '' : 'none';
}

function populateSelect(elementId, values) {
    const select = document.getElementById(elementId);
    while (select.options.length > 1) select.remove(1);
    for (const v of values) {
        const opt = document.createElement('option');
        // Accept either bare strings or {value, label} objects so we can show
        // a friendlier label (e.g. "Class II") while filtering on the raw value.
        if (v && typeof v === 'object') {
            opt.value = v.value;
            opt.textContent = v.label;
        } else {
            opt.value = v;
            opt.textContent = v;
        }
        select.appendChild(opt);
    }
}

function resetFilters() {
    document.getElementById('filter-area').value = '';
    document.getElementById('filter-phase').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-intervention').value = '';
    document.getElementById('filter-product-category').value = '';
    document.getElementById('filter-device-class').value = '';
    updateDrilldowns();  // collapse the dependent groups back to hidden
    document.getElementById('filter-start').value = '';
    document.getElementById('filter-end').value = '';
    if (viewMode === 'us_states') {
        backToWorld();
    } else {
        refreshWorldChoropleth();
    }
}

// =============================================================================
// WORLD CHOROPLETH
// =============================================================================

async function loadWorldGeoJSON() {
    const resp = await fetch('/static/geo/countries.geojson');
    const geojson = await resp.json();
    worldGeoLayer = L.geoJSON(geojson, {
        style: () => defaultStyle(),
        onEachFeature: onEachCountry,
    }).addTo(map);
}

async function refreshWorldChoropleth() {
    showLoading(true);
    try {
        const params = buildFilterParams();
        const data = await fetchJSON(`/api/aggregate?by=country${params ? '&' + params : ''}`);
        countryData = {};
        for (const row of data.rows) countryData[row.group_key] = row;
        updateSidebarStats(data, 'countries');
        if (worldGeoLayer) worldGeoLayer.setStyle(f => worldStyle(f));
    } catch (e) {
        console.error('[trialcat] Refresh world failed:', e);
    } finally {
        showLoading(false);
    }
}

function getCount(lookup, key) {
    return lookup[key] ? lookup[key].trial_count : 0;
}

function getColor(count) {
    if (count === 0) return COLORS.noData;
    if (count <= 2)  return '#e0f0d4';
    if (count <= 5)  return COLORS.low;
    if (count <= 10) return '#8fce7a';
    if (count <= 20) return COLORS.mid;
    if (count <= 50) return '#3b9a27';
    return COLORS.high;
}

function defaultStyle() {
    return { fillColor: COLORS.noData, weight: 1, color: '#ccc', fillOpacity: 0.7 };
}

function worldStyle(feature) {
    const count = getCount(countryData, feature.properties.iso_a2);
    return {
        fillColor: getColor(count),
        weight: 1,
        color: count > 0 ? COLORS.border : '#ccc',
        fillOpacity: 0.7,
    };
}

// =============================================================================
// COUNTRY INTERACTION
// =============================================================================

function onEachCountry(feature, layer) {
    const iso = feature.properties.iso_a2;
    const name = feature.properties.name;

    layer.bindTooltip(() => {
        const count = getCount(countryData, iso);
        return `<strong>${name}</strong><br>${count} trial${count !== 1 ? 's' : ''}`;
    }, { sticky: true });

    layer.on('click', () => showCountryStats(iso, name, layer));
    layer.on('mouseover', () => layer.setStyle({ weight: 2, color: COLORS.border, fillOpacity: 0.85 }));
    layer.on('mouseout', () => { if (worldGeoLayer) worldGeoLayer.resetStyle(layer); });
}

async function showCountryStats(isoCode, countryName, layer) {
    const params = buildFilterParams();
    try {
        const stats = await fetchJSON(`/api/stats?country_code=${isoCode}${params ? '&' + params : ''}`);

        // Build popup — add "View by state" button for US
        const drillDownBtn = isoCode === 'US'
            ? '<button class="popup-drilldown" onclick="drillDownToStates()">View by state →</button>'
            : '';

        const popupContent = `
            <div class="trial-popup">
                <h3>${countryName} (${isoCode})</h3>
                <table>
                    <tr><td>Trials</td><td><strong>${stats.trial_count.toLocaleString()}</strong></td></tr>
                    <tr><td>Total enrolled</td><td><strong>${stats.total_enrollment ? stats.total_enrollment.toLocaleString() : 'N/A'}</strong></td></tr>
                    ${stats.approx_rate_sample_size > 0 ? `
                    <tr><td colspan="2" class="section-header">Approx. enrollment rate (pts/mo)</td></tr>
                    <tr><td>Low</td><td>${stats.approx_rate_min?.toFixed(1) ?? 'N/A'}</td></tr>
                    <tr><td>Median</td><td><strong>${stats.approx_rate_median?.toFixed(1) ?? 'N/A'}</strong></td></tr>
                    <tr><td>High</td><td>${stats.approx_rate_max?.toFixed(1) ?? 'N/A'}</td></tr>
                    <tr><td>Based on</td><td>${stats.approx_rate_sample_size} trial${stats.approx_rate_sample_size !== 1 ? 's' : ''}</td></tr>
                    ` : '<tr><td colspan="2"><em>No enrollment rate data</em></td></tr>'}
                    ${stats.avg_months_enrolling ? `
                    <tr><td>Avg duration</td><td>${stats.avg_months_enrolling.toFixed(1)} months</td></tr>
                    ` : ''}
                </table>
                ${stats.approx_rate_sample_size < 5 && stats.approx_rate_sample_size > 0 ?
                    '<p class="popup-warning">⚠ Small sample — interpret with caution</p>' : ''}
                <div class="popup-actions">
                    ${drillDownBtn}
                    <button class="popup-export" onclick="exportCSV()">Export CSV</button>
                </div>
            </div>
        `;

        stageExport(`${countryName} (${isoCode})`, stats);
        layer.bindPopup(popupContent, { maxWidth: 320, className: 'trialcat-popup' }).openPopup();
    } catch (e) {
        layer.bindPopup(`<p>Error loading stats for ${countryName}</p>`).openPopup();
    }
}

// =============================================================================
// US STATE DRILL-DOWN
// =============================================================================

async function drillDownToStates() {
    map.closePopup();
    viewMode = 'us_states';

    // Hide world layer, show state layer
    if (worldGeoLayer) map.removeLayer(worldGeoLayer);

    // Load state GeoJSON on first use
    if (!stateGeoData) {
        const resp = await fetch('/static/geo/us-states.geojson');
        stateGeoData = await resp.json();
    }

    // Create state layer if not already created
    if (stateGeoLayer) map.removeLayer(stateGeoLayer);
    stateGeoLayer = L.geoJSON(stateGeoData, {
        style: () => defaultStyle(),
        onEachFeature: onEachState,
    }).addTo(map);

    // Zoom to US
    map.fitBounds(US_BOUNDS, { padding: [20, 20] });

    // Add "Back to world" button
    addBackControl();

    // Fetch state-level data
    await refreshStateChoropleth();
}

async function refreshStateChoropleth() {
    showLoading(true);
    try {
        const params = buildFilterParams();
        const data = await fetchJSON(`/api/aggregate?by=us_state${params ? '&' + params : ''}`);
        stateData = {};
        for (const row of data.rows) stateData[row.group_key] = row;
        updateSidebarStats(data, 'states');
        if (stateGeoLayer) stateGeoLayer.setStyle(f => stateStyle(f));
    } catch (e) {
        console.error('[trialcat] Refresh states failed:', e);
    } finally {
        showLoading(false);
    }
}

function stateStyle(feature) {
    const count = getCount(stateData, feature.properties.code);
    return {
        fillColor: getColor(count),
        weight: 1,
        color: count > 0 ? COLORS.border : '#ccc',
        fillOpacity: 0.7,
    };
}

function onEachState(feature, layer) {
    const code = feature.properties.code;
    const name = feature.properties.name;

    layer.bindTooltip(() => {
        const count = getCount(stateData, code);
        return `<strong>${name}</strong><br>${count} trial${count !== 1 ? 's' : ''}`;
    }, { sticky: true });

    layer.on('click', () => showStateStats(code, name, layer));
    layer.on('mouseover', () => layer.setStyle({ weight: 2, color: COLORS.border, fillOpacity: 0.85 }));
    layer.on('mouseout', () => { if (stateGeoLayer) stateGeoLayer.resetStyle(layer); });
}

async function showStateStats(stateCode, stateName, layer) {
    const params = buildFilterParams();
    try {
        const stats = await fetchJSON(`/api/stats?country_code=US&state_code=${stateCode}${params ? '&' + params : ''}`);

        const popupContent = `
            <div class="trial-popup">
                <h3>${stateName} (${stateCode})</h3>
                <table>
                    <tr><td>Trials</td><td><strong>${stats.trial_count.toLocaleString()}</strong></td></tr>
                    <tr><td>Total enrolled</td><td><strong>${stats.total_enrollment ? stats.total_enrollment.toLocaleString() : 'N/A'}</strong></td></tr>
                    ${stats.approx_rate_sample_size > 0 ? `
                    <tr><td colspan="2" class="section-header">Approx. enrollment rate (pts/mo)</td></tr>
                    <tr><td>Low</td><td>${stats.approx_rate_min?.toFixed(1) ?? 'N/A'}</td></tr>
                    <tr><td>Median</td><td><strong>${stats.approx_rate_median?.toFixed(1) ?? 'N/A'}</strong></td></tr>
                    <tr><td>High</td><td>${stats.approx_rate_max?.toFixed(1) ?? 'N/A'}</td></tr>
                    <tr><td>Based on</td><td>${stats.approx_rate_sample_size} trial${stats.approx_rate_sample_size !== 1 ? 's' : ''}</td></tr>
                    ` : '<tr><td colspan="2"><em>No enrollment rate data</em></td></tr>'}
                    ${stats.avg_months_enrolling ? `
                    <tr><td>Avg duration</td><td>${stats.avg_months_enrolling.toFixed(1)} months</td></tr>
                    ` : ''}
                </table>
                ${stats.approx_rate_sample_size < 5 && stats.approx_rate_sample_size > 0 ?
                    '<p class="popup-warning">⚠ Small sample — interpret with caution</p>' : ''}
                <div class="popup-actions">
                    <button class="popup-export" onclick="exportCSV()">Export CSV</button>
                </div>
            </div>
        `;

        stageExport(`${stateName} (${stateCode})`, stats);
        layer.bindPopup(popupContent, { maxWidth: 320, className: 'trialcat-popup' }).openPopup();
    } catch (e) {
        layer.bindPopup(`<p>Error loading stats for ${stateName}</p>`).openPopup();
    }
}

// =============================================================================
// BACK TO WORLD
// =============================================================================

function backToWorld() {
    viewMode = 'world';
    map.closePopup();

    // Swap layers
    if (stateGeoLayer) map.removeLayer(stateGeoLayer);
    if (worldGeoLayer) worldGeoLayer.addTo(map);

    // Remove back button
    if (backControl) { map.removeControl(backControl); backControl = null; }

    // Zoom back to world
    map.setView([25, 10], 2);

    // Re-apply world choropleth colors
    refreshWorldChoropleth();
}

function addBackControl() {
    if (backControl) return; // already showing

    const BackControl = L.Control.extend({
        options: { position: 'topleft' },
        onAdd: function () {
            const btn = L.DomUtil.create('button', 'back-to-world-btn');
            btn.innerHTML = '← World view';
            btn.title = 'Back to world map';
            btn.onclick = function (e) {
                e.stopPropagation();
                e.preventDefault();
                backToWorld();
            };
            L.DomEvent.disableClickPropagation(btn);
            return btn;
        },
    });

    backControl = new BackControl();
    map.addControl(backControl);
}

// =============================================================================
// SIDEBAR STATS
// =============================================================================

function updateSidebarStats(aggregateData, groupLabel) {
    const el = document.getElementById('sidebar-stats');
    el.innerHTML = `
        <div class="stats-summary">
            <div class="stat-item">
                <span class="stat-value">${aggregateData.total_trials.toLocaleString()}</span>
                <span class="stat-label">trials</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">${aggregateData.rows.length}</span>
                <span class="stat-label">${groupLabel || 'groups'}</span>
            </div>
        </div>
    `;
}

// =============================================================================
// UI HELPERS
// =============================================================================

function showLoading(show) {
    document.getElementById('map-loading').style.display = show ? 'flex' : 'none';
}

// =============================================================================
// CSV EXPORT — client-side, zero backend overhead
// =============================================================================

/**
 * Generate and download a CSV from a stats response object.
 * Called from the "Export CSV" button in popups.
 * The CSV includes a branded footer so if it ends up in an email or report,
 * it's clear where it came from and that it's approximate.
 */
let _lastExportData = null; // stash for the onclick handler

function stageExport(locationName, stats) {
    _lastExportData = { locationName, stats };
}

function exportCSV() {
    if (!_lastExportData) return;
    const { locationName, stats } = _lastExportData;
    const f = stats.filter_applied || {};

    const rows = [
        ['trialcat — Clinical Trial Enrollment Summary'],
        ['Location', locationName],
        ['Generated', new Date().toISOString().split('T')[0]],
        [],
        ['Metric', 'Value'],
        ['Total trials', stats.trial_count],
        ['Total enrolled', stats.total_enrollment ?? 'N/A'],
        ['Approx. enrollment rate — Low (pts/mo)', stats.approx_rate_min?.toFixed(1) ?? 'N/A'],
        ['Approx. enrollment rate — Median (pts/mo)', stats.approx_rate_median?.toFixed(1) ?? 'N/A'],
        ['Approx. enrollment rate — High (pts/mo)', stats.approx_rate_max?.toFixed(1) ?? 'N/A'],
        ['Rate sample size (trials with data)', stats.approx_rate_sample_size],
        ['Avg. enrollment duration (months)', stats.avg_months_enrolling?.toFixed(1) ?? 'N/A'],
        [],
        ['Filters Applied'],
        ['Therapeutic area', f.therapeutic_area || 'All'],
        ['Phase', f.phase || 'All'],
        ['Status', f.status || 'All'],
        ['Intervention type', f.intervention_type || 'All'],
        ['Start date from', f.start_date || 'Any'],
        ['Start date to', f.end_date || 'Any'],
        [],
        ['Source: trialcat.ai | The Real Cat AI Labs 501(c)(3) | Data from ClinicalTrials.gov'],
        ['DISCLAIMER: For research and educational purposes only. Enrollment rates are approximate.'],
        ['Not intended for clinical, regulatory, or investment decision-making. Use at your own risk.'],
        ['Full terms: https://trialcat.ai/terms'],
    ];

    const csv = rows.map(r => r.map(cell => {
        const s = String(cell ?? '');
        return s.includes(',') || s.includes('"') || s.includes('\n')
            ? '"' + s.replace(/"/g, '""') + '"'
            : s;
    }).join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const safeName = locationName.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    a.href = url;
    a.download = `trialcat_${safeName}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
