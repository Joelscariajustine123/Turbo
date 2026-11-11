# Generates the Android/iOS platform folders for the three Turbo apps and
# adds the permissions they need. Run once after installing Flutter:
#
#   cd mobile
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#
# Safe to run again: your lib/ code and pubspec.yaml are always kept.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$utf8 = New-Object System.Text.UTF8Encoding $false

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    Write-Error 'Flutter is not on PATH. Install it from https://docs.flutter.dev/get-started/install and reopen the terminal.'
}

function Write-Text($path, $text) { [System.IO.File]::WriteAllText($path, $text, $utf8) }

function Patch-Android($app, [string[]]$permissions) {
    $path = Join-Path $root "$app\android\app\src\main\AndroidManifest.xml"
    if (-not (Test-Path $path)) { return }
    $xml = [System.IO.File]::ReadAllText($path)

    foreach ($p in $permissions) {
        if ($xml -notmatch [regex]::Escape("android.permission.$p")) {
            $xml = $xml -replace '(<application)', "<uses-permission android:name=`"android.permission.$p`"/>`r`n    `$1"
        }
    }
    # Allow plain http:// to your development server.
    if ($xml -notmatch 'usesCleartextTraffic') {
        $xml = ([regex]'<application').Replace($xml, '<application android:usesCleartextTraffic="true"', 1)
    }
    # Let url_launcher open the phone dialer, UPI apps and email.
    if ($xml -notmatch 'android:scheme="upi"') {
        $intents = @'
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="upi"/></intent>
        <intent><action android:name="android.intent.action.DIAL"/><data android:scheme="tel"/></intent>
        <intent><action android:name="android.intent.action.SENDTO"/><data android:scheme="mailto"/></intent>
'@
        if ($xml -match '<queries>') {
            $xml = ([regex]'<queries>').Replace($xml, "<queries>`r`n$intents", 1)
        } else {
            $xml = $xml -replace '</manifest>', "    <queries>`r`n$intents    </queries>`r`n</manifest>"
        }
    }
    Write-Text $path $xml
}

function Patch-Ios($app, [hashtable]$keys) {
    $path = Join-Path $root "$app\ios\Runner\Info.plist"
    if (-not (Test-Path $path)) { return }
    $plist = [System.IO.File]::ReadAllText($path)
    $add = ''
    foreach ($k in $keys.Keys) {
        if ($plist -notmatch [regex]::Escape("<key>$k</key>")) { $add += "`t<key>$k</key>`n`t$($keys[$k])`n" }
    }
    if ($add) {
        $i = $plist.LastIndexOf('</dict>')
        $plist = $plist.Substring(0, $i) + $add + $plist.Substring($i)
        Write-Text $path $plist
    }
}

function Create-App($app) {
    $dir = Join-Path $root $app
    Write-Host "`n=== $app ===" -ForegroundColor Cyan
    $backup = Join-Path $env:TEMP "turbo-$app-backup"
    if (Test-Path $backup) { Remove-Item -Recurse -Force $backup }
    New-Item -ItemType Directory $backup | Out-Null
    Copy-Item -Recurse (Join-Path $dir 'lib') $backup
    Copy-Item (Join-Path $dir 'pubspec.yaml'), (Join-Path $dir 'analysis_options.yaml') $backup

    Push-Location $dir
    try {
        flutter create --org com.turbocab --project-name $app --platforms android,ios .
        if ($LASTEXITCODE -ne 0) { throw "flutter create failed for $app" }
    } finally { Pop-Location }

    # Put our code back exactly as it was.
    Remove-Item -Recurse -Force (Join-Path $dir 'lib')
    Copy-Item -Recurse (Join-Path $backup 'lib') $dir
    Copy-Item (Join-Path $backup 'pubspec.yaml'), (Join-Path $backup 'analysis_options.yaml') $dir -Force
    # The generated sample test refers to a counter app that doesn't exist.
    $sample = Join-Path $dir 'test\widget_test.dart'
    if (Test-Path $sample) { Remove-Item $sample }

    Push-Location $dir
    try { flutter pub get } finally { Pop-Location }
}

Push-Location (Join-Path $root 'turbo_core')
try { flutter pub get } finally { Pop-Location }

Create-App 'turbo_rider'
Patch-Android 'turbo_rider' @('INTERNET', 'ACCESS_FINE_LOCATION', 'ACCESS_COARSE_LOCATION')
Patch-Ios 'turbo_rider' @{
    'NSLocationWhenInUseUsageDescription' = '<string>Turbo uses your location to set your pickup point.</string>'
    'LSApplicationQueriesSchemes'         = '<array><string>tel</string><string>upi</string></array>'
    'NSAppTransportSecurity'              = '<dict><key>NSAllowsArbitraryLoads</key><true/></dict>'
}

Create-App 'turbo_driver'
# Live tracking: location + a foreground service so GPS keeps working with the screen locked.
Patch-Android 'turbo_driver' @('INTERNET', 'CAMERA', 'ACCESS_FINE_LOCATION', 'ACCESS_COARSE_LOCATION',
    'FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_LOCATION', 'WAKE_LOCK', 'POST_NOTIFICATIONS')
Patch-Ios 'turbo_driver' @{
    'NSCameraUsageDescription'                    = '<string>Take a profile photo for riders to recognise you.</string>'
    'NSPhotoLibraryUsageDescription'              = '<string>Choose a profile photo for riders to recognise you.</string>'
    'NSLocationWhenInUseUsageDescription'         = '<string>Turbo shares your location with the rider of a ride you accepted.</string>'
    'NSLocationAlwaysAndWhenInUseUsageDescription' = '<string>Turbo keeps sharing your location with your rider while the screen is locked during a ride.</string>'
    'UIBackgroundModes'                           = '<array><string>location</string></array>'
    'LSApplicationQueriesSchemes'                 = '<array><string>tel</string><string>https</string></array>'
    'NSAppTransportSecurity'                      = '<dict><key>NSAllowsArbitraryLoads</key><true/></dict>'
}

Create-App 'turbo_admin'
Patch-Android 'turbo_admin' @('INTERNET')
Patch-Ios 'turbo_admin' @{
    'LSApplicationQueriesSchemes' = '<array><string>mailto</string></array>'
    'NSAppTransportSecurity'      = '<dict><key>NSAllowsArbitraryLoads</key><true/></dict>'
}

Write-Host "`nDone. Start Django with:  python manage.py runserver 0.0.0.0:8000" -ForegroundColor Green
Write-Host "Then run an app, e.g.:    cd turbo_rider; flutter run" -ForegroundColor Green
Write-Host "On a real phone add:      --dart-define=API_URL=http://<your-PC-LAN-IP>:8000" -ForegroundColor Green
