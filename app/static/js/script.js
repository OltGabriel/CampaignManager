const player = document.getElementById("videoPlayer");
const nextButton = document.getElementById("nextButton");
const dashboard = document.getElementById("dashboard");

let dashboardVisible = false;
let statusUpdateInterval;
let currentVideoInfo = null;
let retryCount = 0;
const maxRetries = 3;

// Show status message
function showStatus(message, type = 'success') {
    const statusEl = document.getElementById("statusMessage");
    const className = type === 'error' ? 'error-message' : 
                    type === 'warning' ? 'warning-message' : 'success-message';
    statusEl.innerHTML = `<div class="${className}">${message}</div>`;
    setTimeout(() => {
        statusEl.innerHTML = "";
    }, 5000);
}

// Load next video
async function loadVideo(forceNext = false) {
    console.log("Loading next video...", forceNext ? "(forced next)" : "");
    nextButton.disabled = true;

    const placeholderImage = document.getElementById("placeholderImage");

    try {
        const url = forceNext ?
            `/next-video?skip=true&_t=${Date.now()}` :
            `/next-video?_t=${Date.now()}`;

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const contentType = (response.headers.get("content-type") || "").toLowerCase();
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);

        // Cleanup
        if (player.src && player.src.startsWith('blob:')) {
            URL.revokeObjectURL(player.src);
        }
        if (placeholderImage.src && placeholderImage.src.startsWith('blob:')) {
            URL.revokeObjectURL(placeholderImage.src);
        }

        if (contentType.includes("video")) {
            console.log("Received video, setting player...");
            placeholderImage.style.display = "none";
            placeholderImage.src = "";

            player.src = blobUrl;
            player.style.display = "block";


            player.onloadeddata = () => {
                console.log("Video loaded, attempting to play...");

                // Ascundem placeholder-ul doar după ce video-ul e gata
                placeholderImage.style.display = "none";
                placeholderImage.src = "";

                player.style.display = "block";
                
                player.play().then(() => {
                    console.log("Video playing successfully");
                    setTimeout(updateVideoInfo, 500);
                    showStatus(forceNext ? "Skipped to next video" : "Video loaded successfully");
                }).catch(err => {
                    console.error("Error playing video:", err);
                    showStatus("Error playing video: " + err.message, 'error');
                });
            };


            player.onerror = (e) => {
                console.error("Video error:", e);
                showStatus("Video error occurred", 'error');
            };

        } else if (contentType.includes("image")) {
            console.log("Received placeholder image");
            player.pause();
            player.removeAttribute('src'); // 🔁 RESET VIDEO
            player.load();
            player.style.display = "none";

            placeholderImage.src = blobUrl;
            placeholderImage.style.display = "block";

            showStatus("Showing placeholder (no scheduled content)", 'warning');
        } else {
            throw new Error("Unsupported content type: " + contentType);
        }

        retryCount = 0;
    } catch (error) {
        console.error("Error loading content:", error);
        showStatus("Error loading content: " + error.message, 'error');

        if (retryCount < maxRetries) {
            retryCount++;
            showStatus(`Retrying... (${retryCount}/${maxRetries})`, 'warning');
            setTimeout(() => loadVideo(forceNext), 2000);
        }
    }

    nextButton.disabled = false;
}


// Skip to next video
function skipVideo() {
    console.log("Skip video requested - forcing next video");
    retryCount = 0; // Reset retry count for manual skip
    
    // Stop current video immediately
    player.pause();
    
    // Force load next video with skip parameter
    loadVideo(true);
}

// Update video information
async function updateVideoInfo() {
    try {
        console.log("Fetching current video info...");
        const response = await fetch("/api/current-video-id");
        
        if (!response.ok) {
            console.error("Failed to fetch video info:", response.status, response.statusText);
            
            if (response.status === 404) {
                // Handle 404 gracefully - might be startup issue
                document.getElementById("videoID").textContent = "No video loaded";
                document.getElementById("videoType").innerHTML = '<span class="status-indicator status-inactive"></span>Not loaded';
                document.getElementById("videoFile").textContent = "-";
                document.getElementById("campaignInfo").style.display = "none";
                return;
            }
            
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        currentVideoInfo = data;
        console.log("Video info received:", data);

        document.getElementById("videoID").textContent = data.id || "unknown";
        document.getElementById("videoFile").textContent = data.filename || "-";
        
        const typeSpan = document.getElementById("videoType");
        const campaignInfo = document.getElementById("campaignInfo");
        
        if (data.type === "campaign") {
            typeSpan.innerHTML = '<span class="status-indicator status-campaign"></span>Campaign';
            if (data.campaign_name) {
                document.getElementById("campaignName").textContent = data.campaign_name;
                campaignInfo.style.display = "block";
            } else {
                campaignInfo.style.display = "none";
            }
        } else {
            typeSpan.innerHTML = '<span class="status-indicator status-filler"></span>Filler';
            campaignInfo.style.display = "none";
        }
        
        // Show status info if available
        if (data.status) {
            showStatus(data.status, 'warning');
        }
        
    } catch (err) {
        console.error("Failed to fetch video info:", err);
        document.getElementById("videoID").textContent = "error";
        document.getElementById("videoType").innerHTML = '<span class="status-indicator status-inactive"></span>Error';
        document.getElementById("campaignInfo").style.display = "none";
        showStatus("Failed to get video info: " + err.message, 'error');
    }
}

// Update campaign status
async function updateCampaignStatus() {
    try {
        const response = await fetch("/api/campaign-status");
        const data = await response.json();

        // Update current time
        const time = new Date(data.current_time).toLocaleTimeString();
        document.getElementById("currentTime").textContent = time;

        // Update active campaigns count
        const activeCampaigns = data.total_campaigns || 0;
        document.getElementById("activeCampaigns").textContent = activeCampaigns;

        // remove call to nonexistent updateCampaignDashboard()
        // updateCampaignDashboard(data.campaigns);

    } catch (err) {
        console.error("Failed to fetch campaign status:", err);
        document.getElementById("activeCampaigns").textContent = "error";
        showStatus("Failed to get campaign status: " + err.message, 'error');
    }
}


// Update campaign dashboard
function updateCampaignDashboardFromSchedule(scheduleData) {
    const listEl = document.getElementById("campaignList");
    const now = new Date();

    const scheduleDateStr = scheduleData.schedule_date; // ex: "26-06-2025"
    const playlist = scheduleData.playlist || [];

    if (!playlist.length) {
        listEl.innerHTML = "<p>No schedule entries available</p>";
        return;
    }

    // Parse date string into JS Date (day-month-year)
    const [day, month, year] = scheduleDateStr.split("-");
    const scheduleDate = new Date(`${year}-${month}-${day}`);

    let html = "";
    let currentFound = false;

    playlist.forEach((item, index) => {
        const itemTimeStr = item.at;
        const duration = item.duration || 30;

        const [h, m, s] = itemTimeStr.split(":").map(Number);
        const itemStart = new Date(scheduleDate);
        itemStart.setHours(h, m, s);

        const itemEnd = new Date(itemStart.getTime() + duration * 1000);

        let status = "future";
        if (now >= itemStart && now <= itemEnd) {
            status = "current";
            currentFound = true;
        } else if (now > itemEnd) {
            status = "past";
        }

        html += `
            <div class="schedule-item item-${status}" id="schedule-item-${index}">
                <strong>${item.name || item.id}</strong> (${item.type})<br>
                <small>${item.at} – ${duration}s</small>
            </div>
        `;
    });

    listEl.innerHTML = html;

    // Scroll to current
    if (currentFound) {
        const currentEl = listEl.querySelector(".item-current");
        if (currentEl) {
            currentEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }
}




// Toggle dashboard visibility
async function toggleDashboard() {
    dashboardVisible = !dashboardVisible;
    dashboard.style.display = dashboardVisible ? "block" : "none";

    if (dashboardVisible) {
        try {
            const res = await fetch("/api/schedule-status");
            const data = await res.json();
            updateCampaignDashboardFromSchedule(data);
        } catch (err) {
            console.error("Error loading schedule dashboard", err);
            document.getElementById("campaignList").innerHTML = "<p>Error loading schedule</p>";
        }
    }
}




// Refresh all status information
function refreshStatus() {
    console.log("Refreshing status...");
    updateVideoInfo();
    updateCampaignStatus();
    showStatus("Status refreshed");
}

// Handle video end - auto-load next video
player.addEventListener('ended', () => {
    console.log("Video ended, loading next...");
    setTimeout(() => loadVideo(false), 1000); // Small delay before loading next, don't force skip
});

// Handle player errors
player.addEventListener('error', (e) => {
    console.error("Player error:", e);
    showStatus("Video playback error", 'error');
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    switch(e.key) {
        case ' ':
        case 'Enter':
            e.preventDefault();
            skipVideo();
            break;
        case 'd':
        case 'D':
            toggleDashboard();
            break;
        case 'r':
        case 'R':
            refreshStatus();
            break;
    }
});

// Initialize on page load
window.addEventListener('load', () => {
    console.log("Page loaded, initializing...");
    
    // Initial load (not a skip)
    loadVideo(false);
    updateCampaignStatus();
    
    // Set up periodic status updates (every 30 seconds)
    statusUpdateInterval = setInterval(() => {
        updateCampaignStatus();
        // Also update video info periodically in case backend state changed
        updateVideoInfo();
    }, 30000);
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
    }
    
    // Clean up blob URLs
    if (player.src && player.src.startsWith('blob:')) {
        URL.revokeObjectURL(player.src);
    }
});

// Add some visual feedback for button interactions
document.querySelectorAll('button').forEach(button => {
    button.addEventListener('click', function() {
        this.style.transform = 'scale(0.95)';
        setTimeout(() => {
            this.style.transform = 'scale(1)';
        }, 100);
    });
});

console.log("Campaign Video Player initialized");