$root = Join-Path (Get-Location) "content"
if (!(Test-Path $root)) { Write-Host "No content/ folder found. Run from repo root."; exit 1 }

$files = Get-ChildItem $root -Recurse -Filter *.md -File
$fixed = 0

foreach ($f in $files) {
  $bytes = [IO.File]::ReadAllBytes($f.FullName)

  if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    $bytes = $bytes[3..($bytes.Length-1)]
  }

  $text = [Text.Encoding]::UTF8.GetString($bytes)

  $text2 = -join ($text.ToCharArray() | Where-Object {
    $c = [int][char]$_
    ($c -ge 32) -or ($c -in 9,10,13)
  })

  $m = [regex]::Match($text2, "(?m)^\-\-\-\s*$")
  if ($m.Success -and $m.Index -gt 0) {
    $text2 = $text2.Substring($m.Index)
  }

  $newBytes = (New-Object Text.UTF8Encoding($false)).GetBytes($text2)

  if ($text2 -ne $text) {
    [IO.File]::WriteAllBytes($f.FullName, $newBytes)
    $fixed++
  }
}

Write-Host "Sanitized files changed: $fixed"
