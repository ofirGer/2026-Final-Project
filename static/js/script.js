function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

async function updateDashboard() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();

        // 1. PROCESS AND AGGREGATE NETWORK FILES (THE SWARM LOGIC)
        const networkFiles = {};

        for (const [peerId, peerData] of Object.entries(data.peers)) {
            for (const [file_id, meta] of Object.entries(peerData.files)) {
                // Skip files that we are already sharing ourselves
                if (data.my_files[file_id]) continue;

                if (!networkFiles[file_id]) {
                    networkFiles[file_id] = { meta: meta, peers: new Set() };
                }
                networkFiles[file_id].peers.add(peerData.ip);
            }
        }

        // Render Network Files List
        const networkList = document.getElementById('network-files-list');
        networkList.innerHTML = '';
        let foundFiles = false;

        for (const [file_id, fileData] of Object.entries(networkFiles)) {
            foundFiles = true;
            const peerCount = fileData.peers.size;

            // Logic to display Swarm badge if more than 1 peer has the file
            let peerBadge = `<span class="badge peer-badge">1 Peer</span>`;
            if (peerCount > 1) {
                peerBadge = `<span class="badge swarm-badge">⚡ ${peerCount} Peers (Swarm)</span>`;
            }

            networkList.innerHTML += `
                <li>
                    <div class="file-info">
                        <span class="file-name">${fileData.meta.filename}</span>
                        <div class="file-meta">
                            <span class="badge">${formatBytes(fileData.meta.size)}</span>
                            ${peerBadge}
                        </div>
                    </div>
                    <form action="/download" method="post" style="margin:0;">
                        <input type="hidden" name="file_id" value="${file_id}">
                        <button type="submit" class="btn-success">Download</button>
                    </form>
                </li>`;
        }

        if (!foundFiles) {
            networkList.innerHTML = '<li class="empty-state">No network files discovered yet.</li>';
        }

        // 2. UPDATE MY SHARED FILES
        const myFilesList = document.getElementById('my-files-list');
        myFilesList.innerHTML = '';
        let foundMyFiles = false;

        for (const [file_id, meta] of Object.entries(data.my_files)) {
            foundMyFiles = true;
            myFilesList.innerHTML += `
                <li>
                    <div class="file-info">
                        <a href="/open/${file_id}" target="_blank" class="file-name">${meta.filename}</a>
                        <div class="file-meta">
                            <span class="badge">${formatBytes(meta.size)}</span>
                        </div>
                    </div>
                    <form action="/remove" method="post" style="margin: 0;">
                        <input type="hidden" name="file_id" value="${file_id}">
                        <button type="submit" class="btn-remove">Remove</button>
                    </form>
                </li>`;
        }

        if (!foundMyFiles) {
            myFilesList.innerHTML = '<li class="empty-state">You are not sharing any files.</li>';
        }

        // 3. UPDATE ACTIVE DOWNLOADS
        const downloadList = document.getElementById('download-list');
        downloadList.innerHTML = '';
        const downloads = data.downloads || {};

        if (Object.keys(downloads).length === 0) {
             downloadList.innerHTML = '<li class="empty-state">No active downloads</li>';
        } else {
            for (const [file_id, downloadInfo] of Object.entries(downloads)) {
                let displayProgress = downloadInfo.progress;
                let barColor = "var(--success-color)";
                let barWidth = downloadInfo.progress;

                // Check for Failed State
                if (displayProgress === "Failed" || String(displayProgress).includes("Failed")) {
                    displayProgress = "Failed (Disconnected)";
                    barColor = "var(--danger-color)";
                    barWidth = 100;
                } else {
                    displayProgress = displayProgress + "%";
                }

                downloadList.innerHTML += `
                    <li style="display: block;">
                        <div class="progress-wrapper">
                            <div class="progress-header">
                                <span style="color: var(--text-main);">${downloadInfo.filename}</span>
                                <span style="color: ${barColor};">${displayProgress}</span>
                            </div>
                            <div class="progress-container">
                                <div class="progress-bar" style="width: ${barWidth}%; background-color: ${barColor};"></div>
                            </div>
                        </div>
                    </li>`;
            }
        }

    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

// Auto-refresh
setInterval(updateDashboard, 2000);

// Initial call on load
document.addEventListener('DOMContentLoaded', updateDashboard);