+++
title = "Install Camp"
description = "Install instructions and current source-build guidance for Camp."
weight = 10
+++

# Install Camp

Camp is not packaged yet. The planned installer paths are shown here so the
site can settle around the intended user experience, but the working path today
is to build the compiler from source.

## Planned package managers

```sh
brew install camplang/tap/camp
```

```powershell
choco install camp
```

```powershell
winget install CampLang.Camp
```

## Build from source

Until binary releases and package-manager distribution are ready, clone the
compiler repository and build it with the .NET SDK:

```sh
git clone https://github.com/camplang-dev/camp.git
cd camp
dotnet build src/camplang.sln
```

After building, the compiler entry point is available from the repository's
`bin` directory.

