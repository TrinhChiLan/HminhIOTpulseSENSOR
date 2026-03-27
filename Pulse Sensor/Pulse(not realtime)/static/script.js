const ctx = document.getElementById('chart').getContext('2d');

const chart = new Chart(ctx,{
    type:'line',
    data:{
        labels:Array(20).fill(''),
        datasets:[{
            data:Array(20).fill(0),
            borderColor:'rgba(255, 0, 0, 1)',
            backgroundColor: 'rgba(255, 0, 0, 0.1)',
            borderWidth: 3,
            fill: true,
            tension:0.4,
            pointBackgroundColor: 'rgba(255, 0, 0, 1)',
            pointBorderColor: 'rgba(255, 0, 0, 1)',
            pointRadius: 2,
            pointHoverRadius: 6
        }]
    },
    options:{
        responsive: true,
        plugins:{
            legend:{display:false},
        },
        scales:{
            y:{
                min:40,
                max:150,
                grid: { color: '#eee' },
                ticks: { color: '#666' }
            },
            x: {
                display: false
            }
        },
        animation: { duration: 0 }
    }
});

const ctxSpo2 = document.getElementById('spo2-chart').getContext('2d');
const spo2Chart = new Chart(ctxSpo2,{
    type:'line',
    data:{
        labels:Array(20).fill(''),
        datasets:[{
            data:Array(20).fill(0),
            borderColor:'rgba(0, 122, 255, 1)',
            backgroundColor: 'rgba(0, 122, 255, 0.1)',
            borderWidth: 3,
            fill: true,
            tension:0.4,
            pointBackgroundColor: 'rgba(0, 122, 255, 1)',
            pointBorderColor: 'rgba(0, 122, 255, 1)',
            pointRadius: 2,
            pointHoverRadius: 6
        }]
    },
    options:{
        responsive: true,
        plugins:{
            legend:{display:false},
        },
        scales:{
            y:{
                min:75,
                max:100,
                grid: { color: '#eee' },
                ticks: { color: '#666' }
            },
            x: {
                display: false
            }
        },
        animation: { duration: 0 }
    }
});


async function update(){
    try {
        let res = await fetch('/bpm')
        let data = await res.json()

        if (!data.logged_in) {
            document.getElementById("login-overlay").style.display = "flex";
            document.querySelector(".main-content").style.display = "none";
            return;
        } else {
            document.getElementById("login-overlay").style.display = "none";
            document.querySelector(".main-content").style.display = "block";
            document.getElementById("user-display").innerText = "User: " + data.phone;
        }

        const overlay = document.getElementById("sensor-overlay");
        const banner = document.getElementById("completion-banner");
        const overlayTitle = document.getElementById("sensor-status-title");
        const overlayDesc = document.getElementById("sensor-status-desc");
        const overlayProgressCont = document.getElementById("sensor-progress-bar");
        const overlayProgress = document.getElementById("sensor-progress");
        const liveIndicator = document.getElementById("live-indicator");

        if (data.status === "waiting" || data.status === "detecting" || !data.status) {
            overlay.style.display = "flex";
            banner.style.display = "none";
            overlayTitle.innerText = "Waiting for Sensor...";
            overlayDesc.innerText = "Please place your finger on the sensor.";
            overlayProgressCont.style.display = "none";
            if (liveIndicator) liveIndicator.style.display = "none";
            document.getElementById("bpm").innerText = "--";
            document.getElementById("spo2").innerText = "--";
            
            chart.data.datasets[0].data = Array(20).fill(0);
            chart.update();
            spo2Chart.data.datasets[0].data = Array(20).fill(0);
            spo2Chart.update();
        } else if (data.status === "stabilizing") {
            overlay.style.display = "flex";
            banner.style.display = "none";
            overlayTitle.innerText = "Stabilizing...";
            overlayDesc.innerText = `Please wait, stabilizing signal... ${data.progress}%`;
            overlayProgressCont.style.display = "block";
            overlayProgress.style.width = `${data.progress}%`;
            if (liveIndicator) liveIndicator.style.display = "none";
            
            document.getElementById("bpm").innerText = "--";
            document.getElementById("spo2").innerText = "--";
            chart.data.datasets[0].data = Array(20).fill(0);
            chart.update();
            spo2Chart.data.datasets[0].data = Array(20).fill(0);
            spo2Chart.update();
        } else if (data.status === "reading" || data.status === "completed") {
            overlay.style.display = "none";
            if (data.status === "completed") {
                banner.style.display = "block";
                if (liveIndicator) liveIndicator.style.display = "none";
            } else {
                banner.style.display = "none";
                if (liveIndicator) liveIndicator.style.display = "block";
            }
            
            document.getElementById("bpm").innerText = data.bpm > 0 ? data.bpm : "--";
            document.getElementById("spo2").innerText = data.spo2 > 0 ? data.spo2.toFixed(1) : "--";

            if (data.bpm > 0) {
                chart.data.datasets[0].data.push(data.bpm);
                if(chart.data.datasets[0].data.length > 20) chart.data.datasets[0].data.shift();
                chart.update();

                spo2Chart.data.datasets[0].data.push(data.spo2);
                if(spo2Chart.data.datasets[0].data.length > 20) spo2Chart.data.datasets[0].data.shift();
                spo2Chart.update();
            }
        }

    } catch (e) {
        console.error("Update error:", e);
    }
}

async function login() {
    const phone = document.getElementById("phone-input").value;
    if (!phone) return alert("Please enter a phone number");

    const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone })
    });
    const data = await res.json();
    if (data.success) {
        document.getElementById("login-overlay").style.display = "none";
        document.querySelector(".main-content").style.display = "block";
        fetchHistory();
    }
}

async function logout() {
    await fetch("/logout");
    location.reload();
}

async function fetchHistory() {
    try {
        const res = await fetch("/history");
        const data = await res.json();
        const list = document.getElementById("history-list");
        if (data.success) {
            if (data.history.length === 0) {
                list.innerHTML = "<p style='padding:15px'>No recordings yet. Waiting for automatic log (every 1 min)...</p>";
                return;
            }
            list.innerHTML = data.history.map(item => `
                <div class="history-item">
                    <span class="bpm-val">${item.bpm} BPM ${item.spo2 ? '| ' + item.spo2 + '% SpO2' : ''}</span>
                    <span class="time-val">${item.date}${item.time}</span>
                </div>
            `).join('');
        }
    } catch (e) {}
}

setInterval(update, 1000);
setInterval(fetchHistory, 30000); // Fetch history every 30s
fetchHistory();
