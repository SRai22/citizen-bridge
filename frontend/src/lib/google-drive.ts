const MIME_TYPES = "application/pdf,image/jpeg,image/png,image/webp";

interface PickerDocument {
  id: string;
  name: string;
  mimeType: string;
}

interface PickerBuilder {
  addView(view: PickerView): PickerBuilder;
  setAppId(id: string): PickerBuilder;
  setCallback(callback: (data: { action: string; docs?: PickerDocument[] }) => void): PickerBuilder;
  setDeveloperKey(key: string): PickerBuilder;
  setOAuthToken(token: string): PickerBuilder;
  setOrigin(origin: string): PickerBuilder;
  build(): { setVisible(visible: boolean): void };
}

interface PickerView {
  setMimeTypes(types: string): PickerView;
}

interface GoogleWindow extends Window {
  gapi: { load(name: string, options: { callback(): void; onerror(): void }): void };
  google: {
    accounts: { oauth2: { initTokenClient(config: {
      client_id: string;
      scope: string;
      callback(response: { access_token?: string; error?: string }): void;
    }): { requestAccessToken(options: { prompt: string }): void } } };
    picker: {
      Action: { PICKED: string; CANCEL: string };
      DocsView: new () => PickerView;
      PickerBuilder: new () => PickerBuilder;
    };
  };
}

export async function pickGoogleDriveFile(): Promise<File> {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_DRIVE_CLIENT_ID;
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_DRIVE_API_KEY;
  const appId = process.env.NEXT_PUBLIC_GOOGLE_DRIVE_APP_ID;
  if (!clientId || !apiKey || !appId) {
    throw new Error("Google Drive needs CLIENT_ID, API_KEY, and APP_ID configuration.");
  }

  await Promise.all([
    loadScript("google-api", "https://apis.google.com/js/api.js"),
    loadScript("google-identity", "https://accounts.google.com/gsi/client"),
  ]);
  const googleWindow = window as unknown as GoogleWindow;
  await new Promise<void>((resolve, reject) => {
    googleWindow.gapi.load("picker", { callback: resolve, onerror: () => reject(new Error("Could not load Google Drive.")) });
  });
  const token = await new Promise<string>((resolve, reject) => {
    const client = googleWindow.google.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: "https://www.googleapis.com/auth/drive.file",
      callback: (response) => response.access_token
        ? resolve(response.access_token)
        : reject(new Error(response.error || "Google Drive access was not granted.")),
    });
    client.requestAccessToken({ prompt: "consent" });
  });
  const selected = await new Promise<PickerDocument>((resolve, reject) => {
    const picker = googleWindow.google.picker;
    const view = new picker.DocsView().setMimeTypes(MIME_TYPES);
    new picker.PickerBuilder()
      .addView(view)
      .setAppId(appId)
      .setDeveloperKey(apiKey)
      .setOAuthToken(token)
      .setOrigin(location.origin)
      .setCallback((data) => {
        if (data.action === picker.Action.PICKED && data.docs?.[0]) resolve(data.docs[0]);
        else if (data.action === picker.Action.CANCEL) reject(new Error("No Google Drive file was selected."));
      })
      .build()
      .setVisible(true);
  });
  const response = await fetch(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(selected.id)}?alt=media`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Could not download the selected Google Drive file.");
  return new File([await response.blob()], selected.name, { type: selected.mimeType });
}

function loadScript(id: string, src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.getElementById(id) as HTMLScriptElement | null;
    if (existing?.dataset.loaded === "true") return resolve();
    const script = existing ?? document.createElement("script");
    script.id = id;
    script.src = src;
    script.async = true;
    script.onload = () => { script.dataset.loaded = "true"; resolve(); };
    script.onerror = () => reject(new Error("Could not load Google Drive."));
    if (!existing) document.head.appendChild(script);
  });
}
