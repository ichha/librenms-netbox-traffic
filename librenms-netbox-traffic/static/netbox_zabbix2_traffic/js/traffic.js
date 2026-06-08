document.addEventListener("DOMContentLoaded", function () {
    // 1. Extract device and interface details from script attributes
    const scriptElement = document.querySelector('script[src*="traffic.js"]');
    if (!scriptElement) return;

    const deviceName = scriptElement.getAttribute("data-device");
    const interfaceName = scriptElement.getAttribute("data-interface");
    if (!deviceName || !interfaceName) return;

    // 2. Select DOM elements
    const loadingEl = document.getElementById("zabbix-loading");
    const errorEl = document.getElementById("zabbix-error");
    const errorMsgEl = document.getElementById("zabbix-error-msg");
    const chartWrapperEl = document.getElementById("zabbix-chart-wrapper");
    const rangeButtons = document.querySelectorAll(".btn-range");

    let currentChart = null;
    let currentRange = "1d";

    // 3. Formatter function for bits per second (bps)
    function formatBps(bps) {
        if (bps === undefined || bps === null || isNaN(bps)) return "0 bps";
        if (bps >= 1e9) {
            return (bps / 1e9).toFixed(2) + " Gbps";
        } else if (bps >= 1e6) {
            return (bps / 1e6).toFixed(2) + " Mbps";
        } else if (bps >= 1e3) {
            return (bps / 1e3).toFixed(2) + " kbps";
        } else {
            return bps.toFixed(2) + " bps";
        }
    }

    // 4. Fetch data from custom Django proxy API endpoint (zabbix2-traffic base URL)
    async function fetchTrafficData(range) {
        // Toggle loading UI
        loadingEl.classList.remove("d-none");
        errorEl.classList.add("d-none");
        chartWrapperEl.classList.add("d-none");

        const apiUrl = `/api/plugins/zabbix2-traffic/traffic-data/?device=${encodeURIComponent(deviceName)}&interface=${encodeURIComponent(interfaceName)}&range=${range}`;

        try {
            const response = await fetch(apiUrl);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }

            renderChartAndStats(data, range);
        } catch (error) {
            console.error("Zabbix integration error:", error);
            errorMsgEl.textContent = error.message;
            errorEl.classList.remove("d-none");
            loadingEl.classList.add("d-none");
        }
    }

    // 5. Render dynamic Chart.js lines & fill out Legend Stats table
    function renderChartAndStats(data, range) {
        loadingEl.classList.add("d-none");
        chartWrapperEl.classList.remove("d-none");

        // Extract datasets
        const inHistory = data.history.in || [];
        const outHistory = data.history.out || [];

        // Align coordinates and build X-axis labels
        const primaryHistory = inHistory.length >= outHistory.length ? inHistory : outHistory;
        const labels = primaryHistory.map(item => {
            const d = new Date(item.x);
            if (range === "1d" || range === "2d") {
                return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
            } else {
                return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
            }
        });

        const inValues = inHistory.map(item => item.y);
        const outValues = outHistory.map(item => item.y);

        // Update Bottom Statistics Table
        document.getElementById("stat-in-last").textContent = formatBps(data.stats.in.last);
        document.getElementById("stat-in-min").textContent = formatBps(data.stats.in.min);
        document.getElementById("stat-in-avg").textContent = formatBps(data.stats.in.avg);
        document.getElementById("stat-in-max").textContent = formatBps(data.stats.in.max);

        document.getElementById("stat-out-last").textContent = formatBps(data.stats.out.last);
        document.getElementById("stat-out-min").textContent = formatBps(data.stats.out.min);
        document.getElementById("stat-out-avg").textContent = formatBps(data.stats.out.avg);
        document.getElementById("stat-out-max").textContent = formatBps(data.stats.out.max);

        // Setup Chart
        const ctx = document.getElementById("zabbixTrafficChart").getContext("2d");

        // Destroy previous chart if it exists to avoid rendering bugs
        if (currentChart) {
            currentChart.destroy();
        }

        // Create gradient fills
        const inGradient = ctx.createLinearGradient(0, 0, 0, 350);
        inGradient.addColorStop(0, "rgba(46, 204, 113, 0.45)");
        inGradient.addColorStop(1, "rgba(46, 204, 113, 0.01)");

        const outGradient = ctx.createLinearGradient(0, 0, 0, 350);
        outGradient.addColorStop(0, "rgba(241, 196, 15, 0.45)");
        outGradient.addColorStop(1, "rgba(241, 196, 15, 0.01)");

        currentChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Bits received (Inbound)",
                        data: inValues,
                        borderColor: "#2ecc71",
                        borderWidth: 2.2,
                        backgroundColor: inGradient,
                        fill: true,
                        tension: 0.22,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        pointBackgroundColor: "#2ecc71",
                        pointBorderColor: "#fff",
                    },
                    {
                        label: "Bits sent (Outbound)",
                        data: outValues,
                        borderColor: "#f1c40f",
                        borderWidth: 2.2,
                        backgroundColor: outGradient,
                        fill: true,
                        tension: 0.22,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        pointBackgroundColor: "#f1c40f",
                        pointBorderColor: "#fff",
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: false, // Custom styled legend table used instead
                    },
                    tooltip: {
                        backgroundColor: "rgba(33, 37, 41, 0.95)",
                        titleColor: "#f8f9fa",
                        bodyColor: "#f8f9fa",
                        borderColor: "rgba(255, 255, 255, 0.1)",
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 6,
                        callbacks: {
                            label: function (context) {
                                let label = context.dataset.label || "";
                                if (label) {
                                    label += ": ";
                                }
                                if (context.parsed.y !== null) {
                                    label += formatBps(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: "rgba(108, 117, 125, 0.08)",
                        },
                        ticks: {
                            color: "#6c757d",
                            font: {
                                size: 11
                            },
                            maxRotation: 0,
                            autoSkip: true,
                            autoSkipPadding: 45
                        }
                    },
                    y: {
                        grid: {
                            color: "rgba(108, 117, 125, 0.08)",
                        },
                        ticks: {
                            color: "#6c757d",
                            font: {
                                size: 11
                            },
                            callback: function (value) {
                                return formatBps(value);
                            }
                        }
                    }
                }
            }
        });
    }

    // 6. Bind range filter button click events
    rangeButtons.forEach(button => {
        button.addEventListener("click", function () {
            rangeButtons.forEach(b => b.classList.remove("active"));
            this.classList.add("active");

            currentRange = this.getAttribute("data-range");
            fetchTrafficData(currentRange);
        });
    });

    // 7. Initial loading call
    fetchTrafficData(currentRange);
});
