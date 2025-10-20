$ErrorActionPreference = 'Stop'
$path = 'c:\Users\369\Documents\Bots\Music Industry Machine\config\SMM_Services_Tiers.csv'
$timestamp = Get-Date -Format yyyyMMdd_HHmmss
$backup = "$path.bak_$timestamp"
Copy-Item -LiteralPath $path -Destination $backup -Force

# Load CSV
$csv = Import-Csv -LiteralPath $path

# Remove miscategorized Instagram Saves rows (24516, 24520, 24517, 24584)
$removeIds = @('24516','24520','24517','24584')
$csv = $csv | Where-Object { $removeIds -notcontains $_.ID }

# Remove misplaced Instagram Likes row for 6290 (keep Shares rows)
$csv = $csv | Where-Object { -not (($_.ID -eq '6290') -and ($_.Platform -eq 'Instagram') -and ($_."Service Category" -eq 'Likes')) }

# Correct Telegram vs Instagram mix-ups for 6330/2650/6491
foreach ($row in $csv) {
    switch ($row.ID) {
        '6330' {
            $row.Platform = 'Telegram'
            $row.'Service Category' = 'Channel/Group Members'
            $row.Provider = 'JustAnotherPanel'
            $row.Name = 'Telegram Channel Members [Mixed - Max 50K]'
            $row.'Rate/1K' = '$0.08'
            $row.'Min/Max' = '10/50,000'
            $row.'Time/Speed' = '-'
            $row.'Why Organic/Notes' = 'Mixed quality accounts'
        }
        '2650' {
            $row.Platform = 'Telegram'
            $row.'Service Category' = 'Channel/Group Members'
            $row.Provider = 'JustAnotherPanel'
            $row.Name = 'Telegram Channel Members [HQ - Max 50K]'
            $row.'Rate/1K' = '$0.30'
            $row.'Min/Max' = '10/50,000'
            $row.'Time/Speed' = '-'
            $row.'Why Organic/Notes' = 'HQ accounts'
        }
        '6491' {
            $row.Platform = 'Telegram'
            $row.'Service Category' = 'Channel/Group Members'
            $row.Provider = 'JustAnotherPanel'
            $row.Name = 'Telegram Channel/Group Members [STABLE - NON DROP] [30 Days Guarantee]'
            $row.'Rate/1K' = '$0.88'
            $row.'Min/Max' = '100/1,000,000'
            $row.'Time/Speed' = '-'
            $row.'Why Organic/Notes' = 'Stable non-drop'
        }
    }
}

# Correct provider for Instagram Shares IDs to JustAnotherPanel
$idsToJAP = @('6290','6291','4309','4312','4356')
foreach ($row in $csv) {
    if ($idsToJAP -contains $row.ID -and $row.Platform -eq 'Instagram' -and $row.'Service Category' -eq 'Shares') {
        $row.Provider = 'JustAnotherPanel'
    }
}

# Save CSV back with same headers order
$csv | Export-Csv -LiteralPath $path -NoTypeInformation -Encoding UTF8
Write-Output ("Backup: {0}" -f $backup)
Write-Output 'Done. CSV updated.'
