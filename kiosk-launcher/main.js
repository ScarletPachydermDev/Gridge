const { app, components, BrowserWindow } = require("electron");

function targetUrl() {
  const arg = process.argv.slice(1).find((a) => /^https?:\/\//.test(a));
  if (!arg) {
    console.error("Usage: kiosk-launcher <url>");
    process.exit(1);
  }
  return arg;
}

const HIDE_SCROLLBAR_CSS = "::-webkit-scrollbar { width: 0 !important; height: 0 !important; }";

function createWindow(url) {
  const win = new BrowserWindow({
    fullscreen: true,
    frame: false,
    autoHideMenuBar: true,
  });
  win.webContents.on("did-finish-load", () => {
    win.webContents.insertCSS(HIDE_SCROLLBAR_CSS);
  });
  win.loadURL(url);
}

app.whenReady().then(async () => {
  await components.whenReady();
  createWindow(targetUrl());
});

app.on("window-all-closed", () => app.quit());
