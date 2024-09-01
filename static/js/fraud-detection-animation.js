// Initialize the map
var map = L.map('fraud-map').setView([40.7128, -74.0060], 3);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// Define locations
var newYork = [40.7128, -74.0060];
var paris = [48.8566, 2.3522];

// Create markers
var nyMarker = L.marker(newYork, {icon: L.divIcon({className: 'transaction-marker'})}).addTo(map);
var parisMarker = L.marker(paris, {icon: L.divIcon({className: 'transaction-marker'})}).addTo(map);
var alertMarker = L.marker(paris, {icon: L.divIcon({className: 'fraud-alert', html: 'FRAUD ALERT!'})});

// Hide markers initially
nyMarker.setOpacity(0);
parisMarker.setOpacity(0);

function startAnimation() {
    // Reset map view
    map.setView([40.7128, -74.0060], 3);
    
    // Animation timeline
    var tl = gsap.timeline();

    tl.to(nyMarker._icon, {duration: 1, opacity: 1, ease: "power2.inOut"})
      .to({}, {duration: 1}) // pause
      .to(map, {duration: 2, zoom: 4, center: newYork, ease: "power2.inOut"})
      .to({}, {duration: 1}) // pause
      .to(map, {duration: 3, center: paris, ease: "power2.inOut"})
      .to(parisMarker._icon, {duration: 1, opacity: 1, ease: "power2.inOut"})
      .call(() => alertMarker.addTo(map))
      .to(alertMarker._icon, {duration: 0.5, scale: 1.2, repeat: 3, yoyo: true})
      .to({}, {duration: 2}) // pause at the end
      .call(() => {
          nyMarker.setOpacity(0);
          parisMarker.setOpacity(0);
          map.removeLayer(alertMarker);
      });
}

document.getElementById('start-animation').addEventListener('click', startAnimation);