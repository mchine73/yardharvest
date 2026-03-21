// YardHarvest Map Utilities (Leaflet.js + OpenStreetMap)

const YHMap = {
    init(containerId, centerLat, centerLon, zoom) {
        zoom = zoom || 13;
        const map = L.map(containerId).setView([centerLat, centerLon], zoom);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 18
        }).addTo(map);
        return map;
    },

    addListingMarker(map, lat, lon, title, price, url) {
        const marker = L.marker([lat, lon]).addTo(map);
        // Use DOM API to prevent XSS — never concatenate user input into HTML
        const div = document.createElement('div');
        const strong = document.createElement('strong');
        strong.textContent = title;
        div.appendChild(strong);
        div.appendChild(document.createElement('br'));
        div.appendChild(document.createTextNode('$' + price));
        div.appendChild(document.createElement('br'));
        const link = document.createElement('a');
        link.href = url;
        link.textContent = 'View Details';
        div.appendChild(link);
        marker.bindPopup(div);
        return marker;
    },

    addDeliveryZone(map, lat, lon, radiusMiles) {
        return L.circle([lat, lon], {
            radius: radiusMiles * 1609.34,
            color: '#2D6A4F',
            fillColor: '#2D6A4F',
            fillOpacity: 0.08,
            weight: 2,
            dashArray: '5, 10'
        }).addTo(map).bindPopup('Delivery zone (' + radiusMiles + ' mi)');
    },

    fitToMarkers(map, markers) {
        if (markers.length > 0) {
            const group = L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.1));
        }
    }
};
