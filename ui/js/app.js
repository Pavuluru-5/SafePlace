/**
 * SafePlace — Offline AI Safety Copilot Frontend Application
 * Interacts with FastAPI backend for spatial calculations, routing, safe bubble, and SLM chat.
 */

// Application State
const state = {
    userLat: 17.4435,
    userLon: 78.3772,
    currentCity: 'hyderabad',
    dataAgeHours: 0,
    pois: [],
    selectedPoi: null,
    activeRouteMode: 'safest', // 'safest' or 'fastest'
    currentRouteData: null,
    bubbleLayers: [],
    poiMarkers: {},
    routeLayers: {
        safest: null,
        fastest: null
    },
    userMarker: null
};

// Map & Layer references
let map = null;

// Optional: if you have a CARTO or Mapbox API key, you can set it here
const MAP_CONFIG = {
    cartoApiKey: "" // Leave empty for 100% free OpenStreetMap Dark HUD (No API Key Required)
};

// Initialize when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    initEventListeners();
    fetchPois();
    updateSafeBubble();
});

function initMap() {
    map = L.map('map', {
        center: [state.userLat, state.userLon],
        zoom: 15,
        zoomControl: false
    });

    L.control.zoom({ position: 'topright' }).addTo(map);

    // High-contrast Dark HUD tiles (100% Free & Open, no API key required)
    if (MAP_CONFIG.cartoApiKey) {
        L.tileLayer(`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?api_key=${MAP_CONFIG.cartoApiKey}`, {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);
    } else {
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            className: 'map-tiles-dark',
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
            subdomains: ['a', 'b', 'c'],
            maxZoom: 19
        }).addTo(map);
    }

    // User Location Marker (draggable)
    const userIcon = L.divIcon({
        className: 'user-marker-icon',
        html: `<div style="background:#3b82f6; width:16px; height:16px; border-radius:50%; border:3px solid #ffffff; box-shadow:0 0 12px #3b82f6;"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
    });

    state.userMarker = L.marker([state.userLat, state.userLon], {
        draggable: true,
        icon: userIcon
    }).addTo(map);

    state.userMarker.bindPopup("<b>Your GPS Position</b><br>Drag to simulate movement").openPopup();

    state.userMarker.on('dragend', (e) => {
        const pos = e.target.getLatLng();
        state.userLat = pos.lat;
        state.userLon = pos.lon;
        updateSafeBubble();
        if (state.selectedPoi) {
            calculateAndDrawRoutes(state.selectedPoi.id);
        }
    });

    map.on('click', (e) => {
        state.userMarker.setLatLng(e.latlng);
        state.userLat = e.latlng.lat;
        state.userLon = e.latlng.lon;
        updateSafeBubble();
        if (state.selectedPoi) {
            calculateAndDrawRoutes(state.selectedPoi.id);
        }
    });
}

function initEventListeners() {
    // City Selector
    const citySelect = document.getElementById('city-selector');
    if (citySelect) {
        citySelect.addEventListener('change', (e) => {
            const cityKey = e.target.value;
            fetch('/api/switch-city', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ city_key: cityKey })
            })
            .then(res => res.json())
            .then(data => {
                state.currentCity = cityKey;
                state.userLat = data.center.lat;
                state.userLon = data.center.lon;
                state.userMarker.setLatLng([state.userLat, state.userLon]);
                map.setView([state.userLat, state.userLon], 15);
                fetchPois();
                updateSafeBubble();
                addChatMessage(`Switched location to **${data.city_name}**. Local spatial database and safe corridors loaded.`, 'ai');
            });
        });
    }

    // Real Device GPS Locate Button
    const realGpsBtn = document.getElementById('real-gps-btn');
    if (realGpsBtn) {
        realGpsBtn.addEventListener('click', () => {
            if ("geolocation" in navigator) {
                realGpsBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Locating...';
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        realGpsBtn.innerHTML = '<i class="fa-solid fa-crosshairs"></i> Located!';
                        setTimeout(() => { realGpsBtn.innerHTML = '<i class="fa-solid fa-crosshairs"></i> Locate Me'; }, 2000);

                        // Seed local database around real coordinates
                        fetch('/api/set-location', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ lat: lat, lon: lon, name: "My Local Coordinates" })
                        })
                        .then(res => res.json())
                        .then(data => {
                            state.userLat = lat;
                            state.userLon = lon;
                            state.userMarker.setLatLng([lat, lon]);
                            map.setView([lat, lon], 15);
                            fetchPois();
                            updateSafeBubble();
                            addChatMessage(`📍 GPS Located: Dynamic safety network and verified havens generated around your real coordinates (**${lat.toFixed(4)}, ${lon.toFixed(4)}**).`, 'ai');
                        });
                    },
                    (error) => {
                        realGpsBtn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> GPS Failed';
                        setTimeout(() => { realGpsBtn.innerHTML = '<i class="fa-solid fa-crosshairs"></i> Locate Me'; }, 2500);
                        alert("Could not access real device GPS location. Please ensure location permissions are enabled in your browser.");
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }

    // Reset Location Button
    document.getElementById('reset-loc-btn').addEventListener('click', () => {
        map.panTo([state.userLat, state.userLon]);
        updateSafeBubble();
    });

    // Emergency "I'M NOT SAFE" button
    document.getElementById('emergency-btn').addEventListener('click', triggerEmergencyMode);

    // Data Age Slider (Demonstrates confidence decay and abstention)
    const slider = document.getElementById('data-age-slider');
    const ageVal = document.getElementById('data-age-val');
    slider.addEventListener('input', (e) => {
        const hours = parseInt(e.target.value);
        state.dataAgeHours = hours;
        ageVal.textContent = hours > 24 ? `${Math.round(hours / 24)}d (${hours}h)` : `${hours}h`;
        
        // Notify backend & update
        fetch('/api/data-trust/age', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hours: hours })
        }).then(() => {
            updateSafeBubble();
            if (state.selectedPoi) {
                calculateAndDrawRoutes(state.selectedPoi.id);
            }
        });
    });

    // Sync Data Button
    document.getElementById('sync-btn').addEventListener('click', () => {
        fetch('/api/sync', { method: 'POST' })
            .then(res => res.json())
            .then(() => {
                slider.value = 0;
                state.dataAgeHours = 0;
                ageVal.textContent = '0h';
                fetchPois();
                updateSafeBubble();
                addChatMessage('Data successfully refreshed and synchronized from municipal safety registry.', 'ai');
            });
    });

    // Route Mode Tabs
    document.getElementById('tab-safest').addEventListener('click', () => {
        state.activeRouteMode = 'safest';
        document.getElementById('tab-safest').classList.add('active');
        document.getElementById('tab-fastest').classList.remove('active');
        renderRouteMetrics();
    });

    document.getElementById('tab-fastest').addEventListener('click', () => {
        state.activeRouteMode = 'fastest';
        document.getElementById('tab-fastest').classList.add('active');
        document.getElementById('tab-safest').classList.remove('active');
        renderRouteMetrics();
    });

    // POI Filter
    document.getElementById('poi-filter').addEventListener('change', (e) => {
        renderPoiList(e.target.value);
    });

    // Chat Form Submit
    document.getElementById('chat-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if (text) {
            sendUserChatMessage(text);
            input.value = '';
        }
    });

    // Suggested Demo Pills
    document.querySelectorAll('.pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const prompt = pill.getAttribute('data-prompt');
            sendUserChatMessage(prompt);
        });
    });

    // Voice Assistant Simulation
    const voiceBtn = document.getElementById('voice-listen-btn');
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRec();
        recognition.continuous = false;
        recognition.interimResults = false;

        voiceBtn.addEventListener('click', () => {
            voiceBtn.classList.add('listening');
            recognition.start();
        });

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            voiceBtn.classList.remove('listening');
            sendUserChatMessage(transcript);
        };

        recognition.onerror = () => {
            voiceBtn.classList.remove('listening');
        };
        recognition.onend = () => {
            voiceBtn.classList.remove('listening');
        };
    } else {
        voiceBtn.title = "Voice recognition not supported in this browser";
    }
}

// Fetch and render POIs
function fetchPois() {
    fetch('/api/pois')
        .then(res => res.json())
        .then(pois => {
            state.pois = pois;
            renderPoiMarkers(pois);
            renderPoiList();
        });
}

function getPoiColor(category) {
    switch (category.toLowerCase()) {
        case 'police': return '#3b82f6';
        case 'hospital': return '#ef4444';
        case 'pharmacy': return '#10b981';
        case 'public_building': return '#a855f7';
        case 'fire_station': return '#f59e0b';
        case 'transport_hub': return '#06b6d4';
        default: return '#10b981';
    }
}

function getPoiIconClass(category) {
    switch (category.toLowerCase()) {
        case 'police': return 'fa-solid fa-shield-halved';
        case 'hospital': return 'fa-solid fa-hospital';
        case 'pharmacy': return 'fa-solid fa-prescription-bottle-medical';
        case 'public_building': return 'fa-solid fa-landmark';
        case 'fire_station': return 'fa-solid fa-fire-extinguisher';
        case 'transport_hub': return 'fa-solid fa-train';
        default: return 'fa-solid fa-building';
    }
}

function renderPoiMarkers(pois) {
    // Clear existing
    Object.values(state.poiMarkers).forEach(m => map.removeLayer(m));
    state.poiMarkers = {};

    pois.forEach(p => {
        const color = getPoiColor(p.category);
        const iconClass = getPoiIconClass(p.category);

        const customIcon = L.divIcon({
            className: 'poi-custom-marker',
            html: `<div style="background:${color}; color:white; width:30px; height:30px; border-radius:8px; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px ${color}; font-size:14px; cursor:pointer;">
                <i class="${iconClass}"></i>
            </div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });

        const marker = L.marker([p.lat, p.lon], { icon: customIcon }).addTo(map);
        
        marker.bindPopup(`
            <div style="color:#0f172a;">
                <strong style="font-size:14px;">${p.name}</strong><br>
                <span style="font-size:12px; color:#475569;">${p.category.toUpperCase()} • ${p.opening_hours}</span><br>
                <div style="margin-top:8px;">
                    <button onclick="window.selectPoiById('${p.id}')" style="background:#3b82f6; color:white; border:none; border-radius:4px; padding:4px 8px; font-size:11px; cursor:pointer;">
                        Navigate Here
                    </button>
                </div>
            </div>
        `);

        marker.on('click', () => {
            selectPoiById(p.id);
        });

        state.poiMarkers[p.id] = marker;
    });
}

window.selectPoiById = function(poiId) {
    const poi = state.pois.find(p => p.id === poiId);
    if (!poi) return;
    state.selectedPoi = poi;
    calculateAndDrawRoutes(poiId);
};

function renderPoiList(filterCat = '') {
    const list = document.getElementById('poi-list');
    list.innerHTML = '';

    const filtered = filterCat 
        ? state.pois.filter(p => p.category.toLowerCase() === filterCat.toLowerCase())
        : state.pois;

    filtered.forEach(p => {
        const item = document.createElement('div');
        item.className = 'poi-item';
        item.innerHTML = `
            <div class="poi-info">
                <div class="poi-icon ${p.category}"><i class="${getPoiIconClass(p.category)}"></i></div>
                <div>
                    <div class="poi-title">${p.name}</div>
                    <div class="poi-meta">${p.category.replace('_', ' ').toUpperCase()} • ${p.opening_hours}</div>
                </div>
            </div>
            <button class="btn btn-sm btn-outline"><i class="fa-solid fa-chevron-right"></i></button>
        `;
        item.addEventListener('click', () => {
            selectPoiById(p.id);
        });
        list.appendChild(item);
    });
}

// Safe Bubble Calculations and Visual Isochrone Rings
function updateSafeBubble() {
    const url = `/api/safe-bubble?lat=${state.userLat}&lon=${state.userLon}&data_age_hours=${state.dataAgeHours}`;
    fetch(url)
        .then(res => res.json())
        .then(bubble => {
            // Update stats
            const b5 = bubble.bands[0] ? bubble.bands[0].destinations.length : 0;
            const b10 = bubble.bands[1] ? bubble.bands[1].destinations.length : 0;
            const b15 = bubble.bands[2] ? bubble.bands[2].destinations.length : 0;

            document.getElementById('b5-count').textContent = b5;
            document.getElementById('b10-count').textContent = b10;
            document.getElementById('b15-count').textContent = b15;
            document.getElementById('zone-confidence').textContent = `${bubble.overall_zone_confidence}%`;

            const badge = document.getElementById('bubble-status-badge');
            badge.className = `badge ${bubble.is_in_safe_zone ? 'badge-success' : 'badge-warning'}`;
            badge.textContent = bubble.is_in_safe_zone ? 'Active' : 'Advisory';

            document.getElementById('bubble-status-msg').textContent = bubble.status_message;

            // Draw Isochrone circles
            state.bubbleLayers.forEach(l => map.removeLayer(l));
            state.bubbleLayers = [];

            // 5 min ring (Green)
            const c5 = L.circle([state.userLat, state.userLon], {
                radius: bubble.bands[0].max_distance_meters,
                color: '#10b981',
                weight: 1.5,
                fillColor: '#10b981',
                fillOpacity: 0.05,
                dashArray: '4, 4'
            }).addTo(map);

            // 10 min ring (Blue)
            const c10 = L.circle([state.userLat, state.userLon], {
                radius: bubble.bands[1].max_distance_meters,
                color: '#3b82f6',
                weight: 1.5,
                fillColor: '#3b82f6',
                fillOpacity: 0.03,
                dashArray: '6, 6'
            }).addTo(map);

            state.bubbleLayers.push(c5, c10);
        });
}

// Calculate & Visualize Safe vs Fast Routes
function calculateAndDrawRoutes(destinationId) {
    const url = `/api/route?lat=${state.userLat}&lon=${state.userLon}&destination_id=${destinationId}&data_age_hours=${state.dataAgeHours}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            state.currentRouteData = data;
            renderRouteMetrics();
            drawRoutePolylines(data.safest_route, data.fastest_route);
        });
}

function drawRoutePolylines(safest, fastest) {
    // Remove previous routes
    if (state.routeLayers.safest) map.removeLayer(state.routeLayers.safest);
    if (state.routeLayers.fastest) map.removeLayer(state.routeLayers.fastest);

    // Safest Route (Glow green / cyan line)
    state.routeLayers.safest = L.polyline(safest.path_coordinates, {
        color: '#10b981',
        weight: 6,
        opacity: 0.9,
        lineCap: 'round'
    }).addTo(map);

    // Fastest Route (Amber dashed line showing dark alley risk)
    state.routeLayers.fastest = L.polyline(fastest.path_coordinates, {
        color: '#f59e0b',
        weight: 4,
        opacity: 0.8,
        dashArray: '8, 8'
    }).addTo(map);

    // Fit map bounds to encompass both paths
    const bounds = L.latLngBounds(safest.path_coordinates.concat(fastest.path_coordinates));
    map.fitBounds(bounds, { padding: [40, 40] });
}

function renderRouteMetrics() {
    if (!state.currentRouteData) return;
    const r = state.activeRouteMode === 'safest' 
        ? state.currentRouteData.safest_route 
        : state.currentRouteData.fastest_route;

    document.getElementById('route-safety').textContent = `${r.safety_score}/100`;
    document.getElementById('route-lighting').textContent = `${r.lighting_percentage}%`;
    document.getElementById('route-time').textContent = `${r.duration_minutes} min`;
    document.getElementById('route-dist').textContent = `${r.distance_meters} m`;

    const whyList = document.getElementById('route-why-list');
    whyList.innerHTML = '';
    r.why_recommended.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        whyList.appendChild(li);
    });

    const stepsList = document.getElementById('turn-steps-list');
    stepsList.innerHTML = '';
    r.steps.forEach(st => {
        const row = document.createElement('div');
        row.className = 'step-row';
        row.innerHTML = `
            <div>
                <div>${st.instruction}</div>
                <div style="font-size:10px; color:#64748b;">${st.lighting_level}</div>
            </div>
            <div style="text-align:right; font-weight:600; color:#94a3b8;">${st.distance_meters}m</div>
        `;
        stepsList.appendChild(row);
    });
}

// Emergency "I'M NOT SAFE" Mode Trigger
function triggerEmergencyMode() {
    fetch('/api/emergency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_lat: state.userLat,
            user_lon: state.userLon,
            data_age_hours: state.dataAgeHours
        })
    })
    .then(res => res.json())
    .then(plan => {
        state.selectedPoi = plan.safest_destination;
        state.currentRouteData = {
            safest_route: plan.safest_route,
            fastest_route: plan.fastest_route,
            destination: plan.safest_destination
        };
        state.activeRouteMode = 'safest';
        document.getElementById('tab-safest').classList.add('active');
        document.getElementById('tab-fastest').classList.remove('active');

        renderRouteMetrics();
        drawRoutePolylines(plan.safest_route, plan.fastest_route || plan.safest_route);

        // Post emergency response in chat
        addChatMessage(plan.slm_guidance, 'ai', plan.abstained);

        // Speak aloud emergency guidance if speech synthesis is available
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(
                `Emergency Mode Active. Proceed immediately to ${plan.safest_destination.name}. Route duration is ${plan.safest_route.duration_minutes} minutes along illuminated streets.`
            );
            window.speechSynthesis.speak(utterance);
        }
    });
}

// Chat & SLM Copilot
function sendUserChatMessage(text) {
    if (!text || !text.trim()) return;
    const queryText = text.trim();
    addChatMessage(queryText, 'user');

    const chatContainer = document.getElementById('chat-messages');
    
    // Remove existing typing indicator if any
    const existingTyping = document.getElementById('chat-typing-indicator');
    if (existingTyping) existingTyping.remove();

    // Create typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.id = 'chat-typing-indicator';
    typingDiv.className = 'msg msg-ai';
    typingDiv.innerHTML = `
        <div class="msg-content" style="display:flex; align-items:center; gap:8px; color:var(--text-secondary);">
            <i class="fa-solid fa-circle-notch fa-spin text-cyan"></i>
            <span>Analyzing local spatial telemetry & safe corridors...</span>
        </div>
    `;
    chatContainer.appendChild(typingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: queryText,
            user_lat: state.userLat,
            user_lon: state.userLon,
            data_age_hours_override: state.dataAgeHours
        })
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`API error (${res.status} ${res.statusText})`);
        }
        return res.json();
    })
    .then(resp => {
        const typingEl = document.getElementById('chat-typing-indicator');
        if (typingEl) typingEl.remove();

        const responseText = resp.response_text || 'No response generated.';
        addChatMessage(responseText, 'ai', resp.abstained);

        if (resp.suggested_poi) {
            state.selectedPoi = resp.suggested_poi;
            
            // Highlight marker on map if present
            if (state.poiMarkers[resp.suggested_poi.id]) {
                state.poiMarkers[resp.suggested_poi.id].openPopup();
            }

            if (resp.suggested_route && resp.suggested_route.path_coordinates && resp.suggested_route.path_coordinates.length > 1) {
                state.currentRouteData = {
                    safest_route: resp.suggested_route,
                    fastest_route: resp.suggested_route,
                    destination: resp.suggested_poi
                };
                state.activeRouteMode = 'safest';
                const tabS = document.getElementById('tab-safest');
                const tabF = document.getElementById('tab-fastest');
                if (tabS) tabS.classList.add('active');
                if (tabF) tabF.classList.remove('active');

                renderRouteMetrics();
                drawRoutePolylines(resp.suggested_route, resp.suggested_route);
            }
        }

        // Voice output (safe speech synthesis)
        if ('speechSynthesis' in window && !resp.abstained && responseText) {
            try {
                window.speechSynthesis.cancel(); // Stop prior speech
                const cleanText = responseText.replace(/[*#•_`~]/g, '');
                const utter = new SpeechSynthesisUtterance(cleanText.substring(0, 200));
                utter.rate = 1.0;
                window.speechSynthesis.speak(utter);
            } catch (e) {
                console.warn('Speech synthesis notice:', e);
            }
        }
    })
    .catch(err => {
        const typingEl = document.getElementById('chat-typing-indicator');
        if (typingEl) typingEl.remove();

        console.error('Chat error:', err);
        addChatMessage(`⚠️ Unable to reach On-Device AI Copilot (${err.message}). Please ensure the server is active at http://127.0.0.1:8000.`, 'ai', true);
    });
}

function addChatMessage(content, sender, isAbstained = false) {
    const chatContainer = document.getElementById('chat-messages');
    if (!chatContainer) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `msg msg-${sender} ${isAbstained ? 'abstain' : ''}`;

    const text = String(content || '');

    // Format markdown safely and cleanly
    let formatted = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1); padding:2px 4px; border-radius:4px;">$1</code>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n• /g, '<br>• ')
        .replace(/\n- /g, '<br>• ')
        .replace(/\n(\d+)\. /g, '<br>$1. ')
        .replace(/\n/g, '<br>');

    if (sender === 'ai') {
        const tag = isAbstained
            ? `<div class="guardrail-tag" style="color:#f59e0b;"><i class="fa-solid fa-triangle-exclamation"></i> Uncertainty Aware: Abstaining due to stale evidence</div>`
            : `<div class="guardrail-tag"><i class="fa-solid fa-check-double"></i> Grounded in local spatial telemetry</div>`;

        msgDiv.innerHTML = `
            <div class="msg-content">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <strong style="color:var(--color-cyan); font-size:0.8rem;"><i class="fa-solid fa-brain"></i> SafePlace Copilot</strong>
                </div>
                <div>${formatted}</div>
                ${tag}
            </div>
        `;
    } else {
        msgDiv.innerHTML = `<div>${formatted}</div>`;
    }

    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

