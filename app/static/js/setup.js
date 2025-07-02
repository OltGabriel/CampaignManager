console.log("setup.js loaded");
console.log("deviceSetupForm:", document.getElementById("deviceSetupForm"));

// On page load, check if device is already configured
// window.addEventListener("DOMContentLoaded", async function () {
//     try {
//         const res = await fetch("/api/device/configured");
//         if (res.ok) {
//             const result = await res.json();
//             if (result.configured) {
//                 // Always redirect to video stream
//                 window.location.href = "/video";
//                 return;
//             }
//         }
//     } catch (err) {
//         // Ignore errors, allow setup to proceed
//     }
// });

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
        console.log("setup: status", res.status, "type", res.type, "body", result);
        if (res.ok) {
            document.getElementById("statusMsg").textContent = "✅ Config saved! Redirecting...";
            console.log("Redirecting based on stream_type...");
            if (data.stream_type === "audio") {
                window.location.href = "/audio";
            } else {
                window.location.href = "/video";
            }
        } else {
            document.getElementById("statusMsg").textContent = "❌ Error: " + result.error;
        }
    } catch (err) {
        document.getElementById("statusMsg").textContent = "❌ Request failed: " + err.message;
    }
});
