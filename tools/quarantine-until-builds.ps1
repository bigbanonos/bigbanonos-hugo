# tools/quarantine-until-builds.ps1
# Runs Hugo repeatedly. If it fails, finds the content/*.md file mentioned in the error and renames it to *.md.DISABLED.
# Stops when Hugo succeeds or when it can't detect a file.

$max = 300
$quarantined = @()

for ($i=0; $i -lt $max; $i++) {
  Write-Host "`nRun $($i+1): hugo --gc --minify"
  $out = & hugo --gc --minify 2>&1
  $code = $LASTEXITCODE

  if ($code -eq 0) {
    Write-Host "✅ Hugo build OK."
    break
  }

  $text = ($out -join "`n")

  # Match a markdown file path inside content/
  $m = [regex]::Match($text, 'content[/\\][^":]+\.md')
  if (!$m.Success) {
    Write-Host "❌ Build failed but I couldn't detect which content file caused it."
    Write-Host $text
    break
  }

  $rel = $m.Value
  $full = Join-Path (Get-Location) $rel

  if (!(Test-Path $full)) {
    Write-Host "❌ Hugo reported $rel but it doesn't exist locally at: $full"
    Write-Host "This usually means Netlify is building a different commit/branch than your local folder."
    break
  }

  $new = "$full.DISABLED"
  Write-Host "🚫 QUARANTINE: $rel -> $($rel).DISABLED"
  Move-Item -LiteralPath $full -Destination $new -Force
  $quarantined += $rel
}

Write-Host "`n--- Summary ---"
if ($quarantined.Count -gt 0) {
  Write-Host "Quarantined $($quarantined.Count) files:"
  $quarantined | ForEach-Object { Write-Host " - $_" }
} else {
  Write-Host "No files quarantined."
}
