param(
    [Parameter(Mandatory)][string]$Presentation,
    [Parameter(Mandatory)][string]$Pdf
)

$ErrorActionPreference = 'Stop'
$presentationPath = (Resolve-Path -LiteralPath $Presentation).Path
$pdfPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Pdf)
$powerPoint = New-Object -ComObject PowerPoint.Application
$deck = $null
try {
    # ReadOnly and WithWindow keep the export from editing the presentation or opening a window.
    $deck = $powerPoint.Presentations.Open($presentationPath, -1, 0, 0)
    $deck.SaveAs($pdfPath, 32)
    Write-Output "Exported $($deck.Slides.Count) slides to $pdfPath"
}
finally {
    if ($null -ne $deck) {
        $deck.Close()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($deck)
    }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint)
}
