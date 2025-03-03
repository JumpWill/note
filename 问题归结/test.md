```
powershell -ExecutionPolicy ByPass -Command "Set-NetFirewallRule -DisplayGroup “网络发现” -Enabled True -Profile Any"
powershell -ExecutionPolicy ByPass -Command "Enable-NetFirewallRule -DisplayGroup “文件和打印机共享”"
powershell -ExecutionPolicy ByPass -Command "Enable-NetFirewallRule -DisplayGroup “远程桌面”"
```
