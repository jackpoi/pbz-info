# Icon only (no text -> safe for any script encoding).
#   powershell -ExecutionPolicy Bypass -File build\make_icon.ps1
# Output: build\app.ico  (256x256 PNG-in-ICO, Vista+)

Add-Type -AssemblyName System.Drawing

$out = $PSScriptRoot
$bg     = [System.Drawing.ColorTranslator]::FromHtml('#0A0908')
$accent = [System.Drawing.ColorTranslator]::FromHtml('#D24A32')
$muted  = [System.Drawing.ColorTranslator]::FromHtml('#6B5F54')

$size = 256
$bmp = New-Object System.Drawing.Bitmap($size, $size)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::Transparent)

# rounded square background
$radius = 52
$d = $radius * 2
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$path.AddArc(0, 0, $d, $d, 180, 90)
$path.AddArc($size - $d, 0, $d, $d, 270, 90)
$path.AddArc($size - $d, $size - $d, $d, $d, 0, 90)
$path.AddArc(0, $size - $d, $d, $d, 90, 90)
$path.CloseFigure()

$brush = New-Object System.Drawing.SolidBrush($bg)
$g.FillPath($brush, $path)

# same mark as the UI: diagonal + top-right bracket + short muted rule
$s = $size / 24.0
$redPen = New-Object System.Drawing.Pen($accent, (2.4 * $s))
$mutedPen = New-Object System.Drawing.Pen($muted, (1.6 * $s))
foreach ($p in @($redPen, $mutedPen)) {
    $p.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $p.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
}
$redPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

$g.DrawLine($mutedPen, [float](4.0 * $s), [float](12.5 * $s), [float](10.5 * $s), [float](12.5 * $s))
$g.DrawLine($redPen, [float](4.5 * $s), [float](19.5 * $s), [float](18.0 * $s), [float](6.0 * $s))
$g.DrawLine($redPen, [float](13.0 * $s), [float](4.6 * $s), [float](19.4 * $s), [float](4.6 * $s))
$g.DrawLine($redPen, [float](19.4 * $s), [float](4.6 * $s), [float](19.4 * $s), [float](11.0 * $s))

$g.Dispose()
$pngPath = Join-Path $out 'icon-256.png'
$bmp.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

# wrap PNG into ICO
$png = [System.IO.File]::ReadAllBytes($pngPath)
$ms = New-Object System.IO.MemoryStream
$bw = New-Object System.IO.BinaryWriter($ms)
$bw.Write([UInt16]0)
$bw.Write([UInt16]1)
$bw.Write([UInt16]1)
$bw.Write([Byte]0)
$bw.Write([Byte]0)
$bw.Write([Byte]0)
$bw.Write([Byte]0)
$bw.Write([UInt16]1)
$bw.Write([UInt16]32)
$bw.Write([UInt32]$png.Length)
$bw.Write([UInt32]22)
$bw.Write($png)
$bw.Flush()
[System.IO.File]::WriteAllBytes((Join-Path $out 'app.ico'), $ms.ToArray())
$bw.Dispose(); $ms.Dispose()
Remove-Item $pngPath -Force

Write-Host "icon: $(Join-Path $out 'app.ico')"
