// Helper to format file sizes
function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

// --- NEW: Helper to format transfer speeds ---
function formatSpeed(bytesPerSec) {
    if (!bytesPerSec || bytesPerSec === 0) return '0 B/s';
    const k = 1024;
    const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
    const i = Math.floor(Math.log(bytesPerSec) / Math.log(k));
    return `${parseFloat((bytesPerSec / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
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

        if (Object.keys(networkFiles).length === 0) {
            networkList.innerHTML = '<li class="empty-state">No files available on the network yet.</li>';
        } else {
            for (const [file_id, fileInfo] of Object.entries(networkFiles)) {
                const peerCount = fileInfo.peers.size;
                let swarmBadge = '';
                if (peerCount > 1) {
                    swarmBadge = `<span class="swarm-badge">⚡ Swarm (${peerCount})</span>`;
                }

                networkList.innerHTML += `
                    <li>
                        <div class="file-info">
                            <span class="file-name">${fileInfo.meta.filename}</span>
                            <span class="file-meta">${formatBytes(fileInfo.meta.size)}</span>
                            ${swarmBadge}
                        </div>
                        <div class="file-actions">
                            <form action="/download" method="POST" style="margin:0;">
                                <input type="hidden" name="file_id" value="${file_id}">
                                <button type="submit" class="btn-success">Download</button>
                            </form>
                        </div>
                    </li>`;
            }
        }

        // 2. Render My Files List
        const myFilesList = document.getElementById('my-files-list');
        myFilesList.innerHTML = '';
        for (const [file_id, meta] of Object.entries(data.my_files)) {
            myFilesList.innerHTML += `
                <li>
                    <div class="file-info">
                        <a href="/open/${file_id}" target="_blank" class="file-name">${meta.filename}</a>
                        <span class="file-meta">${formatBytes(meta.size)}</span>
                    </div>
                    <div class="file-actions">
                        <form action="/remove" method="POST" style="margin:0;">
                            <input type="hidden" name="file_id" value="${file_id}">
                            <button type="submit" class="btn-remove">Remove</button>
                        </form>
                    </div>
                </li>`;
        }

        // 3. RENDER DOWNLOADS (FIXED COLOR LOGIC)
        const downloadList = document.getElementById('download-list');
        downloadList.innerHTML = '';
        if (Object.keys(data.downloads).length === 0) {
            downloadList.innerHTML = '<li class="empty-state">No active downloads</li>';
        } else {
            for (const [file_id, downloadInfo] of Object.entries(data.downloads)) {
                let rawProgress = downloadInfo.progress; // Original value from Python
                let displayProgress;
                let barColor = "var(--success-color)";
                let barWidth = 0;
                let speedText = formatSpeed(downloadInfo.speed || 0);

                // --- THE FIX: Check for "Failed" BEFORE applying Math.floor ---
                if (rawProgress === "Failed") {
                    displayProgress = "Aborted / Failed";
                    barColor = "var(--danger-color)"; // Turn bar red
                    barWidth = 100;                   // Fill bar to show color
                    speedText = "Stopped";
                } else {
                    let progressNum = Math.floor(rawProgress || 0);
                    displayProgress = progressNum + "%";
                    barWidth = progressNum;

                    if (progressNum === 100) {
                        speedText = "Complete";
                        barColor = "var(--success-color)";
                    }
                }

                downloadList.innerHTML += `
                    <li style="display: block; position: relative; margin-bottom: 15px;">
                        <div class="progress-wrapper">
                            <div class="progress-header">
                                <span style="color: var(--text-main); font-weight: bold;">
                                    ${downloadInfo.filename}
                                    <span style="color:var(--text-muted); font-size:0.8rem; font-weight: normal; margin-left:10px;">${speedText}</span>
                                </span>
                                <span style="color: ${barColor}; font-weight: bold;">${displayProgress}</span>
                            </div>
                            <div class="progress-container" style="height: 10px; background: #e5e7eb; border-radius: 5px; overflow: hidden; margin-top: 5px;">
                                <div class="progress-bar" style="width: ${barWidth}%; height: 100%; background-color: ${barColor}; transition: width 0.3s ease;"></div>
                            </div>
                        </div>
                        ${rawProgress !== "Failed" && rawProgress !== 100 ?
                            `<a href="/abort/${file_id}" style="position: absolute; right: -25px; top: 0; color: #9ca3af; text-decoration: none; font-size: 1.2rem;">✕</a>`
                            : ''}
                    </li>`;
            }
        }

        // 4. RENDER UPLOADS / SEEDING (NEW!)
        const uploadList = document.getElementById('upload-list');
        // We wrap this in an IF statement just in case index.html hasn't been updated yet
        if (uploadList) {
            uploadList.innerHTML = '';
            if (!data.uploads || Object.keys(data.uploads).length === 0) {
                uploadList.innerHTML = '<li class="empty-state">Not currently seeding files.</li>';
            } else {
                for (const [ip, uploadInfo] of Object.entries(data.uploads)) {
                    let speedText = formatSpeed(uploadInfo.speed || 0);
                    uploadList.innerHTML += `
                        <li style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="color: var(--primary-color); font-weight: bold;">▲ Uploading:</span>
                                <span style="color: var(--text-main); margin-left: 5px;">${uploadInfo.filename}</span>
                                <div style="color: var(--text-muted); font-size: 0.8rem; margin-top: 3px;">To: ${ip}</div>
                            </div>
                            <div style="font-weight: bold; color: var(--success-color); background: #dcfce7; padding: 4px 8px; border-radius: 4px; font-size: 0.9rem;">
                                ${speedText}
                            </div>
                        </li>`;
                }
            }
        }

    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

// Auto-refresh every 2 seconds
setInterval(updateDashboard, 2000);

// Initial call on load
document.addEventListener('DOMContentLoaded', updateDashboard);