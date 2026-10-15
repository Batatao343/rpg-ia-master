# Sintetiza a narração de cada cena com a voz pt-BR do Windows (SAPI).
# Entrada: JSON [{ "id": "...", "text": "...", "out": "caminho.wav" }]
param([Parameter(Mandatory = $true)][string]$JobsFile, [int]$Rate = 1)

Add-Type -AssemblyName System.Speech
$jobs = Get-Content -Raw -Encoding UTF8 $JobsFile | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice("Microsoft Maria Desktop")
$synth.Rate = $Rate
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$i = 0
foreach ($j in $jobs) {
    $i++
    $synth.SetOutputToWaveFile($j.out, $fmt)
    $synth.Speak($j.text)
    $synth.SetOutputToNull()
    Write-Output ("[{0}/{1}] {2}" -f $i, $jobs.Count, $j.id)
}
$synth.Dispose()
