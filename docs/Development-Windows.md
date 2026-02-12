# Development on Windows

## Machine Requirements

CPU cores: >=12

RAM: >=32GB

Disk: Local Disk and >=800GB, SSD preferred

Internet speed: Download >= 300Mbps; Upload >= 75 Mbps

## To run on windows, you need to

(1) Download docker desktop on windows.

You need to turn on virtualization support on windows in BIOS when starting your computer.

(2) If you want to build repo on windows image, switch to Windows containers in docker settings.

(3) Enable long path in git. Open windows powershell as administrator,

```powershell
git config --global core.longpaths true
```

(4) Enable long path in Windows system.

and you can now run all the steps in the pipeline.

## Windows Notes
(1) The way to export environment variables in Windows is

```powershell
# powershell
$env:OPENAI_API_KEY="your_key"
```

```cmd
:: command line prompt
set OPENAI_API_KEY=your_key
```

(2) Runtime Warning

For Windows docker, if you save many images / containers on the same machine, the docker will become overloaded -- become very slow and can never start again next time.

So to run Windows instances plase run 20 instances as a batch, push to dockerhub or compress to elsewhere for backup, delete all containers and most images locally, and run next batch. Or, distribute jobs on many Windows machines with each machine processing 20 instances at a time.

(3) If applying patch has decoding problems, please

```powershell
# powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

(4) If you see the following error when repolaunch commits container to image:

```
500 Server Error for
http+docker://localnpipe/v1.52/commit?container=abfe0abab2fbba111ef56d0cd6af0ff4ec327de999f34d6528b1c044125613c9&repo=starryzhang%2Fsweb.eval.win&tag=szimek__signature_pa
d-835_windows&pause=True: Internal Server Error ("re-exec error: exit status 1: output: hcsshim::ImportLayer failed in Win32: The system cannot find the path specified.
(0x3)")
```

We currently consider it the bug of windows docker and does not count it into our success rate.
