# 截图工具：定位窗口截图，不需要抢前台（PrintWindow），抢不到时再退回置顶截图
#   powershell -ExecutionPolicy Bypass -File tools\shot.ps1 -TargetPid 1234 -Out shot.png [-Scroll 6]
param(
    [int]$TargetPid,
    [string]$ProcessName,
    [string]$Out,
    [int]$Scroll = 0
)

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class Snap {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, int d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  public const uint WHEEL = 0x0800;
  public static readonly IntPtr TOPMOST = new IntPtr(-1);
  public static readonly IntPtr NOTOPMOST = new IntPtr(-2);
  public struct RECT { public int Left, Top, Right, Bottom; }
  public static IntPtr FindMain(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p != pid || !IsWindowVisible(h)) return true;
      var c = new StringBuilder(300); GetClassNameW(h, c, 300);
      if (c.ToString().StartsWith("WindowsForms")) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
"@

[Snap]::SetProcessDPIAware() | Out-Null
$h = [IntPtr]::Zero
if ($TargetPid -gt 0) {
    $h = [Snap]::FindMain([uint32]$TargetPid)
}
if ($h -eq [IntPtr]::Zero -and $ProcessName) {
    # onefile 打包后窗口属于子进程，按进程名挨个找更省事
    foreach ($proc in @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)) {
        $h = [Snap]::FindMain([uint32]$proc.Id)
        if ($h -ne [IntPtr]::Zero) { break }
    }
}
if ($h -eq [IntPtr]::Zero) { Write-Error "找不到主窗口"; exit 1 }

$r = New-Object Snap+RECT
[Snap]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.Right - $r.Left
$hh = $r.Bottom - $r.Top

if ($Scroll -ne 0) {
    # 滚轮会送到鼠标位置的窗口；先把窗口临时置顶抢焦点再滚
    [Snap]::SetWindowPos($h, [Snap]::TOPMOST, 0, 0, 0, 0, 0x0001 -bor 0x0002 -bor 0x0040) | Out-Null
    [Snap]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 500
    [Snap]::SetCursorPos($r.Left + [int]($w * 0.68), $r.Top + [int]($hh * 0.6)) | Out-Null
    Start-Sleep -Milliseconds 250
    $steps = [math]::Abs($Scroll)
    $delta = if ($Scroll -gt 0) { -120 } else { 120 }
    for ($i = 0; $i -lt $steps; $i++) {
        [Snap]::mouse_event([Snap]::WHEEL, 0, 0, $delta, [IntPtr]::Zero)
        Start-Sleep -Milliseconds 70
    }
    Start-Sleep -Milliseconds 400
}

# 1) 先试 PrintWindow（不打扰前台）
$bmp = New-Object System.Drawing.Bitmap($w, $hh)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
$ok = [Snap]::PrintWindow($h, $hdc, 2)
$g.ReleaseHdc($hdc)
$g.Dispose()

# 判断是不是全黑（WebView2 常见）
$sample = 0
for ($x = 20; $x -lt $w; $x += 97) {
    for ($y = 20; $y -lt $hh; $y += 83) {
        $c = $bmp.GetPixel($x, $y)
        $sample += $c.R + $c.G + $c.B
    }
}

if (-not $ok -or $sample -lt 2000) {
    # 2) 退回"临时置顶 + 屏幕抓取"
    $bmp.Dispose()
    [Snap]::SetWindowPos($h, [Snap]::TOPMOST, 0, 0, 0, 0, 0x0001 -bor 0x0002) | Out-Null
    [Snap]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 900
    $bmp = New-Object System.Drawing.Bitmap($w, $hh)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size($w, $hh)))
    $g.Dispose()
    [Snap]::SetWindowPos($h, [Snap]::NOTOPMOST, 0, 0, 0, 0, 0x0001 -bor 0x0002) | Out-Null
    Write-Host "used screen capture (occluded)"
} else {
    Write-Host "used PrintWindow"
}

$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "saved $Out (${w}x${hh})"
