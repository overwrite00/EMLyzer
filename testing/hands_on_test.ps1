# Hands-on testing of EMLyzer with real email samples
# Analyzes 15 diverse emails and creates detailed report

$ErrorActionPreference = "Stop"

$emailDir = "D:\Documenti\Email per test analisi"
$outputDir = "D:\GitHub\EMLyzer\testing"
$apiBase = "http://localhost:8000/api"

# Select diverse samples
Write-Host "=" -ForegroundColor Green | ForEach-Object { Write-Host $_ -NoNewline } -End "`n"
Write-Host "EMLYZER HANDS-ON TESTING - Practical Analysis of Real Email Samples`n" -ForegroundColor Cyan

$allFiles = Get-ChildItem $emailDir -Filter "*.eml" | Sort-Object Length
$totalCount = $allFiles.Count

Write-Host "📧 Total emails in corpus: $totalCount"
Write-Host "Selecting 15 diverse samples (small, medium, large)...`n"

# Tercile selection
$tercile = [Math]::Floor($totalCount / 3)
$small = $allFiles[0..($tercile-1)] | Get-Random -Count 5
$medium = $allFiles[$tercile..(2*$tercile-1)] | Get-Random -Count 5
$large = $allFiles[(2*$tercile)..($totalCount-1)] | Get-Random -Count 5

$samples = @($small + $medium + $large) | Sort-Object Name

Write-Host "✓ Selected $(($small).Count + ($medium).Count + ($large).Count) samples" -ForegroundColor Green
Write-Host "  - Small files (phishing/spam): $($small.Count)"
Write-Host "  - Medium files (balanced): $($medium.Count)"
Write-Host "  - Large files (attachments): $($large.Count)`n"

# Results collection
$results = @{
    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    total_samples = $samples.Count
    analyses = @()
    statistics = @{}
    issues = @()
}

# Analyze each sample
$successCount = 0
foreach ($idx in 0..($samples.Count - 1)) {
    $sample = $samples[$idx]
    $filename = $sample.Name
    $fileSize = [Math]::Round($sample.Length / 1024, 1)

    Write-Host "[$($idx+1)/$($samples.Count)] Analyzing $filename ($fileSize KB)..."

    try {
        # Upload email
        $uploadResp = curl.exe -s -X POST `
            -F "file=@$($sample.FullName)" `
            "$apiBase/upload/" `
            -w "`n%{http_code}"

        $statusCode = $uploadResp[-1]
        $content = $uploadResp[0..($uploadResp.Count-2)] -join "`n"

        if ($statusCode -ne "200") {
            Write-Host "  ❌ Upload failed: $statusCode" -ForegroundColor Red
            $results.issues += @{ file = $filename; stage = "upload"; error = $statusCode }
            continue
        }

        $uploadJson = $content | ConvertFrom-Json
        $jobId = $uploadJson.job_id
        Write-Host "  ✓ Uploaded (job_id: $($jobId.Substring(0,8))...)" -ForegroundColor Green

        # Analyze
        Start-Sleep -Milliseconds 500
        $analysisResp = curl.exe -s -X POST "$apiBase/analysis/$jobId" -w "`n%{http_code}"
        $statusCode = $analysisResp[-1]
        $content = $analysisResp[0..($analysisResp.Count-2)] -join "`n"

        if ($statusCode -ne "200") {
            Write-Host "  ❌ Analysis failed: $statusCode" -ForegroundColor Red
            $results.issues += @{ file = $filename; stage = "analysis"; error = $statusCode }
            continue
        }

        $analysis = $content | ConvertFrom-Json
        Write-Host "  ✓ Analysis complete" -ForegroundColor Green

        # Wait for reputation phase
        Start-Sleep -Seconds 2
        $getResp = curl.exe -s "$apiBase/analysis/$jobId"
        $fullResult = $getResp | ConvertFrom-Json

        # Extract metrics
        $riskScore = $fullResult.risk_score
        $riskLabel = $fullResult.risk_label

        $headerFindings = ($fullResult.header_indicators.findings | Measure-Object).Count
        $bodyFindings = ($fullResult.body_indicators.findings | Measure-Object).Count
        $urlFindings = ($fullResult.url_indicators.findings | Measure-Object).Count
        $attFindings = ($fullResult.attachment_indicators.findings | Measure-Object).Count

        $repPhase = $fullResult.reputation_results.reputation_phase ?? "not_started"

        # Record
        $record = @{
            filename = $filename
            file_size_kb = $fileSize
            job_id = $jobId
            risk_score = $riskScore
            risk_label = $riskLabel
            indicators = @{
                header = $headerFindings
                body = $bodyFindings
                url = $urlFindings
                attachment = $attFindings
                total = $headerFindings + $bodyFindings + $urlFindings + $attFindings
            }
            reputation_phase = $repPhase
            key_findings = @{
                header = ($fullResult.header_indicators.findings | Select-Object -First 3 -ExpandProperty description)
                body = ($fullResult.body_indicators.findings | Select-Object -First 3 -ExpandProperty description)
                url = ($fullResult.url_indicators.findings | Select-Object -First 3 -ExpandProperty description)
                attachment = ($fullResult.attachment_indicators.findings | Select-Object -First 3 -ExpandProperty description)
            }
        }

        $results.analyses += $record

        if (-not $results.statistics[$riskLabel]) {
            $results.statistics[$riskLabel] = 0
        }
        $results.statistics[$riskLabel] += 1
        $successCount += 1

        # Print summary
        Write-Host "  Risk: $($riskLabel.ToUpper()) ($riskScore/100)" -ForegroundColor $(
            if ($riskLabel -eq "critical") { "Red" }
            elseif ($riskLabel -eq "high") { "Yellow" }
            elseif ($riskLabel -eq "medium") { "Cyan" }
            else { "Green" }
        )
        Write-Host "  Indicators: H:$headerFindings B:$bodyFindings U:$urlFindings A:$attFindings" -ForegroundColor Gray
        if ($headerFindings -gt 0) {
            Write-Host "    → $($record.key_findings.header[0])" -ForegroundColor Gray
        }

    } catch {
        Write-Host "  ❌ Error: $_" -ForegroundColor Red
        $results.issues += @{ file = $filename; error = $_.Exception.Message }
    }
}

# Save results
$outputFile = Join-Path $outputDir "hands_on_test_results.json"
$results | ConvertTo-Json -Depth 10 | Out-File $outputFile -Encoding UTF8

# Print summary
Write-Host "`n$('='*80)" -ForegroundColor Green
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "$('='*80)`n" -ForegroundColor Green

Write-Host "Analyzed: $successCount/$($samples.Count) emails" -ForegroundColor Green
Write-Host "Failed: $($results.issues.Count)`n" -ForegroundColor $(if ($results.issues.Count -gt 0) { "Red" } else { "Green" })

Write-Host "Risk Distribution:" -ForegroundColor Cyan
foreach ($label in ($results.statistics.Keys | Sort-Object)) {
    $count = $results.statistics[$label]
    $pct = if ($successCount -gt 0) { [Math]::Round(100 * $count / $successCount, 0) } else { 0 }
    Write-Host "  $($label.ToUpper()): $count ($pct%)" -ForegroundColor Gray
}

if ($results.analyses.Count -gt 0) {
    $totalIndicators = ($results.analyses | Measure-Object -Property @{e={$_.indicators.total}} -Sum).Sum
    $avgIndicators = [Math]::Round($totalIndicators / $results.analyses.Count, 1)
    Write-Host "`nIndicator Statistics:" -ForegroundColor Cyan
    Write-Host "  Average indicators per email: $avgIndicators" -ForegroundColor Gray
    Write-Host "  Total indicators found: $totalIndicators" -ForegroundColor Gray
}

Write-Host "`nResults saved to: $outputFile" -ForegroundColor Green
