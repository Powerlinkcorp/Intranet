// background.js
chrome.action.onClicked.addListener(async (tab) => {
    if (!tab.id) return;
    try {
        await chrome.tabs.sendMessage(tab.id, { action: "open_locked_panel" });
    } catch (err) {
        // Si la página se abrió antes de instalar la extensión, inyectamos el script en vivo
        try {
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ["content.js"]
            });
            await chrome.tabs.sendMessage(tab.id, { action: "open_locked_panel" });
        } catch (e) {
            console.error("No se puede inyectar en páginas protegidas del navegador:", e);
        }
    }
});