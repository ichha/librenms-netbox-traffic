document.addEventListener("DOMContentLoaded", function () {
    // 1. Extract device and interface details from script attributes
    const scriptElement = document.querySelector('script[src*="traffic.js"]');
    if (!scriptElement) return;

    const deviceName = scriptElement.getAttribute("data-device");
    const interfaceName = scriptElement.getAttribute("data-interface");
    if (!deviceName || !interfaceName) return;

    // 2. Select DOM elements
    const cardEl = document.getElementById("librenms-traffic-card");
    const loadingEl = document.getElementById("librenms-loading");
    const errorEl = document.getElementById("librenms-error");
    const errorMsgEl = document.getElementById("librenms-error-msg");
    const wrapperEl = document.getElementById("librenms-graph-wrapper");
    const imgEl = document.getElementById("librenms-graph-img");
    const rangeButtons = document.querySelectorAll(".btn-range");

    let currentRange = "1d";

    // 3. Move the card to the top section of the page (inside active tab content or main grid)
    if (cardEl) {
        // Look for main detail view columns, tab pane, or main content container
        const targetContainer = document.querySelector(".tab-pane.active") || 
                                document.querySelector(".tab-content") || 
                                document.querySelector(".col-md-9") || 
                                document.querySelector(".col-12") ||
                                document.querySelector(".content-body") || 
                                document.querySelector("main");
        if (targetContainer) {
            targetContainer.insertBefore(cardEl, targetContainer.firstChild);
        }
    }

    // 4. Function to load LibreNMS graph
    function loadGraph(range) {
        loadingEl.classList.remove("d-none");
        errorEl.classList.add("d-none");
        wrapperEl.classList.add("d-none");

        const apiUrl = `/api/plugins/librenms-traffic/traffic-data/?device=${encodeURIComponent(deviceName)}&interface=${encodeURIComponent(interfaceName)}&range=${range}`;

        // Set image source (browser will perform auth natively using session cookies)
        imgEl.src = apiUrl;
    }

    // 5. Image load and error handlers
    imgEl.onload = function () {
        loadingEl.classList.add("d-none");
        wrapperEl.classList.remove("d-none");
        errorEl.classList.add("d-none");
    };

    imgEl.onerror = async function () {
        loadingEl.classList.add("d-none");
        wrapperEl.classList.add("d-none");
        errorEl.classList.remove("d-none");
        
        try {
            // Fetch the URL to parse the JSON or text error body returned by Django proxy
            const res = await fetch(imgEl.src);
            if (!res.ok) {
                const text = await res.text();
                try {
                    const data = JSON.parse(text);
                    errorMsgEl.textContent = data.error || "Failed to load LibreNMS graph image.";
                } catch (jsonErr) {
                    // Fallback to text snippet (e.g. if it's an HTML error page)
                    errorMsgEl.textContent = text.substring(0, 150) || "Failed to load LibreNMS graph image.";
                }
            } else {
                errorMsgEl.textContent = "Failed to load LibreNMS graph image.";
            }
        } catch (e) {
            errorMsgEl.textContent = "Failed to connect to LibreNMS or retrieve graph details.";
        }
    };

    // 6. Bind range filter button click events
    rangeButtons.forEach(button => {
        button.addEventListener("click", function () {
            rangeButtons.forEach(b => b.classList.remove("active"));
            this.classList.add("active");

            currentRange = this.getAttribute("data-range");
            loadGraph(currentRange);
        });
    });

    // 7. Initial loading call
    loadGraph(currentRange);
});
