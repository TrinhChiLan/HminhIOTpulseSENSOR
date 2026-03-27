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

        document.getElementById("bpm").innerText = data.bpm;

        chart.data.datasets[0].data.push(data.bpm);
        if(chart.data.datasets[0].data.length > 20) chart.data.datasets[0].data.shift();
        chart.update();

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
                    <span class="bpm-val">${item.bpm} BPM</span>
                    <span class="time-val">${item.date}${item.time}</span>
                </div>
            `).join('');
        }
    } catch (e) {}
}

setInterval(update, 1000);
setInterval(fetchHistory, 30000); // Fetch history every 30s
fetchHistory();
