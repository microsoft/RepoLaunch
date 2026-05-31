MOCK_PLATFORM_INSTANCES = {
    "windows" : [
r"""{
 "instance_id": "dotnet__runtime-126064",
 "docker_image_layers": {
  "base_image": "mcr.microsoft.com/dotnet/sdk:8.0-windowsservercore-ltsc2022",
  "setup_layer": [
   "\n    # Skip if git already present\n    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {\n    try {\n        # Prefer Chocolatey (cleaner package mgmt)\n        if (-not (Get-Command choco.exe -ErrorAction SilentlyContinue)) {\n        Set-ExecutionPolicy Bypass -Scope Process -Force\n        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12\n        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))\n        }\n\n        choco install git.install -y --no-progress --params '\"/GitOnlyOnPath /NoAutoCrlf\"'\n    }\n    catch {\n        Write-Host \"Chocolatey install failed: $($_.Exception.Message)  -> falling back to Git for Windows installer\"\n\n        # Fallback: Official Git for Windows silent install\n        $ProgressPreference = 'SilentlyContinue'\n        $temp = Join-Path $env:TEMP 'git-installer.exe'\n        # 'latest' link maintained by Git for Windows; resolves to current amd64 EXE\n        $url  = 'https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe'\n        try {\n        Invoke-WebRequest -Uri $url -OutFile $temp\n        } catch {\n        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $temp\n        }\n\n        # Silent/unattended flags per Git for Windows docs (Inno Setup):\n        # /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS\n        # Optional components: icons, ext\\reg\\shellhere, assoc, assoc_sh, gitlfs, windowsterminal, scalar\n        Start-Process -FilePath $temp -ArgumentList `\n        '/VERYSILENT','/NORESTART','/NOCANCEL','/SP-','/CLOSEAPPLICATIONS','/RESTARTAPPLICATIONS',`\n        '/COMPONENTS=\"icons,ext\\reg\\shellhere,assoc,assoc_sh,gitlfs,windowsterminal,scalar\"' `\n        -Wait\n    }\n\n    # Ensure PATH is updated in this running session (Chocolatey/Git installers update registry only)\n    $gitCmd = 'C:\\Program Files\\Git\\cmd'\n    $gitBin = 'C:\\Program Files\\Git\\bin'\n    if (Test-Path $gitCmd) { $env:PATH = \"$gitCmd;$gitBin;$env:PATH\" }\n    }\n    ",
   "git config --global --add safe.directory \"C:\\testbed\"; git init \"C:\\testbed\"; cd \"C:\\testbed\"; git remote add origin https://github.com/dotnet/runtime.git; git fetch --depth 1 origin d69ff06d522242b57825def7bb613fda6d4beebb; git reset --hard d69ff06d522242b57825def7bb613fda6d4beebb",
   "ls",
   "Get-ChildItem -Recurse -Filter *.sln | Select-Object -First 20",
   "Get-ChildItem -Recurse -Filter *.csproj | Select-Object -First 20",
   "Get-Content src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj",
   "dotnet restore src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj",
   "Get-Content global.json",
   "@'\n{\n  \"sdk\": {\n    \"version\": \"8.0.420\",\n    \"allowPrerelease\": false,\n    \"rollForward\": \"latestFeature\"\n  },\n  \"tools\": {\n    \"dotnet\": \"8.0.420\"\n  },\n  \"msbuild-sdks\": {\n    \"Microsoft.DotNet.Arcade.Sdk\": \"11.0.0-beta.26172.108\",\n    \"Microsoft.DotNet.Helix.Sdk\": \"11.0.0-beta.26172.108\",\n    \"Microsoft.DotNet.SharedFramework.Sdk\": \"11.0.0-beta.26172.108\",\n    \"Microsoft.Build.NoTargets\": \"3.7.0\",\n    \"Microsoft.Build.Traversal\": \"3.4.0\",\n    \"Microsoft.NET.Sdk.IL\": \"11.0.0-preview.3.26172.108\"\n  }\n}\n'@ | Set-Content -Path global.json",
   "dotnet restore src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj",
   "dotnet build src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release",
   "Select-String -Path Directory.Build.props,Directory.Build.targets,eng\\*.props,eng\\*.targets -Pattern \"GenerateResxSource|Arcade\" -SimpleMatch",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\tools\\GenerateResxSource.targets",
   "dotnet build src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:GenerateResxSource=false",
   "Select-String -Path . -Filter *.props,*.targets -Recurse -Pattern \"GenerateResxSource\" -SimpleMatch",
   "Get-ChildItem -Recurse -Include *.props,*.targets | Select-String -Pattern \"GenerateResxSource\" -SimpleMatch",
   "Get-Content Directory.Build.props",
   "Get-Content Directory.Build.rsp",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108 -Recurse -Include *.props,*.targets | Select-String -Pattern \"Disable|GenerateResxSource|ArcadeBuildTasks|BuildTasks\" -SimpleMatch",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\Sdks\\Microsoft.DotNet.Arcade.Sdk\\Sdk.targets",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\sdk",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\sdk\\Sdk.targets",
   "Get-Content Directory.Build.targets",
   "Get-Content eng\\resources.targets",
   "Get-Content src\\tools\\illink\\src\\ILLink.RoslynAnalyzer\\ILLink.RoslynAnalyzer.csproj",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108 -Recurse -Include *.targets,*.props | Select-String -Pattern \"_GenerateResxSource|GenerateResxSource\" -SimpleMatch",
   "Get-Content src\\coreclr\\tools\\aot\\DependencyGraphViewer\\DependencyGraphViewer.csproj",
   "Get-ChildItem -Recurse -Filter SR.cs | Select-String -Pattern \"System.Reflection.Metadata.SR\" -SimpleMatch",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\tools\\Imports.targets",
   "Get-Content src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj",
   "Get-Content eng\\generatorProjects.targets",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\sdk\\Sdk.props",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\tools\\GenerateResxSource.targets",
   "dotnet build src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:GenerateResxSource=false",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj,*.sln,*.proj | Select-String -Pattern \"ILLink.RoslynAnalyzer\" -SimpleMatch",
   "Get-Content eng\\liveBuilds.targets",
   "Get-Content eng\\generators.targets",
   "Get-Content Directory.Build.props",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\tools",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108\\tools\\net",
   "Get-Content eng\\liveILLink.targets",
   "dotnet build src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj | Select-String -Pattern \"Microsoft.Net.Compilers.Toolset\" -SimpleMatch",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj | Select-String -Pattern \"Compilers.Toolset|Net.Compilers\" -SimpleMatch",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.net.compilers.toolset\\5.6.0-2.26172.108\\build\\Microsoft.Net.Compilers.Toolset.props",
   "Get-Content Directory.Build.rsp",
   "Get-Content src\\coreclr\\tools\\aot\\DependencyGraphViewer\\DependencyGraphViewer.csproj",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj,*.sln | Select-String -Pattern \"Net.Compilers.Toolset\" -SimpleMatch",
   "Get-ChildItem \"C:\\Program Files\\dotnet\\packs\"",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj | Select-String -Pattern \"DisableImplicitFrameworkReferences|DisableStandardFrameworkReferences\" -SimpleMatch",
   "Get-ChildItem -Recurse -Include Directory.Packages.props,*.props,*.targets,*.csproj | Select-String -Pattern \"Microsoft.Net.Compilers.Toolset\" -SimpleMatch",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj,*.sln,*.json | Select-String -Pattern \"5.6.0-2.26172.108|Microsoft.Net.Compilers.Toolset\" -SimpleMatch",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj,*.sln,*.json | Select-String -Pattern \"CompilersToolset\" -SimpleMatch",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 /p:RoslynCompilerType=Framework",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj | Select-String -Pattern \"Roslyn|CompilerType|NetCompilersToolset\" -SimpleMatch",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108 -Recurse -Include *.props,*.targets | Select-String -Pattern \"RoslynCompilerType|NetCompilersToolset\" -SimpleMatch",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj | Select-String -Pattern \"MicrosoftNetCompilersToolset\" -SimpleMatch",
   "Get-Content Directory.Build.props",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.net.compilers.toolset\\5.6.0-2.26172.108\\build\\Microsoft.Net.Compilers.Toolset.targets",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.net.compilers.toolset\\5.6.0-2.26172.108\\build",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj,*.sln,*.json | Select-String -Pattern \"CompilersToolset\" -SimpleMatch",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.dotnet.arcade.sdk\\11.0.0-beta.26172.108 -Recurse -Include *.props,*.targets | Select-String -Pattern \"Net.Compilers.Toolset|CompilersToolset\" -SimpleMatch",
   "Get-Content artifacts\\obj\\coreclr\\DependencyGraphViewer\\DependencyGraphViewer.csproj.nuget.g.props",
   "Get-ChildItem -Recurse -Filter Directory.Packages.props",
   "Get-ChildItem C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.net.compilers.toolset\\5.6.0-2.26172.108 -Recurse -Include *.props,*.targets | Select-String -Pattern \"UseNetCompilersToolset|Disable|Toolset\" -SimpleMatch",
   "Get-Content C:\\Users\\ContainerAdministrator\\.nuget\\packages\\microsoft.net.compilers.toolset\\5.6.0-2.26172.108\\build\\Microsoft.Net.Compilers.Toolset.props",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj,*.sln | Select-String -Pattern \"MicrosoftNetCompilersToolsetVersion\" -SimpleMatch",
   "Get-ChildItem -Recurse -Include *.props,*.targets,*.csproj,*.sln | Select-String -Pattern \"Compilers\" -SimpleMatch",
   "Get-Content eng\\Versions.props",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 --logger \"console;verbosity=detailed\""
  ],
  "organize_layer": [
   "dotnet build src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0",
   "New-Item -ItemType Directory -Force -Path reports | Out-Null; dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 --logger \"json;LogFileName=reports\\test-results.json\"",
   "New-Item -ItemType Directory -Force -Path reports | Out-Null; dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 --logger \"trx;LogFileName=reports\\test-results.trx\"",
   "Get-Content src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\TestResults\\reports\\test-results.trx",
   "Get-Content src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\TestResults\\reports\\test-results.trx",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 --filter \"FullyQualifiedName=DependecyGraphViewer.Tests.TestFiileParsing.DependsOn\" --logger \"trx;LogFileName=reports\\single.trx\"",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 --list-tests",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 --filter \"FullyQualifiedName=DependecyGraphViewer.Tests.TestFileParsing.DependsOn\" --logger \"trx;LogFileName=reports\\single.trx\"",
   "dotnet test src\\coreclr\\tools\\aot\\DependencyGraphViewer\\Tests\\DependecyGraphViewer.Tests.csproj -c Release /p:_RequiresLiveILLink=false /p:UsingToolMicrosoftNetCompilers=false /p:RunAnalyzers=false /p:EnableNETAnalyzers=false /p:NetCoreAppToolCurrentVersion=8.0 /p:NetCoreAppCurrentVersion=8.0 /p:NetCoreAppToolCurrent=net8.0 /p:NetCoreAppCurrent=net8.0 --filter \"FullyQualifiedName=DependecyGraphViewer.Tests.TestFileParsing.NumberOfNodes&DisplayName~nodeCount: 0, isValid: False, linkCount: 0\" --logger \"trx;LogFileName=reports\\single.trx\""
  ]
 }
}""",
# A synthetic instance whose commands fail in every way (a throwing cmdlet, a native
# nonzero exit, and a failing *last* command in the *last* layer). A correct generator
# must still build the image successfully end-to-end (note 5).
r"""{
 "instance_id": "synthetic__windows-failing",
 "docker_image_layers": {
  "base_image": "mcr.microsoft.com/dotnet/sdk:8.0-windowsservercore-ltsc2022",
  "setup_layer": [
   "Write-Host marker-setup-ran",
   "Get-Item C:\\does\\not\\exist",
   "cmd /c exit 7"
  ],
  "organize_layer": [
   "Write-Host marker-organize-ran",
   "cmd /c exit 9"
  ]
 }
}"""
],

"android": [
r"""{
  "instance_id": "android-security-lints-5c27",
  "docker_image_layers": {
    "base_image": "cimg/android:2026.03.1",
    "setup_layer": [
      "command -v git >/dev/null || (apt-get update && apt-get install -y git)",
      "git config --global --add safe.directory /testbed; git init /testbed; cd /testbed; git remote add origin https://github.com/google/android-security-lints.git; git fetch --depth 1 origin 5c27e1bcfb29f55020e1529d3d18e476813ef79e; git reset --hard 5c27e1bcfb29f55020e1529d3d18e476813ef79e",
      "./gradlew test ",
      "./gradlew test ",
      "./gradlew test --info",
      "./gradlew :checks:test --rerun-tasks",
      "for f in checks/build/test-results/test/TEST-*.xml; do echo \"==== $f\"; cat \"$f\"; done"
    ],
    "organize_layer": [
      "./gradlew build",
      "./gradlew assemble",
      "./gradlew :checks:assemble",
      "./gradlew :checks:test --rerun-tasks",
      "for f in checks/build/test-results/test/TEST-*.xml; do echo \"==== $f\"; cat \"$f\"; done",
      "./gradlew build",
      "./gradlew assemble",
      "./gradlew :checks:assemble",
      "./gradlew :checks:test --rerun-tasks",
      "for f in checks/build/test-results/test/TEST-*.xml; do echo \"==== $f\"; cat \"$f\"; done",
      "./gradlew :checks:test --tests \"com.example.lint.checks.BadCryptographyUsageDetectorTest.testWhenNoUnsafeAlgoUsed_noWarning\" --rerun-tasks",
      "pwd",
      "ls checks/src/test/java/com/example/lint/checks",
      "./gradlew build",
      "./gradlew assemble",
      "./gradlew :checks:assemble",
      "./gradlew :checks:test --rerun-tasks",
      "for f in checks/build/test-results/test/TEST-*.xml; do echo \"==== $f\"; cat \"$f\"; done",
      "./gradlew build",
      "./gradlew assemble",
      "./gradlew :checks:assemble",
      "./gradlew :checks:test --rerun-tasks",
      "for f in checks/build/test-results/test/TEST-*.xml; do echo \"==== $f\"; cat \"$f\"; done",
      "./gradlew :checks:test --tests \"com.example.lint.checks.BadCryptographyUsageDetectorTest.testWhenNoUnsafeAlgoUsed_noWarning\" --rerun-tasks",
      "pwd",
      "ls checks/src/test/java/com/example/lint/checks"
    ]
  }
}""",
# A synthetic instance whose commands fail in every way (a command that errors, a
# nonzero exit, and a failing *last* command in the *last* layer). A correct generator
# must still build the image successfully end-to-end (note 5).
r"""{
  "instance_id": "synthetic__android-failing",
  "docker_image_layers": {
    "base_image": "cimg/android:2026.03.1",
    "setup_layer": [
      "echo marker-setup-ran",
      "false",
      "this-command-does-not-exist"
    ],
    "organize_layer": [
      "echo marker-organize-ran",
      "exit 3"
    ]
  }
}"""
],

"linux": [
r"""{
 "instance_id": "oxc-project__oxc-21163",
 "docker_image_layers": {
  "base_image": "rust:1.90",
  "setup_layer": [
   "apt update && apt install -y git",
   "git config --global --add safe.directory /testbed; git init /testbed; cd /testbed; git remote add origin https://github.com/oxc-project/oxc.git; git fetch --depth 1 origin 8e2ed83efd88806872d9ebb48960e3018fbea9c2; git reset --hard 8e2ed83efd88806872d9ebb48960e3018fbea9c2",
   "rustup toolchain install 1.94.1",
   "rustup override set 1.94.1",
   "cargo ck",
   "apt-get update && apt-get install -y cmake",
   "cargo ck",
   "cargo test --all-features",
   "sed -n '160,240p' crates/oxc_codegen/tests/integration/sourcemap.rs",
   "apt-get update && apt-get install -y nodejs",
   "curl -fsSL https://nodejs.org/dist/v24.14.0/node-v24.14.0-linux-x64.tar.xz -o /tmp/node.tar.xz && tar -C /usr/local --strip-components=1 -xJf /tmp/node.tar.xz",
   "node --version && cargo test --all-features",
   "npm install -g oxlint-tsgolint@0.20.0",
   "cargo test --all-features -- --nocapture"
  ],
  "organize_layer": [
   "cd /testbed && npm --version && node --version && cargo --version",
   "cd /testbed && test -f package-lock.json && echo has-lock || echo no-lock",
   "cd /testbed && ls -1 package-lock.json 2>/dev/null || true",
   "cd /testbed && mkdir -p reports && cargo test --all-features -- --format json 2>&1 | tee reports/cargo-test.jsonl",
   "cd /testbed && mkdir -p reports && cargo test --all-features -- --nocapture 2>&1 | tee reports/cargo-test.log",
   "cd /testbed && cat reports/cargo-test.log",
   "cd /testbed && cargo test -p oxc_allocator --all-features allocator::test::string_from_empty_array -- --nocapture"
  ]
 }
}""",
# A synthetic instance whose commands fail in every way (a command that errors, a
# nonzero exit, and a failing *last* command in the *last* layer). A correct generator
# must still build the image successfully end-to-end (note 5).
r"""{
 "instance_id": "synthetic__linux-failing",
 "docker_image_layers": {
  "base_image": "rust:1.90",
  "setup_layer": [
   "echo marker-setup-ran",
   "false",
   "this-command-does-not-exist"
  ],
  "organize_layer": [
   "echo marker-organize-ran",
   "exit 3"
  ]
 }
}"""
]
}

import json
import platform
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest

from launch.scripts.gen_dockerfile import (
    _encode_windows_command,
    gen_linux_dockerfile,
    gen_windows_dockerfile,
)
from launch.core.runtime import available_platforms


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def supported_integration_platforms() -> set[str]:
    system = platform.system().lower()
    if system == "windows":
        return {"windows"}
    if system == "linux":
        platforms = {"linux", "android"}
        #if os.environ.get("REPOLAUNCH_RUN_MACOS_INTEGRATION") == "1" and os.path.exists("/dev/kvm"):
        #    platforms.add("macos")
        return platforms
    return set()


def parsed_instances(raw_instances: list[str]) -> list[dict[str, Any]]:
    """The MOCK_PLATFORM_INSTANCES values are lists of JSON strings."""
    return [json.loads(raw) for raw in raw_instances]


def render_dockerfile(runtime_platform: str, instance: dict[str, Any]) -> str:
    """Render the dockerfile for one instance, dispatching on platform.

    Note the generators take the ``docker_image_layers`` sub-dict (LayerInfo), not the
    whole instance.
    """
    layers = instance["docker_image_layers"]
    if runtime_platform == "windows":
        return gen_windows_dockerfile(layers)
    if runtime_platform in ("linux", "android"):
        return gen_linux_dockerfile(layers)
    raise ValueError(f"Unsupported platform: {runtime_platform}")


def all_commands(instance: dict[str, Any]) -> list[str]:
    layers = instance["docker_image_layers"]
    return list(layers.get("setup_layer") or []) + list(layers.get("organize_layer") or [])


def check_docker_existance() -> None:
    """Skip (not fail) when the docker CLI / daemon is unavailable on this host."""
    subprocess.run(
        ["docker", "ps"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )


def write_dockerfile(tmp_path: Path, dockerfile: str) -> Path:
    path = tmp_path / f"Dockerfile_{uuid.uuid4().hex[:8]}"
    path.write_text(dockerfile, encoding="utf-8")
    return path


def run_docker(args: list[str]) -> subprocess.CompletedProcess:
    """Run a docker command with all output going straight to the screen.

    stdout/stderr are inherited (not captured), so the build log streams live. Run pytest
    with -s to see it in real time, or -rA to have pytest replay it for passing tests.
    """
    print("\n$ " + " ".join(args), flush=True)
    return subprocess.run(args, timeout=3600)


# Parametrization shared by the integration tests. The second tuple element keeps the
# original ``base_image`` slot name but actually carries the raw instance list for the
# platform (each item is a JSON string).
_PLATFORM_PARAMS = [
    pytest.param("linux", MOCK_PLATFORM_INSTANCES["linux"], id="linux"),
    pytest.param("android", MOCK_PLATFORM_INSTANCES["android"], id="android"),
    pytest.param("windows", MOCK_PLATFORM_INSTANCES["windows"], id="windows"),
    #pytest.param("macos", "sickcodes/docker-osx:auto", id="macos"),
]


# --------------------------------------------------------------------------- #
# unit tests (no docker) -- always run; lock the generator's output contract
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("runtime_platform", "raw_instances"), _PLATFORM_PARAMS)
def test_dockerfile_contains_base_image_and_all_commands(runtime_platform, raw_instances):
    """Every command (and the base image) must be present in the rendered dockerfile."""
    for instance in parsed_instances(raw_instances):
        dockerfile = render_dockerfile(runtime_platform, instance)
        assert isinstance(dockerfile, str)
        assert instance["docker_image_layers"]["base_image"] in dockerfile

        for cmd in all_commands(instance):
            if runtime_platform == "windows":
                # windows commands are sentinel-encoded; check the encoded form is present.
                assert _encode_windows_command(cmd) in dockerfile
            else:
                # linux commands are embedded verbatim (possibly across several lines).
                first_line = cmd.strip().splitlines()[0]
                assert first_line in dockerfile


@pytest.mark.parametrize(("runtime_platform", "raw_instances"), _PLATFORM_PARAMS)
def test_dockerfile_has_exactly_two_layers(runtime_platform, raw_instances):
    # Every instance has a setup and an organize layer, each rendered as exactly one RUN
    # instruction (notes 3 & 4). True for both generators: windows emits `RUN <script>`,
    # linux/android emit `RUN <<'RL_CMD_EOF'` -- both start the line with "RUN ".
    for instance in parsed_instances(raw_instances):
        dockerfile = render_dockerfile(runtime_platform, instance)
        run_instructions = [ln for ln in dockerfile.splitlines() if ln.startswith("RUN ")]
        assert len(run_instructions) == 2
        assert dockerfile.count("# ---- setup layer ----") == 1
        assert dockerfile.count("# ---- organize layer ----") == 1


@pytest.mark.integration
@pytest.mark.parametrize(("runtime_platform", "raw_instances"), _PLATFORM_PARAMS)
def test_gen_dockerfile_syntax(runtime_platform: available_platforms, raw_instances: list[str], tmp_path: Path):
    if runtime_platform not in supported_integration_platforms():
        #if runtime_platform == "macos" and host_platform.system().lower() == "linux":
        #    warnings.warn("macos integration test uses a big linux container with macos vm inside. Due to efficiency macos support is not tested by default. If you want to test macos behaviour, install kvm and export REPOLAUNCH_RUN_MACOS_INTEGRATION=1.")
        #    pytest.skip("MacosRuntime is not tested by default.")
        #else:
        pytest.skip(f"{runtime_platform} runtime is not supported on this host")
    check_docker_existance()
    for instance in parsed_instances(raw_instances):
        dockerfile = render_dockerfile(runtime_platform, instance)
        assert isinstance(dockerfile, str)
        df_path = write_dockerfile(tmp_path, dockerfile)
        print(f"\n===== Dockerfile [{instance['instance_id']}] =====\n{dockerfile}", flush=True)
        # docker buildx build --check -f <df> .  -> non-zero exit on any syntax/lint error
        proc = run_docker(["docker", "buildx", "build", "--check", "-f", str(df_path), str(tmp_path)])
        assert proc.returncode == 0, f"buildx --check failed for {instance['instance_id']}"


@pytest.mark.integration
@pytest.mark.parametrize(("runtime_platform", "raw_instances"), _PLATFORM_PARAMS)
def test_gen_dockerfile_should_siliently_bypass_error_commands(runtime_platform: available_platforms, raw_instances: list[str], tmp_path: Path):
    if runtime_platform not in supported_integration_platforms():
        #if runtime_platform == "macos" and host_platform.system().lower() == "linux":
        #    warnings.warn("macos integration test uses a big linux container with macos vm inside. Due to efficiency macos support is not tested by default. If you want to test macos behaviour, install kvm and export REPOLAUNCH_RUN_MACOS_INTEGRATION=1.")
        #    pytest.skip("MacosRuntime is not tested by default.")
        #else:
        pytest.skip(f"{runtime_platform} runtime is not supported on this host")
    check_docker_existance()

    # raw_instances holds the platform's real instance(s) plus a synthetic instance whose
    # commands fail in every way (a command that errors, a native nonzero exit, and a
    # failing *last* command in the *last* layer; see MOCK_PLATFORM_INSTANCES). A correct
    # generator must build every one of them successfully end-to-end: a failing command
    # must not abort the build (note 5).
    for instance in parsed_instances(raw_instances):
        dockerfile = render_dockerfile(runtime_platform, instance)
        df_path = write_dockerfile(tmp_path, dockerfile)
        print(f"\n===== Dockerfile [{instance['instance_id']}] =====\n{dockerfile}", flush=True)
        tag = f"repolaunch_gen_test:{runtime_platform}_{instance['instance_id'].replace('/', '_')}_{uuid.uuid4().hex[:8]}".lower()
        try:
            proc = run_docker(["docker", "build", "-f", str(df_path), "-t", tag, str(tmp_path)])
            assert proc.returncode == 0, f"build aborted for instance {instance['instance_id']}"
        finally:
            run_docker(["docker", "image", "rm", "-f", tag])

