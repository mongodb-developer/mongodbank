// Initialize variables
let map, nyMarker, parisMarker, alertMarker;

// Define locations
const newYork = [40.7128, -74.0060];
const paris = [48.8566, 2.3522];

// Initialize the map and markers
function initMap() {
    map = L.map('fraud-map').setView([40.7128, -74.0060], 3);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    nyMarker = L.marker(newYork, {
        icon: L.divIcon({className: 'transaction-marker'}),
        opacity: 0
    }).addTo(map).bindPopup("Transaction in New York: $5000");

    parisMarker = L.marker(paris, {
        icon: L.divIcon({className: 'transaction-marker'}),
        opacity: 0
    }).addTo(map).bindPopup("Transaction in Paris: $3000");
    
    alertMarker = L.marker(paris, {
        icon: L.divIcon({className: 'fraud-alert', html: 'FRAUD&nbsp;ALERT!'}),
        opacity: 0
    });

    // Ensure map is fully loaded before allowing animation to start
    map.whenReady(() => {
        const startButton = document.getElementById('start-animation');
        if (startButton) {
            startButton.disabled = false;
            startButton.addEventListener('click', startAnimation);
        } else {
            console.error("Start animation button not found");
        }
    });
}

function startAnimation() {
    if (!map || !nyMarker || !parisMarker || !alertMarker) {
        console.error("Map or markers not initialized");
        return;
    }

    // Reset map view
    map.setView([40.7128, -74.0060], 3);
    
    // Animation sequence
    setTimeout(() => {
        nyMarker.setOpacity(1).openPopup();
        showTextMessage("Transaction in New York detected: $5000", 3000); // Display for 3 seconds
        setTimeout(() => {
            map.flyTo(newYork, 6, {
                duration: 2,
                easeLinearity: 0.5
            });
            setTimeout(() => {
                map.flyTo(paris, 6, {
                    duration: 3,
                    easeLinearity: 0.5
                });
                setTimeout(() => {
                    parisMarker.setOpacity(1).openPopup();
                    showTextMessage("Transaction in Paris detected: $3000", 3000); // Display for 3 seconds
                    setTimeout(() => {
                        alertMarker.addTo(map).setOpacity(1);
                        pulseAlertMarker();
                        shakeMap();
                        showTextMessage("FRAUD ALERT! Transactions in multiple locations.", 5000); // Display for 5 seconds
                        setTimeout(() => {
                            nyMarker.setOpacity(0).closePopup();
                            parisMarker.setOpacity(0).closePopup();
                            map.removeLayer(alertMarker);
                        }, 5000);
                    }, 1000);
                }, 3000);
            }, 2000);
        }, 1000);
    }, 0);
}

function pulseAlertMarker() {
    let scale = 1;
    const pulseInterval = setInterval(() => {
        scale = scale === 1 ? 1.2 : 1;
        alertMarker.getElement().style.transform = `scale(${scale})`;
    }, 500);

    setTimeout(() => {
        clearInterval(pulseInterval);
    }, 4000);
}

function shakeMap() {
    let shakeInterval = setInterval(() => {
        map.panBy([10, 0], {animate: true, duration: 0.05});
        setTimeout(() => map.panBy([-20, 0], {animate: true, duration: 0.05}), 50);
        setTimeout(() => map.panBy([10, 0], {animate: true, duration: 0.05}), 100);
    }, 300);

    setTimeout(() => {
        clearInterval(shakeInterval);
    }, 2000);
}

function showTextMessage(message, duration = 5000) {
    const messageElement = document.getElementById('fraud-warning');
    messageElement.innerHTML = message;
    messageElement.classList.remove('d-none');
    setTimeout(() => {
        messageElement.classList.add('d-none');
    }, duration);
}

// Initialize everything when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initMap);
