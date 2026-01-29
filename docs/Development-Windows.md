# Development on Windows

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

