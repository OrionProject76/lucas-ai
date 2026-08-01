extends Node

var update_interval: float = 1.0
var timer: float = 0.0

func _ready():
    print("SystemMonitor initialise")

func _process(delta: float):
    timer += delta
    if timer >= update_interval:
        timer = 0.0
        _update_stats()

func _update_stats():
    var output = []
    var exit_code = OS.execute("powershell", [
        "-Command",
        "$cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue; " +
        "$ram = Get-WmiObject Win32_OperatingSystem | Select-Object @{Name='RAM';Expression={[math]::Round((($_.TotalVisibleMemorySize - $_.FreePhysicalMemory) / $_.TotalVisibleMemorySize) * 100, 1)}}; " +
        "Write-Output "$([math]::Round($cpu,1)),$($ram.RAM)""
    ], output, true)
    var cpu = 0.0
    var ram = 0.0
    if exit_code == OK and output.size() > 0:
        var parts = output[0].strip_edges().split(",")
        if parts.size() >= 2:
            cpu = float(parts[0])
            ram = float(parts[1])
    var gpu = 0.0
    var gpu_out = []
    var gpu_exit = OS.execute("powershell", [
        "-Command",
        "try { $g = (nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>$null).Trim(); if($g) { Write-Output $g } else { Write-Output 0 } } catch { Write-Output 0 }"
    ], gpu_out, true)
    if gpu_exit == OK and gpu_out.size() > 0:
        gpu = float(gpu_out[0].strip_edges())
    Global.system_data_updated.emit(cpu, ram, gpu)
