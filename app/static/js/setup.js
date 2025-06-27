document.getElementById("deviceSetupForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const form = e.target;
    const data = {
        device_name: form.device_name.value.trim(),
        location_id: parseInt(form.location_id.value),
        stream_type: form.stream_type.value
    };

    try {
        const res = await fetch("/api/device/setup", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });

        const result = await res.json();
        if (res.ok) {
            document.getElementById("statusMsg").textContent = "✅ Config saved!";
        } else {
            document.getElementById("statusMsg").textContent = "❌ Error: " + result.error;
        }
    } catch (err) {
        document.getElementById("statusMsg").textContent = "❌ Request failed: " + err.message;
    }
});
