# RAM livre + pytest/python orfaos (SPEC-386 R4). Chamado por scripts/dev/ram.sh. Saida ASCII.
$os = Get-CimInstance Win32_OperatingSystem
"RAM livre: {0:N1} GB de {1:N1} GB" -f ($os.FreePhysicalMemory / 1MB), ($os.TotalVisibleMemorySize / 1MB)
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'pytest|python -$|supabase' }
if ($procs) {
    $procs | ForEach-Object {
        $cmd = $_.CommandLine.Substring(0, [Math]::Min(90, $_.CommandLine.Length))
        "{0,7} {1,6:N0} MB  {2}" -f $_.ProcessId, ($_.WorkingSetSize / 1MB), $cmd
    }
    "matar: taskkill /T /F /PID <pid>  (nunca /IM python.exe)"
} else {
    "sem pytest/python orfao"
}
