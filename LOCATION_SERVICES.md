# macOS Location Services for NetPulse

Starting in macOS 14.4+, accessing Wi-Fi metadata such as the BSSID and SSID via the `CoreWLAN` framework requires the requesting application to have **Location Services** permission authorized by the user.

## Why NetPulse Python Processes Do Not Prompt for Permission

When running NetPulse in development mode via tools like `python`, `Terminal.app`, or Antigravity, you will **not** see the macOS Location Services permission prompt for NetPulse, and it will not appear in **System Settings → Privacy & Security → Location Services**.

### The Reason
macOS enforces privacy permissions on an application bundle (`.app`) basis. The OS inspects the `Info.plist` of the executing binary's bundle to check for specific usage description keys (such as `NSLocationWhenInUseUsageDescription`).
- When running `python -m netpulse.app`, the executing binary is the Python interpreter (e.g., `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app`).
- The default Python interpreter's `Info.plist` **does not** contain the `NSLocationWhenInUseUsageDescription` key.
- Because the required key is missing, macOS silently denies the authorization request from `CLLocationManager` without prompting the user.

As a result, in pure Python development mode, `CoreWLAN` gracefully redacts the SSID (returning `None`), triggering NetPulse's fallback UI ("Wi-Fi Network").

**Development Workaround**: There is no direct way to grant a raw Python script Location Services without bypassing SIP or altering the Python framework's `Info.plist` (which is highly discouraged and often blocked by macOS). Testing SSID extraction requires packaging the application into an `.app` bundle.

## Requirements for the Packaged NetPulse.app

To ensure the packaged `.app` bundle successfully prompts for and receives Location Services permission, the final `.app` must be built (e.g., via `pyinstaller` or `py2app`) with an `Info.plist` that includes the required keys.

### Required `Info.plist` Keys

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>NetPulse requires Location Services permission to identify your active Wi-Fi network (SSID) for historical network usage tracking.</string>
<key>NSLocationUsageDescription</key>
<string>NetPulse requires Location Services permission to identify your active Wi-Fi network (SSID) for historical network usage tracking.</string>
```

### Runtime Handling in NetPulse
NetPulse handles this requirement at runtime via `WiFiInspector` in `netpulse/hardware/wifi.py`:
1. It dynamically loads the `CoreLocation.framework`.
2. It instantiates a `CLLocationManager`.
3. It checks the authorization status (`CLLocationManager.authorizationStatus()`).
4. If the status is `NotDetermined` (0), it invokes `requestWhenInUseAuthorization()`.
5. If running as a packaged app with the correct `Info.plist`, macOS will display the permission prompt to the user.
6. `CoreWLAN` handles the rest gracefully: if the user accepts, future network polls will contain the actual SSID. If denied, it continues to fallback to `"Wi-Fi Network"`.

This ensures NetPulse remains compliant with macOS privacy restrictions without resorting to undocumented shell commands or private APIs.
