const { app, components, BrowserWindow } = require("electron");

function targetUrl() {
  const arg = process.argv.slice(1).find((a) => /^https?:\/\//.test(a));
  if (!arg) {
    console.error("Usage: kiosk-launcher <url>");
    process.exit(1);
  }
  return arg;
}

function createWindow(url) {
  const win = new BrowserWindow({
    fullscreen: true,
    frame: false,
    autoHideMenuBar: true,
  });
  win.loadURL(url);
}

app.whenReady().then(async () => {
  await components.whenReady();
  createWindow(targetUrl());
});

app.on("window-all-closed", () => app.quit());
